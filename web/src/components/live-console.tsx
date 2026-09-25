"use client";

import { useCallback, useRef } from "react";
import { History, Radio, RotateCcw } from "lucide-react";
import { CasePicker } from "@/components/verify/case-picker";
import {
  KitchenPanel,
  RecordedKitchenAnswer,
} from "@/components/verify/kitchen-panel";
import { ModeBanner, recordedBadge } from "@/components/verify/mode-banner";
import { RunOutcome } from "@/components/verify/run-outcome";
import { KindChip, TraceStepLine } from "@/components/verify/trace-step";
import type { AgentMode } from "@/lib/orchestrator";
import {
  RECORDED_CASES,
  closestRecording,
  type RecordedCase,
} from "@/lib/replays";
import { revealWhenStacked } from "@/lib/reveal";
import { useAgentConnection } from "@/lib/use-agent-connection";
import { useVerifyRun, type RunView } from "@/lib/use-verify-run";

/**
 * The operator screen: one server, one phone. Pick or type what the diner
 * asked, watch the agent work, answer the kitchen, read the verdict.
 *
 * Runs against the live agent when it answers, and plays real recorded runs
 * when it does not, always saying which.
 */
export function LiveConsole() {
  const { connection, skip, retry, markOffline } = useAgentConnection();
  const liveMode: AgentMode | null =
    connection.kind === "live" ? connection.mode : null;
  const waiting =
    connection.kind === "connecting" || connection.kind === "waking";
  const { view, start, startReplay, answerKitchen, reset, reconnect } =
    useVerifyRun(liveMode, markOffline);
  const traceRef = useRef<HTMLElement>(null);

  const checking = view.phase === "running" || view.phase === "answering";
  const replaying =
    view.source?.kind === "replay" ? view.source.recording : null;

  /** On a phone the trace is below the picker: take the viewer to it. */
  const reveal = useCallback(() => {
    window.requestAnimationFrame(() => revealWhenStacked(traceRef.current));
  }, []);

  const replay = useCallback(
    (recording: RecordedCase) => {
      startReplay(recording);
      reveal();
    },
    [startReplay, reveal],
  );

  return (
    <div className="grid gap-8 lg:grid-cols-[24rem_minmax(0,1fr)] lg:items-start">
      <div className="flex flex-col gap-4 lg:sticky lg:top-24">
        <ModeBanner
          connection={connection}
          replayRecordedWith={replaying?.recordedWith ?? null}
          onSkip={skip}
          onRetry={retry}
          onWatchGemma={() => replay(RECORDED_CASES["bolognese-celery"])}
        />
        {view.phase === "awaiting_human" && <PendingKitchen onReset={reset} />}
        <CasePicker
          disabled={waiting || checking}
          checking={checking}
          liveMode={liveMode}
          onPreset={(preset) => {
            start({ text: preset.text }, preset.replayId);
            reveal();
          }}
          onRequest={(request) => {
            start(request);
            reveal();
          }}
        />
      </div>

      <section
        ref={traceRef}
        aria-live="polite"
        aria-label="Agent trace"
        className="scroll-mt-20"
      >
        {view.phase === "idle" ? (
          <EmptyState />
        ) : (
          <Ticket
            view={view}
            onAnswer={answerKitchen}
            onReplay={() => startReplay(closestFor(view))}
            onReconnect={() => {
              retry();
              reconnect();
            }}
          />
        )}
      </section>
    </div>
  );
}

/** A case is parked on the kitchen: say so, and let the operator move on. */
function PendingKitchen({ onReset }: { onReset: () => void }) {
  return (
    <div className="border-pen-lit border px-3 py-3" role="status">
      <p className="text-pen-lit font-mono text-xs leading-5 font-semibold">
        Waiting on the kitchen
      </p>
      <p className="text-muted-foreground mt-1.5 text-xs leading-5">
        The ticket needs the chef&apos;s answer. Picking another case drops this
        one.
      </p>
      <button
        type="button"
        onClick={onReset}
        className="border-console-line text-paper hover:border-paper mt-2 flex min-h-11 items-center gap-2 border px-3 font-mono text-xs tracking-wider uppercase"
      >
        <RotateCcw className="size-4" aria-hidden="true" />
        Start a new case
      </button>
    </div>
  );
}

/** The recording closest to a failed live run, for the fallback button. */
function closestFor(view: RunView) {
  return view.source?.kind === "replay"
    ? view.source.recording
    : pickClosest(view.steps[0]?.result?.utterance);
}

/** Closest recording to whatever utterance the failed run heard. */
function pickClosest(utterance: unknown) {
  return closestRecording(typeof utterance === "string" ? utterance : "");
}

type TicketActions = {
  onAnswer: ReturnType<typeof useVerifyRun>["answerKitchen"];
  onReplay: () => void;
  onReconnect: () => void;
};

