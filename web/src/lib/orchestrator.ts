import type { KitchenRisk, Trace } from "@/lib/trace";

/**
 * Client for the FastAPI orchestrator.
 *
 * The contract is poll-based rather than streamed: a run pauses on
 * `awaiting_human` until the kitchen answers, and polling makes that pause
 * trivial to represent on both sides.
 *
 *   GET  {base}/health                    -> { ok, mode, dishes, open_runs }
 *   POST {base}/api/case                  -> { run_id }          (503 when full)
 *   GET  {base}/api/case/{run_id}         -> RunState
 *   POST {base}/api/case/{run_id}/answer  -> RunState            (409 once answered)
 */

const DEVELOPMENT_DEFAULT_URL = "http://127.0.0.1:8000";

/**
 * The orchestrator base URL, or null when there is none to talk to.
 *
 * Only `NEXT_PUBLIC_ORCHESTRATOR_URL` names a backend. The localhost default
 * exists for `next dev` alone: a production page must never probe the
 * visitor's own machine.
 */
function resolveOrchestratorUrl(): string | null {
  const configured = process.env.NEXT_PUBLIC_ORCHESTRATOR_URL?.trim();
  if (configured) return configured.replace(/\/+$/, "");
  if (process.env.NODE_ENV === "development") return DEVELOPMENT_DEFAULT_URL;
  return null;
}

export const ORCHESTRATOR_URL = resolveOrchestratorUrl();

export const POLL_INTERVAL_MS = 900;

/** One health request. Long enough for a sleeping free-tier host to answer. */
const HEALTH_TIMEOUT_MS = 15_000;
/** Pause between health attempts while the host boots. */
const HEALTH_RETRY_DELAY_MS = 3_000;
/** Give up waking after this long and fall back to recorded runs. */
export const WAKE_BUDGET_MS = 65_000;

const HTTP_CONFLICT = 409;
const HTTP_SERVICE_UNAVAILABLE = 503;

/** `rules` is the keyless hosted mode; `gemma` means Gemma 4 E2B is loaded. */
export type AgentMode = "rules" | "gemma";

export type RunStatus =
  "running" | "awaiting_human" | "answering" | "complete" | "failed";

export interface RunState {
  run_id: string;
  status: RunStatus;
  /** The question the agent needs the kitchen to answer, when `awaiting_human`. */
  pending_question?: string;
  /** Everything known so far. `verdict` is only meaningful once complete. */
  trace: Trace;
  error?: string;
}

export interface CaseRequest {
  /** What the diner said, typed. */
  text?: string;
  /** What the diner said, recorded. Only a Gemma-mode backend can hear it. */
  audio?: Blob;
}

/** The kitchen's structured reply: a risk call plus an optional free note. */
export interface KitchenAnswer {
  risk: KitchenRisk;
  note?: string;
}

/** An HTTP failure that keeps its status, so callers can treat 409/503 apart. */
export class OrchestratorError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
  ) {
    super(message);
    this.name = "OrchestratorError";
  }

  /** The case was already answered, possibly from another device. */
  get isConflict(): boolean {
    return this.status === HTTP_CONFLICT;
  }

  /** Every case slot is held by a run still waiting on a kitchen. */
  get isBusy(): boolean {
    return this.status === HTTP_SERVICE_UNAVAILABLE;
  }
}

/** The base URL, or a thrown error when this build has no backend configured. */
function baseUrl(): string {
  if (!ORCHESTRATOR_URL)
    throw new OrchestratorError("no live agent is configured", null);
  return ORCHESTRATOR_URL;
}

/** Parse a JSON response, turning any non-2xx into an `OrchestratorError`. */
async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `live agent returned ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // The status alone is enough to act on.
    }
    throw new OrchestratorError(detail, response.status);
  }
  return (await response.json()) as T;
}

/** Browsers record webm/ogg; the filename is how the orchestrator learns the format. */
function audioFilename(blob: Blob): string {
  if (blob.type.includes("ogg")) return "request.ogg";
  if (blob.type.includes("mp4")) return "request.mp4";
  if (blob.type.includes("wav")) return "request.wav";
  return "request.webm";
}

/** Open a case and return its run id. */
async function postCase(request: CaseRequest): Promise<string> {
  const body = new FormData();
  if (request.text) body.set("text", request.text);
  if (request.audio)
    body.set("audio", request.audio, audioFilename(request.audio));

  const response = await fetch(`${baseUrl()}/api/case`, {
    method: "POST",
    body,
  });
  const data = await readJson<{ run_id: string }>(response);
  return data.run_id;
}

/** The run as it stands now. */
async function getRun(runId: string): Promise<RunState> {
  return readJson<RunState>(await fetch(`${baseUrl()}/api/case/${runId}`));
}

/**
 * Send the kitchen's answer. A structured answer is preferred; a plain string
 * is still accepted by the backend and read fail-closed.
 */
async function postAnswer(
  runId: string,
  answer: KitchenAnswer | string,
): Promise<RunState> {
  const payload =
    typeof answer === "string"
      ? { answer }
      : { risk: answer.risk, ...(answer.note ? { note: answer.note } : {}) };
  const response = await fetch(`${baseUrl()}/api/case/${runId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<RunState>(response);
}

export const orchestrator = { postCase, getRun, postAnswer };

/**
 * One health request with its own timeout.
 *
 * @returns The backend's mode, or null when it did not answer in time.
 */
export async function checkHealth(
  signal?: AbortSignal,
): Promise<AgentMode | null> {
  if (!ORCHESTRATOR_URL) return null;
  const timeout = AbortSignal.timeout(HEALTH_TIMEOUT_MS);
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
  try {
    const response = await fetch(`${ORCHESTRATOR_URL}/health`, {
      signal: combined,
      cache: "no-store",
    });
    if (!response.ok) return null;
    const body = (await response.json()) as { mode?: string };
    return body.mode === "gemma" ? "gemma" : "rules";
  } catch {
    return null;
  }
}

/** True when a real orchestrator is reachable, so the UI knows which mode it is in. */
export async function probeOrchestrator(
  signal?: AbortSignal,
): Promise<boolean> {
  return (await checkHealth(signal)) !== null;
}

/** Resolve after `ms`, or early and quietly when `signal` aborts. */
function pause(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = window.setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      window.clearTimeout(timer);
      resolve();
    });
  });
}

/**
 * Keep asking `/health` until the host answers or the wake budget runs out.
 *
 * A free-tier host sleeps when idle and takes up to about a minute to boot,
 * so one failed probe is not evidence that the agent is down.
 *
 * @param onWaiting Called once the first attempt has failed, so the UI can say
 *   it is waking the agent rather than silently replaying.
 */
export async function wakeOrchestrator(
  signal: AbortSignal,
  onWaiting: () => void,
): Promise<AgentMode | null> {
  if (!ORCHESTRATOR_URL) return null;
  const deadline = Date.now() + WAKE_BUDGET_MS;
  let attempt = 0;
  while (!signal.aborted && Date.now() < deadline) {
    const mode = await checkHealth(signal);
    if (mode) return mode;
    if (attempt === 0) onWaiting();
    attempt += 1;
    await pause(HEALTH_RETRY_DELAY_MS, signal);
  }
  return null;
}
