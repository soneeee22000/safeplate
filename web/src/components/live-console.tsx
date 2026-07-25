"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CaseForm } from "@/components/case-form";
import { TicketLine } from "@/components/evidence-ticket";
import recordedCase from "@/data/trace-refusal.json";
import {
  DemoRun,
  POLL_INTERVAL_MS,
  orchestrator,
  probeOrchestrator,
  type CaseRequest,
} from "@/lib/orchestrator";
import {
  LANGUAGE_NAMES,
  VERDICT_PRESENTATION,
  countForcedSteps,
  countGemmaSteps,
  formatDuration,
  isRtl,
  type Trace,
  type TraceStep,
} from "@/lib/trace";

type ConsoleStatus =
  "idle" | "running" | "awaiting_human" | "complete" | "failed";

interface RunView {
  status: ConsoleStatus;
  steps: TraceStep[];
  trace: Trace | null;
  pendingQuestion?: string;
  error?: string;
}

const IDLE_VIEW: RunView = { status: "idle", steps: [], trace: null };

/**
 * The operator screen. One server, one device: open a case, watch the agent
 * work, answer the question it puts to the kitchen, read the verdict.
 *
 * Runs against the FastAPI orchestrator when it is up, and replays a recorded
 * case when it is not — so the interface is demonstrable before the loop lands.
 */
export function LiveConsole() {
  const [view, setView] = useState<RunView>(IDLE_VIEW);
  const [liveBackend, setLiveBackend] = useState(false);
  const [answer, setAnswer] = useState("");

  const runIdRef = useRef<string | null>(null);
  const demoRef = useRef<DemoRun | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    probeOrchestrator(controller.signal)
      .then(setLiveBackend)
      .catch(() => {});
    return () => controller.abort();
  }, []);

  const startCase = useCallback(
    async (request: CaseRequest) => {
      setAnswer("");
      setView({ status: "running", steps: [], trace: null });

      if (!liveBackend) {
        demoRef.current = new DemoRun(
          JSON.parse(JSON.stringify(recordedCase)) as Trace,
        );
        return;
      }

      try {
        runIdRef.current = await orchestrator.postCase(request);
      } catch (error) {
        setView({
          status: "failed",
          steps: [],
          trace: null,
          error:
            error instanceof Error ? error.message : "orchestrator unreachable",
        });
      }
    },
    [liveBackend],
  );

  // One ticker drives both modes: it advances the recording, or polls the loop.
  useEffect(() => {
    if (view.status !== "running") return;

    const timer = window.setInterval(async () => {
      const demo = demoRef.current;

      if (!liveBackend && demo) {
        demo.advance();
        const question = demo.pendingQuestion;
        setView({
          status: question
            ? "awaiting_human"
            : demo.finished
              ? "complete"
              : "running",
          steps: demo.steps,
          trace: demo.finished ? demo.trace : null,
          pendingQuestion: question,
        });
        return;
      }

      const runId = runIdRef.current;
      if (!runId) return;

      try {
        const state = await orchestrator.getRun(runId);
        setView({
          status:
            state.status === "failed"
              ? "failed"
              : state.status === "complete"
                ? "complete"
                : state.status === "awaiting_human"
                  ? "awaiting_human"
                  : "running",
          steps: state.trace.steps,
          trace: state.status === "complete" ? state.trace : null,
          pendingQuestion: state.pending_question,
          error: state.error,
        });
      } catch (error) {
        setView((current) => ({
          ...current,
          status: "failed",
          error:
            error instanceof Error ? error.message : "lost the orchestrator",
        }));
      }
    }, POLL_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [view.status, liveBackend]);

  const submitAnswer = useCallback(async () => {
    const text = answer.trim();
    if (!text) return;
    setAnswer("");

    const demo = demoRef.current;
    if (!liveBackend && demo) {
      demo.answer(text);
      setView({
        status: demo.finished ? "complete" : "running",
        steps: demo.steps,
        trace: demo.finished ? demo.trace : null,
      });
      return;
    }

    const runId = runIdRef.current;
    if (!runId) return;

    try {
      await orchestrator.postAnswer(runId, text);
      setView((current) => ({
        ...current,
        status: "running",
        pendingQuestion: undefined,
      }));
    } catch (error) {
      setView((current) => ({
        ...current,
        status: "failed",
        error:
          error instanceof Error ? error.message : "could not send the answer",
      }));
    }
  }, [answer, liveBackend]);

  const busy = view.status === "running" || view.status === "awaiting_human";

  return (
    <div className="grid gap-8 lg:grid-cols-[22rem_minmax(0,1fr)] lg:items-start">
      <div className="space-y-4 lg:sticky lg:top-24">
        <ModeBanner live={liveBackend} />
        <CaseForm
          onSubmit={startCase}
          disabled={busy}
          liveBackend={liveBackend}
        />
      </div>

      <section aria-live="polite">
        {view.status === "idle" ? (
          <EmptyState />
        ) : (
          <article className="mx-auto w-full max-w-2xl">
            <div className="ticket-edge" aria-hidden="true" />
            <div className="bg-paper text-ink px-6 py-7 sm:px-9">
              <ol className="divide-ink/15 divide-y">
                {view.steps.map((step) => (
                  <TicketLine key={step.n} step={step} />
                ))}
              </ol>

              {view.status === "running" && <Working />}

              {view.status === "awaiting_human" && view.pendingQuestion && (
                <KitchenPrompt
                  question={view.pendingQuestion}
                  value={answer}
                  onChange={setAnswer}
                  onSubmit={submitAnswer}
                />
              )}

              {view.status === "failed" && (
                <p className="text-refuse border-refuse mt-5 border-l-2 pl-3 font-mono text-sm">
                  The run stopped: {view.error ?? "unknown error"}. Nothing is
                  cleared on a failed run.
                </p>
              )}

              {view.status === "complete" && view.trace && (
                <Outcome trace={view.trace} />
              )}
            </div>
            <div
              className="ticket-edge ticket-edge-bottom"
              aria-hidden="true"
            />
          </article>
        )}
      </section>
    </div>
  );
}

function ModeBanner({ live }: { live: boolean }) {
  return (
    <p
      className={`border px-3 py-2 font-mono text-xs leading-5 ${
        live
          ? "border-verified text-verified"
          : "border-confirm text-confirm-lit"
      }`}
    >
      {live
        ? "Live — Gemma 4 E2B, Tesseract and SerpApi on this machine."
        : "Demo mode — replaying a recorded case. The kitchen question is still yours to answer."}
    </p>
  );
}

function EmptyState() {
  return (
    <div className="border-console-line flex min-h-80 items-center justify-center border border-dashed p-10">
      <p className="text-muted-foreground max-w-sm text-center text-sm leading-6">
        Open a case to start. The agent reads the label, checks it against the
        EU-14 table, searches the manufacturer&apos;s declaration, and asks the
        kitchen what no label can tell it.
      </p>
    </div>
  );
}

function Working() {
  return (
    <p className="text-ink-muted mt-5 font-mono text-xs" role="status">
      agent working…
    </p>
  );
}

function KitchenPrompt({
  question,
  value,
  onChange,
  onSubmit,
}: {
  question: string;
  value: string;
  onChange: (next: string) => void;
  onSubmit: () => void;
}) {
  return (
    <div className="border-pen mt-6 border-l-2 pl-4">
      <p className="text-pen font-mono text-[0.7rem] tracking-wider uppercase">
        The agent needs the kitchen
      </p>
      <p className="text-ink mt-2 font-semibold">{question}</p>
      <p className="text-ink-muted mt-1 text-xs leading-5">
        Walk it to the pass. Nothing is cleared until this is answered.
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") onSubmit();
          }}
          placeholder="What the chef said"
          aria-label="The kitchen's answer"
          className="border-ink/30 text-ink placeholder:text-ink-muted min-h-12 min-w-0 flex-1 border bg-transparent px-3 text-base outline-none focus-visible:border-pen"
        />
        <button
          type="button"
          onClick={onSubmit}
          className="bg-ink text-paper min-h-12 px-5 font-mono text-xs tracking-wider uppercase"
        >
          Send
        </button>
      </div>
    </div>
  );
}