/** The paper ticket: source badge, printed steps, kitchen, verdict. */
function Ticket({
  view,
  onAnswer,
  onReplay,
  onReconnect,
}: { view: RunView } & TicketActions) {
  return (
    <article className="mx-auto w-full max-w-2xl">
      <div className="ticket-edge" aria-hidden="true" />
      <div className="bg-paper text-ink px-5 py-6 sm:px-9 sm:py-7">
        <SourceBadge view={view} />
        <ol className="divide-ink/15 divide-y">
          {view.steps.map((step) => (
            <TraceStepLine key={step.n} step={step} />
          ))}
        </ol>
        <TicketTail
          view={view}
          onAnswer={onAnswer}
          onReplay={onReplay}
          onReconnect={onReconnect}
        />
      </div>
      <div className="ticket-edge ticket-edge-bottom" aria-hidden="true" />
    </article>
  );
}

/** Whatever follows the printed steps for the phase the run is in. */
function TicketTail({
  view,
  onAnswer,
  onReplay,
  onReconnect,
}: { view: RunView } & TicketActions) {
  if (view.phase === "running") return <Working />;
  if (view.phase === "failed")
    return (
      <Failure view={view} onReplay={onReplay} onReconnect={onReconnect} />
    );
  if (view.phase === "complete" && view.trace)
    return <RunOutcome trace={view.trace} />;
  if (!view.pendingQuestion) return <Working />;
  if (view.recordedKitchenStep) {
    return (
      <RecordedKitchenAnswer
        question={view.pendingQuestion}
        step={view.recordedKitchenStep}
        onContinue={() => void onAnswer(null)}
      />
    );
  }
  return (
    <KitchenPanel
      question={view.pendingQuestion}
      sending={view.phase === "answering"}
      replay={view.source?.kind === "replay"}
      onAnswer={(answer) => void onAnswer(answer)}
    />
  );
}

/** Says who is producing this ticket: the live agent or a named recording. */
function SourceBadge({ view }: { view: RunView }) {
  const source = view.source;
  if (!source) return null;
  const live = source.kind === "live";
  const label = live
    ? source.mode === "gemma"
      ? "Live · Gemma 4 E2B"
      : "Live · rules mode"
    : recordedBadge(source.recording.recordedWith);
  const Icon = live ? Radio : History;

  return (
    <header className="border-ink/20 mb-2 border-b pb-3">
      <p
        className={`inline-flex items-center gap-1.5 border-2 px-2 py-1 font-mono text-xs font-semibold tracking-wider uppercase ${
          live
            ? "border-verified text-verified-ink"
            : "border-confirm text-confirm-ink"
        }`}
      >
        <Icon className="size-3.5" aria-hidden="true" />
        {label}
      </p>
      {source.kind === "replay" && <ReplayContext view={view} />}
      {view.notice && source.kind === "live" && (
        <p className="text-ink-muted mt-2 text-xs leading-5">{view.notice}</p>
      )}
    </header>
  );
}

/** For a replay: what was recorded, and what was typed if it differs. */
function ReplayContext({ view }: { view: RunView }) {
  if (view.source?.kind !== "replay") return null;
  const recording = view.source.recording;

  return (
    <div className="mt-2 text-xs leading-5">
      {view.notice && (
        <p className="text-confirm-ink font-mono font-semibold">{view.notice}</p>
      )}
      {view.typedRequest && (
        <p className="text-ink-muted">
          You asked: <span className="text-ink">“{view.typedRequest}”</span>
        </p>
      )}
      <p className="text-ink-muted">
        Recorded request:{" "}
        <span className="text-ink">“{recording.request}”</span>
      </p>
    </div>
  );
}

/**
 * A live run that stopped: nothing is cleared. If the case may still be going
 * on the server it can be picked up again; a recording is always on offer.
 */
function Failure({
  view,
  onReplay,
  onReconnect,
}: {
  view: RunView;
  onReplay: () => void;
  onReconnect: () => void;
}) {
  return (
    <div className="border-refuse mt-5 border-l-2 pl-3">
      <p className="text-refuse font-mono text-sm">
        The run stopped: {view.error ?? "unknown error"}. Nothing is cleared on
        a failed run.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {view.resumable && (
          <button
            type="button"
            onClick={onReconnect}
            className="border-ink text-ink min-h-11 border px-4 font-mono text-xs tracking-wider uppercase"
          >
            Reconnect to this case
          </button>
        )}
        {view.offerReplay && (
          <button
            type="button"
            onClick={onReplay}
            className="bg-ink text-paper min-h-11 px-4 font-mono text-xs tracking-wider uppercase"
          >
            Watch the closest recorded run
          </button>
        )}
      </div>
    </div>
  );
}

/** Before any case: what the four chips mean. */
function EmptyState() {
  return (
    <div className="border-console-line flex min-h-80 flex-col justify-center gap-5 border border-dashed p-6 sm:p-10">
      <p className="text-muted-foreground max-w-md text-sm leading-6">
        Pick a case or type what the diner asked. Every line of the ticket says
        which part of the system produced it. The model only hears and speaks;
        code decides, and the kitchen answers what no document can.
      </p>
      <ul className="flex flex-wrap gap-2">
        {(["model", "code", "serpapi", "human"] as const).map((kind) => (
          <li key={kind}>
            <KindChip kind={kind} />
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The agent is working on the next line. */
function Working() {
  return (
    <p className="text-ink-muted mt-5 font-mono text-xs" role="status">
      Agent working…
    </p>
  );
}
