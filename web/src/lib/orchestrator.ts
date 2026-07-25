import type { Trace, TraceStep } from "@/lib/trace";

/**
 * Client for the FastAPI orchestrator, plus a demo fallback.
 *
 * The contract is deliberately poll-based rather than streamed: a run pauses on
 * `awaiting_human` until someone answers the kitchen question, and polling makes
 * that pause trivial to represent on both sides.
 *
 *   POST {base}/api/case                  -> { run_id }
 *   GET  {base}/api/case/{run_id}         -> RunState
 *   POST {base}/api/case/{run_id}/answer  -> RunState
 */

export const ORCHESTRATOR_URL =
  process.env.NEXT_PUBLIC_ORCHESTRATOR_URL ?? "http://127.0.0.1:8000";

export const POLL_INTERVAL_MS = 900;

export type RunStatus = "running" | "awaiting_human" | "complete" | "failed";

export interface RunState {
  run_id: string;
  status: RunStatus;
  /** The question the agent needs a human to answer, when `awaiting_human`. */
  pending_question?: string;
  /** Everything known so far. `verdict` is only meaningful once complete. */
  trace: Trace;
  error?: string;
}

export interface CaseRequest {
  /** What the diner said, typed. */
  text?: string;
  /** What the diner said, recorded. Gemma transcribes and understands it. */
  audio?: Blob;
}

/** The EU 14 declarable allergens — Regulation (EU) No 1169/2011. */
export const EU_ALLERGENS = [
  "peanut",
  "nuts",
  "milk",
  "eggs",
  "fish",
  "crustaceans",
  "molluscs",
  "cereals containing gluten",
  "soybeans",
  "celery",
  "mustard",
  "sesame",
  "lupin",
  "sulphites",
] as const;

export const DINER_LANGUAGES = [
  { code: "ar", name: "Arabic" },
  { code: "uk", name: "Ukrainian" },
  { code: "fr", name: "French" },
  { code: "es", name: "Spanish" },
  { code: "zh", name: "Chinese" },
  { code: "en", name: "English" },
] as const;

/** Browsers record webm/ogg; the filename is how the orchestrator learns the format. */
function audioFilename(blob: Blob): string {
  if (blob.type.includes("ogg")) return "request.ogg";
  if (blob.type.includes("mp4") || blob.type.includes("mp4a"))
    return "request.mp4";
  if (blob.type.includes("wav")) return "request.wav";
  return "request.webm";
}

async function postCase(request: CaseRequest): Promise<string> {
  const body = new FormData();
  if (request.text) body.set("text", request.text);
  if (request.audio)
    body.set("audio", request.audio, audioFilename(request.audio));

  const response = await fetch(`${ORCHESTRATOR_URL}/api/case`, {
    method: "POST",
    body,
  });
  if (!response.ok) throw new Error(`orchestrator returned ${response.status}`);

  const data = (await response.json()) as { run_id: string };
  return data.run_id;
}

async function getRun(runId: string): Promise<RunState> {
  const response = await fetch(`${ORCHESTRATOR_URL}/api/case/${runId}`);
  if (!response.ok) throw new Error(`orchestrator returned ${response.status}`);
  return (await response.json()) as RunState;
}

async function postAnswer(runId: string, answer: string): Promise<RunState> {
  const response = await fetch(`${ORCHESTRATOR_URL}/api/case/${runId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answer }),
  });
  if (!response.ok) throw new Error(`orchestrator returned ${response.status}`);
  return (await response.json()) as RunState;
}

/** True when a real orchestrator is reachable, so the UI knows which mode it is in. */
export async function probeOrchestrator(
  signal?: AbortSignal,
): Promise<boolean> {
  try {
    const response = await fetch(`${ORCHESTRATOR_URL}/health`, { signal });
    return response.ok;
  } catch {
    return false;
  }
}

export const orchestrator = { postCase, getRun, postAnswer };

/**
 * Replays a recorded run when the orchestrator is not up.
 *
 * This is not a simulation of the agent — it is a recording of one, and the UI
 * labels it as such. It still pauses for a real typed answer at the kitchen
 * step, because that pause is the thing worth showing.
 */
export class DemoRun {
  private cursor = 0;

  constructor(private readonly recorded: Trace) {}

  get pendingQuestion(): string | undefined {
    const step = this.recorded.steps[this.cursor];
    if (step?.tool !== "ask_kitchen") return undefined;
    return step.args?.question as string | undefined;
  }

  get finished(): boolean {
    return this.cursor >= this.recorded.steps.length;
  }

  /** Steps emitted so far. */
  get steps(): TraceStep[] {
    return this.recorded.steps.slice(0, this.cursor);
  }

  /** Advance one step, unless the next step needs a human first. */
  advance(): boolean {
    if (this.finished || this.pendingQuestion) return false;
    this.cursor += 1;
    return true;
  }

  /** Supply the human answer and consume the kitchen step. */
  answer(text: string): void {
    const step = this.recorded.steps[this.cursor];
    if (step?.tool !== "ask_kitchen") return;

    step.result = {
      ...step.result,
      answered_by: "chef",
      answer: text,
      answer_en: undefined,
    };
    this.cursor += 1;
  }

  /** The finished trace, with whatever the human actually typed folded in. */
  get trace(): Trace {
    return this.recorded;
  }
}
