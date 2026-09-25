"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type RefObject,
  type SetStateAction,
} from "react";
import {
  OrchestratorError,
  POLL_INTERVAL_MS,
  orchestrator,
  type AgentMode,
  type CaseRequest,
  type KitchenAnswer,
  type RunState,
} from "@/lib/orchestrator";
import {
  ReplayRun,
  RECORDED_CASES,
  closestRecording,
  type RecordedCase,
} from "@/lib/replays";
import type { Trace, TraceStep } from "@/lib/trace";

/** How long each recorded line takes to print on a replay. */
const REPLAY_STEP_MS = 700;
/** Polls that may fail in a row before a live run is reported as stopped. */
const MAX_POLL_FAILURES = 3;
const HTTP_SERVER_ERROR = 500;

export type RunPhase =
  "idle" | "running" | "awaiting_human" | "answering" | "complete" | "failed";

/** What produced the run on screen. */
export type RunSource =
  | { kind: "live"; mode: AgentMode }
  | { kind: "replay"; recording: RecordedCase };

export interface RunView {
  phase: RunPhase;
  source: RunSource | null;
  steps: TraceStep[];
  /** The finished trace; null until the run completes. */
  trace: Trace | null;
  pendingQuestion?: string;
  /** On a replay with a fixed kitchen answer, the step holding that answer. */
  recordedKitchenStep?: TraceStep;
  /** What the operator typed, when it differs from what a replay recorded. */
  typedRequest?: string;
  /** Something the operator should know that is not an error. */
  notice?: string;
  error?: string;
  /** True when the failure is best answered by watching a recording. */
  offerReplay?: boolean;
  /** True when the run may still be going on the server and polling can resume. */
  resumable?: boolean;
}

type SetView = Dispatch<SetStateAction<RunView>>;
type RecordedCaseId = keyof typeof RECORDED_CASES;

const IDLE: RunView = { phase: "idle", source: null, steps: [], trace: null };

const BUSY_MESSAGE =
  "The live agent is holding its maximum of open cases. Try again shortly, or watch a recorded run.";
const CONFLICT_NOTICE =
  "This case was already answered, possibly from another device. Showing that answer.";
const CLOSEST_NOTICE = "Live agent offline — showing the closest recorded run.";

/** Map a polled run onto the view, keeping the live source attached. */
function liveView(state: RunState, mode: AgentMode, notice?: string): RunView {
  return {
    phase: state.status,
    source: { kind: "live", mode },
    steps: state.trace.steps,
    trace: state.status === "complete" ? state.trace : null,
    pendingQuestion: state.pending_question,
    error: state.error,
    notice,
  };
}

/** The phase a replay is in at its cursor. */
function replayPhase(replay: ReplayRun): RunPhase {
  if (replay.pendingQuestion) return "awaiting_human";
  return replay.finished ? "complete" : "running";
}

/** Map a replay's cursor onto the view. */
function replayView(replay: ReplayRun, typedRequest?: string): RunView {
  return {
    phase: replayPhase(replay),
    source: { kind: "replay", recording: replay.recording },
    steps: replay.steps,
    trace: replay.finished ? replay.trace : null,
    pendingQuestion: replay.pendingQuestion,
    recordedKitchenStep: replay.interactive ? undefined : replay.kitchenStep,
    typedRequest,
    notice: typedRequest ? CLOSEST_NOTICE : undefined,
  };
}

/**
 * True when an error means the live agent itself is gone: the network failed,
 * or the host answered with a server error other than "every slot is busy".
 */
function isUnreachable(error: unknown): boolean {
  if (!(error instanceof OrchestratorError)) return true;
  if (error.status === null) return true;
  return error.status >= HTTP_SERVER_ERROR && !error.isBusy;
}

