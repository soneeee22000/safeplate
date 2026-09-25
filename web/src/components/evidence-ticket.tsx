import {
  ENGINE_PRESENTATION,
  formatDuration,
  type TraceStep,
} from "@/lib/trace";

/**
 * One printed line of a ticket: the step, which engine produced it, and
 * whether code forced it. The engine label comes from the step itself, so a
 * rules-mode line is never credited to Gemma.
 */
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
            <code className="text-ink-muted font-mono text-xs">
              {step.tool}
            </code>
            <span
              className={`border px-1.5 font-mono text-xs tracking-wider uppercase ${engine.borderClass} ${engine.inkClass}`}
            >
              {engine.label}
            </span>
            {step.forced && (
              <span
                className="border-refuse text-refuse border px-1.5 font-mono text-xs tracking-wider uppercase"
                title={step.forced_by}
              >
                Forced
              </span>
            )}
            <span className="text-ink-muted ml-auto font-mono text-xs tabular-nums">
              {formatDuration(step.duration_ms)}
            </span>
          </div>

          <p className="text-ink/80 mt-1 text-sm leading-6">{step.reasoning}</p>

          {step.forced_by && (
            <p className="text-refuse mt-1.5 font-mono text-xs">
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
