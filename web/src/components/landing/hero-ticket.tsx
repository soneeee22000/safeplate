import type { CSSProperties } from "react";
import padThaiRecording from "@/data/trace-padthai-rules.json";
import { recordedBadge } from "@/components/verify/mode-banner";
import { VerdictStamp } from "@/components/verify/run-outcome";
import { ENGINE_PRESENTATION, type Trace } from "@/lib/trace";

const TRACE = padThaiRecording as unknown as Trace;
const REQUEST =
  "I'm allergic to fish — can I have the pad thai without fish sauce?";

/** Gap between printed lines on first paint, in milliseconds. */
const LINE_DELAY_MS = 180;
/** Pause after the last line before the stamp lands, in milliseconds. */
const STAMP_PAUSE_MS = 260;

/** First sentence of the reply, which is all the hero has room for. */
function firstSentences(text: string, count: number): string {
  return text
    .split(/(?<=\.)\s+/)
    .slice(0, count)
    .join(" ");
}

/**
 * The hero's paper ticket: a real recorded run (pad thai, fish allergy) printed
 * line by line once, then stamped. It is the page's one piece of motion.
 */
export function HeroTicket() {
  const stampDelay = TRACE.steps.length * LINE_DELAY_MS + STAMP_PAUSE_MS;

  return (
    <figure className="mx-auto w-full max-w-md lg:rotate-1">
      <div className="ticket-edge" aria-hidden="true" />
      <div className="bg-paper text-ink px-5 py-6 sm:px-7">
        <header className="border-ink/25 border-b pb-4">
          <p className="text-ink-muted font-mono text-xs">
            {recordedBadge("rules")}
          </p>
          <p className="font-display mt-2 text-xl font-semibold">
            {TRACE.dish}
          </p>
          <blockquote className="text-ink/80 mt-2 text-sm leading-6">
            &ldquo;{REQUEST}&rdquo;
          </blockquote>
        </header>

        <ol className="divide-ink/15 divide-y">
          {TRACE.steps.map((step, index) => (
            <TicketRow
              key={step.n}
              title={step.title}
              engine={step.engine}
              forced={step.forced}
              delayMs={index * LINE_DELAY_MS}
            />
          ))}
        </ol>

        <div
          className="[&_.stamping]:[animation-delay:var(--stamp-delay)]"
          style={{ "--stamp-delay": `${stampDelay}ms` } as CSSProperties}
        >
          <VerdictStamp verdict={TRACE.verdict} />
        </div>

        <p className="border-ink bg-paper-shade/60 mt-5 border-l-2 px-3 py-2 text-sm leading-6">
          {firstSentences(TRACE.explanation, 2)}
        </p>
      </div>
      <div className="ticket-edge ticket-edge-bottom" aria-hidden="true" />
      <figcaption className="text-muted-foreground mt-3 text-center text-xs">
        The hosted agent&apos;s rules mode, recorded. {TRACE.total_ms} ms end to
        end.
      </figcaption>
    </figure>
  );
}

interface TicketRowProps {
  title: string;
  engine: Trace["steps"][number]["engine"];
  forced: boolean;
  delayMs: number;
}

/** One printed line: what happened, who produced it, and whether it was forced. */
function TicketRow({ title, engine, forced, delayMs }: TicketRowProps) {
  const presentation = ENGINE_PRESENTATION[engine];

  return (
    <li
      className="printing flex flex-wrap items-baseline gap-x-2 gap-y-1 py-2.5"
      style={{ animationDelay: `${delayMs}ms` }}
    >
      <span className={`text-sm font-semibold ${presentation.inkClass}`}>
        {title}
      </span>
      <span
        className={`border px-1.5 font-mono text-xs ${presentation.borderClass} ${presentation.inkClass}`}
      >
        {presentation.label}
      </span>
      {forced && (
        <span className="border-refuse text-refuse border px-1.5 font-mono text-xs">
          Forced
        </span>
      )}
    </li>
  );
}
