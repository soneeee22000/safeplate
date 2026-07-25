"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from "react";
import {
  ENGINE_PRESENTATION,
  LANGUAGE_NAMES,
  VERDICT_PRESENTATION,
  countForcedSteps,
  countGemmaSteps,
  formatDuration,
  isRtl,
  type Engine,
  type Trace,
  type TraceStep,
} from "@/lib/trace";

const PRINT_INTERVAL_MS = 620;

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeToMotionPreference(onChange: () => void): () => void {
  const query = window.matchMedia(REDUCED_MOTION_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

/**
 * Reads the motion preference without tripping hydration: the server snapshot is
 * always false, so the first client render matches, and the store corrects it.
 */
function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribeToMotionPreference,
    () => window.matchMedia(REDUCED_MOTION_QUERY).matches,
    () => false,
  );
}

interface EvidenceTicketProps {
  cases: Trace[];
}

/**
 * The signature element: the agent's run rendered as the ticket a server
 * carries to the pass, printed line by line.
 *
 * Three inks are load-bearing, not decorative. Black is deterministic, blue is
 * Gemma, pen-blue is the human who answered. A judge can count Gemma's
 * contribution from across the room, and the same image answers "what about
 * hallucination?" without an argument.
 */
export function EvidenceTicket({ cases }: EvidenceTicketProps) {
  const [caseIndex, setCaseIndex] = useState(0);
  const [runNonce, setRunNonce] = useState(0);

  const selectCase = useCallback((index: number) => {
    setCaseIndex(index);
    setRunNonce((nonce) => nonce + 1);
  }, []);

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
      <article className="mx-auto w-full max-w-2xl">
        {/* Keyed so a replay resets the print sequence by remounting, rather
            than by resetting state from inside an effect. */}
        <TicketRun key={`${caseIndex}-${runNonce}`} trace={cases[caseIndex]} />

        <div className="mt-5 flex flex-wrap items-center gap-2">
          {cases.map((item, index) => (
            <button
              key={item.case_id}
              type="button"
              onClick={() => selectCase(index)}
              aria-pressed={index === caseIndex}
              className={`min-h-11 border px-4 font-mono text-xs tracking-wide uppercase transition-colors ${
                index === caseIndex
                  ? "border-paper bg-paper text-console"
                  : "border-console-line text-muted-foreground hover:border-paper/50 hover:text-paper"
              }`}
            >
              {VERDICT_PRESENTATION[item.verdict].label}
            </button>
          ))}
          <button
            type="button"
            onClick={() => selectCase(caseIndex)}
            className="border-console-line text-muted-foreground hover:border-paper/50 hover:text-paper min-h-11 border px-4 font-mono text-xs tracking-wide uppercase transition-colors"
          >
            Replay
          </button>
        </div>
      </article>

      <Legend />
    </div>
  );
}

function TicketRun({ trace }: { trace: Trace }) {
  const [printed, setPrinted] = useState(0);
  const [showOriginal, setShowOriginal] = useState(true);
  const reducedMotion = usePrefersReducedMotion();

  const stepCount = trace.steps.length;
  const complete = printed >= stepCount;

  useEffect(() => {
    const interval = reducedMotion ? 0 : PRINT_INTERVAL_MS;
    const timer = window.setInterval(() => {
      setPrinted((current) => (current >= stepCount ? current : current + 1));
    }, interval);

    return () => window.clearInterval(timer);
  }, [stepCount, reducedMotion]);

  const gemmaSteps = useMemo(() => countGemmaSteps(trace), [trace]);
  const forcedSteps = useMemo(() => countForcedSteps(trace), [trace]);
  const verdict = VERDICT_PRESENTATION[trace.verdict];
  const rtl = isRtl(trace.diner_language);
  const languageName =
    LANGUAGE_NAMES[trace.diner_language] ?? trace.diner_language;

  return (
    <>
      <div className="ticket-edge" aria-hidden="true" />

      <div className="bg-paper text-ink px-6 py-7 sm:px-9">
        <header className="border-ink/25 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 border-b pb-4">
          <div>
            <p className="font-mono text-[0.7rem] tracking-[0.2em] uppercase">
              {trace.restaurant}
            </p>
            <h3 className="font-display mt-1 text-xl font-semibold">
              {trace.dish}
            </h3>
          </div>
          <dl className="font-mono text-[0.7rem] leading-5">
            <div className="flex gap-2">
              <dt className="text-ink-muted">case</dt>
              <dd>{trace.case_id}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-ink-muted">asked about</dt>
              <dd className="font-semibold uppercase">{trace.allergen}</dd>
            </div>
          </dl>
        </header>

        <ol className="divide-ink/15 divide-y">
          {trace.steps.slice(0, printed).map((step) => (
            <TicketLine key={step.n} step={step} />
          ))}
        </ol>

        {!complete && (
          <p
            className="text-ink-muted font-mono text-xs"
            role="status"
            aria-live="polite"
          >
            printing step {printed + 1} of {stepCount}…
          </p>
        )}

        {complete && (
          <>
            <div
              className={`stamping mt-7 border-[3px] px-4 py-3 text-center ${verdict.className}`}
            >
              <p className="font-display text-2xl font-bold tracking-tight uppercase sm:text-3xl">
                {verdict.label}
              </p>
              <p className="text-ink-muted mt-1 text-xs">
                {verdict.consequence}
              </p>
            </div>

            <section className="mt-7">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <h4 className="font-mono text-[0.7rem] tracking-[0.2em] uppercase">
                  Told to the diner
                </h4>
                <div className="border-ink/25 flex border text-[0.7rem]">
                  <ToggleButton
                    active={showOriginal}
                    onClick={() => setShowOriginal(true)}
                  >
                    {languageName}
                  </ToggleButton>
                  <ToggleButton
                    active={!showOriginal}
                    onClick={() => setShowOriginal(false)}
                  >
                    English
                  </ToggleButton>
                </div>
              </div>
              <p
                dir={showOriginal && rtl ? "rtl" : "ltr"}
                lang={showOriginal ? trace.diner_language : "en"}
                className="border-gemma bg-paper-shade/60 border-l-2 px-4 py-3 text-sm leading-7 whitespace-pre-line"
              >
                {showOriginal ? trace.explanation : trace.explanation_en}
              </p>
              <p className="text-ink-muted mt-2 font-mono text-[0.7rem]">
                Composed by Gemma 4 in {languageName}. The verdict was fixed
                before it wrote a word.
              </p>
            </section>

            <footer className="border-ink/25 text-ink-muted mt-7 flex flex-wrap gap-x-6 gap-y-1 border-t pt-4 font-mono text-[0.7rem]">
              <span>{formatDuration(trace.total_ms)} total</span>
              <span>{stepCount} steps</span>
              <span>{gemmaSteps} by Gemma</span>
              <span>{forcedSteps} forced by the loop</span>
            </footer>
          </>
        )}
      </div>

      <div className="ticket-edge ticket-edge-bottom" aria-hidden="true" />
    </>
  );
}

function ToggleButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`min-h-11 px-3 font-mono uppercase transition-colors ${
        active ? "bg-ink text-paper" : "text-ink-muted hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

export function TicketLine({ step }: { step: TraceStep }) {
  const engine = ENGINE_PRESENTATION[step.engine];
  const isHuman = step.engine === "human";

  return (
    <li className="printing py-4">
      <div className="flex items-baseline gap-3">
        <span className="text-ink-muted font-mono text-xs tabular-nums">
          {String(step.n).padStart(2, "0")}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h5 className={`font-semibold ${engine.inkClass}`}>{step.title}</h5>
            <code className="text-ink-muted font-mono text-[0.7rem]">
              {step.tool}
            </code>
            <span
              className={`border px-1.5 font-mono text-[0.65rem] tracking-wider uppercase ${engine.borderClass} ${engine.inkClass}`}
            >
              {engine.label}
            </span>
            {step.forced && (
              <span
                className="border-refuse text-refuse border px-1.5 font-mono text-[0.65rem] tracking-wider uppercase"
                title={step.forced_by}
              >
                Forced
              </span>
            )}
            <span className="text-ink-muted ml-auto font-mono text-[0.7rem] tabular-nums">
              {formatDuration(step.duration_ms)}
            </span>
          </div>

          <p className="text-ink/80 mt-1 text-sm leading-6">{step.reasoning}</p>

          {step.forced_by && (
            <p className="text-refuse mt-1.5 font-mono text-[0.7rem]">
              orchestrator rule — {step.forced_by}
            </p>
          )}

          {isHuman && typeof step.result?.answer === "string" && (
            <blockquote className="border-pen text-pen mt-2 border-l-2 pl-3 text-sm italic">
              “{step.result.answer as string}”
              {typeof step.result?.answer_en === "string" && (
                <span className="text-ink-muted block text-xs not-italic">
                  {step.result.answer_en as string}
                </span>
              )}
            </blockquote>
          )}

          {step.note && (
            <p className="text-ink-muted mt-1.5 text-xs leading-5">
              {step.note}
            </p>
          )}
        </div>
      </div>
    </li>
  );
}

function Legend() {
  const order: Engine[] = ["gemma", "rule", "external", "human"];

  return (
    <aside className="border-console-line lg:sticky lg:top-8 border p-5">
      <h4 className="font-mono text-[0.7rem] tracking-[0.2em] uppercase">
        Three inks
      </h4>
      <p className="text-muted-foreground mt-2 text-sm leading-6">
        Every line on the ticket says which part of the system produced it. The
        reasoning is learned. The safety call is not.
      </p>

      <dl className="mt-5 space-y-4">
        {order.map((engine) => {
          const presentation = ENGINE_PRESENTATION[engine];
          const swatch = {
            rule: "bg-paper",
            gemma: "bg-gemma-lit",
            external: "bg-confirm-lit",
            human: "bg-pen-lit",
          }[engine];

          return (
            <div key={engine} className="flex gap-3">
              <span
                className={`mt-1.5 h-2.5 w-2.5 shrink-0 ${swatch}`}
                aria-hidden="true"
              />
              <div>
                <dt className="font-mono text-xs tracking-wider uppercase">
                  {presentation.label}
                </dt>
                <dd className="text-muted-foreground text-sm leading-6">
                  {presentation.description}
                </dd>
              </div>
            </div>
          );
        })}
      </dl>

      <div className="border-console-line mt-5 border-t pt-4">
        <p className="text-refuse font-mono text-xs tracking-wider uppercase">
          Forced
        </p>
        <p className="text-muted-foreground mt-1 text-sm leading-6">
          The orchestrator compelled that call. Gemma 4 E2B measurably does not
          escalate on its own, so the loop never leaves it to chance.
        </p>
      </div>
    </aside>
  );
}
