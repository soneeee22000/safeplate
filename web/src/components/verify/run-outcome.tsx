"use client";

import { useState, type ReactNode } from "react";
import {
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  type LucideIcon,
} from "lucide-react";
import {
  LANGUAGE_NAMES,
  VERDICT_PRESENTATION,
  countForcedSteps,
  formatDuration,
  isRtl,
  type Trace,
  type Verdict,
} from "@/lib/trace";
import {
  STEP_KINDS,
  stepKind,
  type StepKind,
} from "@/components/verify/trace-step";

const VERDICT_ICONS: Record<Verdict, LucideIcon> = {
  do_not_serve: ShieldX,
  needs_confirmation: ShieldAlert,
  verified: ShieldCheck,
};

/** The stamp: what the restaurant may do, decided by code, never by the model. */
export function VerdictStamp({ verdict }: { verdict: Verdict }) {
  const presentation = VERDICT_PRESENTATION[verdict];
  const Icon = VERDICT_ICONS[verdict];

  return (
    <div
      className={`stamping mt-7 border-[3px] px-4 py-3 text-center ${presentation.className}`}
    >
      <p className="font-display flex items-center justify-center gap-2 text-2xl font-bold tracking-tight uppercase sm:text-3xl">
        <Icon className="size-7 shrink-0" aria-hidden="true" />
        {presentation.label}
      </p>
      <p className="text-ink-muted mt-1 text-xs">{presentation.consequence}</p>
    </div>
  );
}

/** Verdict, the reply to show the diner, and who did what. */
export function RunOutcome({ trace }: { trace: Trace }) {
  return (
    <>
      <VerdictStamp verdict={trace.verdict} />
      <DinerReply trace={trace} />
      <RunTally trace={trace} />
    </>
  );
}

/** The reply in the diner's language, with an English toggle for staff. */
function DinerReply({ trace }: { trace: Trace }) {
  const [original, setOriginal] = useState(true);
  const languageName =
    LANGUAGE_NAMES[trace.diner_language] ?? trace.diner_language.toUpperCase();
  const sameText = trace.explanation === trace.explanation_en;
  const text = original ? trace.explanation : trace.explanation_en;

  return (
    <section className="mt-7">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-mono text-xs tracking-[0.2em] uppercase">
          Show the diner
        </h3>
        {!sameText && (
          <div className="border-ink/25 flex border text-xs">
            <ToggleButton active={original} onClick={() => setOriginal(true)}>
              {languageName}
            </ToggleButton>
            <ToggleButton active={!original} onClick={() => setOriginal(false)}>
              English
            </ToggleButton>
          </div>
        )}
      </div>
      <p
        dir={original && isRtl(trace.diner_language) ? "rtl" : "ltr"}
        lang={original ? trace.diner_language : "en"}
        className="border-ink bg-paper-shade/60 border-l-2 px-4 py-3 text-sm leading-7 whitespace-pre-line"
      >
        {text}
      </p>
    </section>
  );
}

/** A two-state toggle button. */
function ToggleButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`min-h-11 px-3 font-mono uppercase ${
        active ? "bg-ink text-paper" : "text-ink-muted"
      }`}
    >
      {children}
    </button>
  );
}

/** Counts of steps per producer, so the division of labour is a number. */
function RunTally({ trace }: { trace: Trace }) {
  const counts = trace.steps.reduce<Record<StepKind, number>>(
    (tally, step) => {
      tally[stepKind(step)] += 1;
      return tally;
    },
    { model: 0, code: 0, human: 0, serpapi: 0 },
  );
  const kinds: StepKind[] = ["model", "code", "serpapi", "human"];

  return (
    <footer className="border-ink/25 text-ink-muted mt-7 flex flex-wrap gap-x-6 gap-y-1 border-t pt-4 font-mono text-xs">
      <span>{formatDuration(trace.total_ms)} total</span>
      {kinds.map((kind) => (
        <span key={kind}>
          {counts[kind]} {STEP_KINDS[kind].label.toLowerCase()}
        </span>
      ))}
      <span>{countForcedSteps(trace)} forced</span>
    </footer>
  );
}