/** A readable message from anything a request threw. */
function messageOf(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

/**
 * Drives one case on the operator console, live or replayed.
 *
 * Live runs are polled while the agent works and left alone while it waits on
 * the kitchen. Replays print a real recording line by line. Either way the
 * kitchen step waits for a person.
 *
 * @param liveMode The live agent's mode, or null when only recordings can play.
 * @param onUnreachable Called when a live request finds the agent gone, so the
 *   connection can fall back to recordings instead of retrying a dead host.
 */
export function useVerifyRun(
  liveMode: AgentMode | null,
  onUnreachable: () => void,
) {
  const [view, setView] = useState<RunView>(IDLE);
  const runIdRef = useRef<string | null>(null);
  const replayRef = useRef<ReplayRun | null>(null);
  const unreachableRef = useRef(onUnreachable);
  useEffect(() => {
    unreachableRef.current = onUnreachable;
  }, [onUnreachable]);

  const startReplay = useCallback(
    (recording: RecordedCase, typedRequest?: string) => {
      runIdRef.current = null;
      const replay = new ReplayRun(recording);
      replayRef.current = replay;
      const differs = typedRequest && typedRequest !== recording.request;
      setView(replayView(replay, differs ? typedRequest : undefined));
    },
    [],
  );

  const startLive = useCallback(
    async (request: CaseRequest, mode: AgentMode) => {
      replayRef.current = null;
      runIdRef.current = null;
      setView({ ...IDLE, phase: "running", source: { kind: "live", mode } });
      try {
        runIdRef.current = await orchestrator.postCase(request);
      } catch (error) {
        const busy = error instanceof OrchestratorError && error.isBusy;
        if (isUnreachable(error)) unreachableRef.current();
        setView({
          ...IDLE,
          phase: "failed",
          source: { kind: "live", mode },
          error: busy
            ? BUSY_MESSAGE
            : messageOf(error, "live agent unreachable"),
          offerReplay: true,
        });
      }
    },
    [],
  );

  const start = useCallback(
    (request: CaseRequest, replayId?: RecordedCaseId) => {
      if (liveMode) {
        void startLive(request, liveMode);
        return;
      }
      const text = request.text ?? "";
      const recording = replayId
        ? RECORDED_CASES[replayId]
        : closestRecording(text);
      startReplay(recording, text);
    },
    [liveMode, startLive, startReplay],
  );

  usePolling(view, runIdRef, unreachableRef, setView);
  useReplayTicker(view, replayRef, setView);
  const answerKitchen = useKitchenAnswer(
    view,
    runIdRef,
    replayRef,
    unreachableRef,
    setView,
  );
  const reset = useCallback(() => {
    runIdRef.current = null;
    replayRef.current = null;
    setView(IDLE);
  }, []);

  /** Resume polling a live run that lost contact; the server may have kept it going. */
  const reconnect = useCallback(() => {
    if (!runIdRef.current) return;
    setView((current) =>
      current.source?.kind === "live"
        ? {
            ...current,
            phase: "running",
            error: undefined,
            offerReplay: false,
            resumable: false,
          }
        : current,
    );
  }, []);

  return { view, start, startReplay, answerKitchen, reset, reconnect };
}

/**
 * Poll a live run while the agent is working on it. A single failed poll is
 * forgiven; only `MAX_POLL_FAILURES` in a row stop the run, and even then it
 * can be resumed, because the case may still be going on the server.
 */
function usePolling(
  view: RunView,
  runIdRef: RefObject<string | null>,
  unreachableRef: RefObject<() => void>,
  setView: SetView,
): void {
  const polling =
    view.source?.kind === "live" &&
    (view.phase === "running" || view.phase === "answering");
  const mode = view.source?.kind === "live" ? view.source.mode : null;

  useEffect(() => {
    if (!polling || !mode) return;
    let failures = 0;
    let stopped = false;
    const timer = window.setInterval(async () => {
      const runId = runIdRef.current;
      if (!runId || stopped) return;
      try {
        const state = await orchestrator.getRun(runId);
        failures = 0;
        if (runIdRef.current !== runId) return;
        setView((current) => liveView(state, mode, current.notice));
      } catch (error) {
        failures += 1;
        if (failures < MAX_POLL_FAILURES || runIdRef.current !== runId) return;
        stopped = true;
        const unreachable = isUnreachable(error);
        if (unreachable) unreachableRef.current();
        setView((current) => ({
          ...current,
          phase: "failed",
          error: messageOf(error, "lost the live agent"),
          offerReplay: true,
          resumable: unreachable,
        }));
      }
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [polling, mode, runIdRef, unreachableRef, setView]);
}

/** Print the next recorded line while a replay is running. */
function useReplayTicker(
  view: RunView,
  replayRef: RefObject<ReplayRun | null>,
  setView: SetView,
): void {
  const ticking = view.source?.kind === "replay" && view.phase === "running";

  useEffect(() => {
    if (!ticking) return;
    const timer = window.setInterval(() => {
      const replay = replayRef.current;
      if (!replay) return;
      replay.advance();
      setView((current) => replayView(replay, current.typedRequest));
    }, REPLAY_STEP_MS);
    return () => window.clearInterval(timer);
  }, [ticking, replayRef, setView]);
}

/**
 * The kitchen's answer: sent to the live run, or used to pick the replay's
 * recorded branch. `null` continues a replay whose answer is fixed.
 */
function useKitchenAnswer(
  view: RunView,
  runIdRef: RefObject<string | null>,
  replayRef: RefObject<ReplayRun | null>,
  unreachableRef: RefObject<() => void>,
  setView: SetView,
) {
  const source = view.source;

  return useCallback(
    async (answer: KitchenAnswer | null) => {
      if (source?.kind === "replay") {
        const replay = replayRef.current;
        if (!replay) return;
        replay.answer(answer?.risk);
        setView((current) => replayView(replay, current.typedRequest));
        return;
      }
      const runId = runIdRef.current;
      if (!runId || !answer || source?.kind !== "live") return;
      setView((current) => ({ ...current, phase: "answering" }));
      await sendLiveAnswer(runId, answer, source.mode, setView, () =>
        unreachableRef.current(),
      );
    },
    [source, runIdRef, replayRef, unreachableRef, setView],
  );
}

/**
 * Post the answer; on 409 show whichever answer won instead of failing. When
 * the host is unreachable the answer may or may not have landed, so the run is
 * left resumable: polling again shows which.
 */
async function sendLiveAnswer(
  runId: string,
  answer: KitchenAnswer,
  mode: AgentMode,
  setView: SetView,
  onUnreachable: () => void,
): Promise<void> {
  try {
    setView(liveView(await orchestrator.postAnswer(runId, answer), mode));
  } catch (error) {
    if (error instanceof OrchestratorError && error.isConflict) {
      const state = await orchestrator.getRun(runId).catch(() => null);
      if (state) {
        setView(liveView(state, mode, CONFLICT_NOTICE));
        return;
      }
    }
    const unreachable = isUnreachable(error);
    if (unreachable) onUnreachable();
    setView((current) => ({
      ...current,
      phase: "failed",
      error: messageOf(error, "could not send the answer"),
      offerReplay: unreachable,
      resumable: unreachable,
    }));
  }
}