function Outcome({ trace }: { trace: Trace }) {
  const [showOriginal, setShowOriginal] = useState(true);
  const verdict = VERDICT_PRESENTATION[trace.verdict];
  const languageName =
    LANGUAGE_NAMES[trace.diner_language] ?? trace.diner_language;
  const rtl = isRtl(trace.diner_language);

  return (
    <>
      <div
        className={`stamping mt-7 border-[3px] px-4 py-3 text-center ${verdict.className}`}
      >
        <p className="font-display text-2xl font-bold tracking-tight uppercase sm:text-3xl">
          {verdict.label}
        </p>
        <p className="text-ink-muted mt-1 text-xs">{verdict.consequence}</p>
      </div>

      <section className="mt-7">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h4 className="font-mono text-[0.7rem] tracking-[0.2em] uppercase">
            Show the diner
          </h4>
          <div className="border-ink/25 flex border text-[0.7rem]">
            <button
              type="button"
              onClick={() => setShowOriginal(true)}
              aria-pressed={showOriginal}
              className={`min-h-11 px-3 font-mono uppercase ${
                showOriginal ? "bg-ink text-paper" : "text-ink-muted"
              }`}
            >
              {languageName}
            </button>
            <button
              type="button"
              onClick={() => setShowOriginal(false)}
              aria-pressed={!showOriginal}
              className={`min-h-11 px-3 font-mono uppercase ${
                !showOriginal ? "bg-ink text-paper" : "text-ink-muted"
              }`}
            >
              English
            </button>
          </div>
        </div>
        <p
          dir={showOriginal && rtl ? "rtl" : "ltr"}
          lang={showOriginal ? trace.diner_language : "en"}
          className="border-gemma bg-paper-shade/60 border-l-2 px-4 py-3 text-sm leading-7 whitespace-pre-line"
        >
          {showOriginal ? trace.explanation : trace.explanation_en}
        </p>
      </section>

      <footer className="border-ink/25 text-ink-muted mt-7 flex flex-wrap gap-x-6 gap-y-1 border-t pt-4 font-mono text-[0.7rem]">
        <span>{formatDuration(trace.total_ms)} total</span>
        <span>{trace.steps.length} steps</span>
        <span>{countGemmaSteps(trace)} by Gemma</span>
        <span>{countForcedSteps(trace)} forced by the loop</span>
      </footer>
    </>
  );
}
