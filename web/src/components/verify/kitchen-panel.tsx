"use client";

import { useEffect, useRef, useState } from "react";
import {
  ChefHat,
  CircleCheck,
  CircleHelp,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import type { KitchenAnswer } from "@/lib/orchestrator";
import { focusAndReveal } from "@/lib/reveal";
import type { KitchenRisk, TraceStep } from "@/lib/trace";

/** The question, focused and scrolled to once, when the ticket stops on it. */
function useFocusOnArrival() {
  const ref = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    focusAndReveal(ref.current);
  }, []);
  return ref;
}

interface RiskChoice {
  risk: KitchenRisk;
  label: string;
  hint: string;
  Icon: LucideIcon;
  className: string;
}

const RISK_CHOICES: RiskChoice[] = [
  {
    risk: "none",
    label: "No risk",
    hint: "No way it reaches the plate",
    Icon: CircleCheck,
    className: "border-verified text-verified-ink hover:bg-verified/10",
  },
  {
    risk: "risk",
    label: "Risk",
    hint: "It could reach the plate",
    Icon: TriangleAlert,
    className: "border-refuse text-refuse hover:bg-refuse/10",
  },
  {
    risk: "unsure",
    label: "Unsure",
    hint: "Cannot say for certain",
    Icon: CircleHelp,
    className: "border-confirm text-confirm-ink hover:bg-confirm/10",
  },
];

interface KitchenPanelProps {
  question: string;
  /** True while an answer is on its way to the live agent. */
  sending: boolean;
  /** True on a replay: each button plays the real recording for that answer. */
  replay: boolean;
  onAnswer: (answer: KitchenAnswer) => void;
}

/**
 * The one question the agent always puts to the kitchen. The chef taps one of
 * three answers; only "No risk" can ever lead to serving.
 */
export function KitchenPanel({
  question,
  sending,
  replay,
  onAnswer,
}: KitchenPanelProps) {
  const [note, setNote] = useState("");
  const questionRef = useFocusOnArrival();

  return (
    <div className="border-pen mt-6 border-l-2 pl-4">
      <p className="text-pen flex items-center gap-2 font-mono text-xs tracking-wider uppercase">
        <ChefHat className="size-4" aria-hidden="true" />
        The agent needs the kitchen
      </p>
      <p
        ref={questionRef}
        tabIndex={-1}
        className="text-ink mt-2 font-semibold outline-none"
      >
        {question}
      </p>
      <p className="text-ink-muted mt-1 text-xs leading-5">
        Walk it to the pass. Nothing is cleared until the chef answers.
      </p>

      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        {RISK_CHOICES.map((choice) => (
          <RiskButton
            key={choice.risk}
            choice={choice}
            disabled={sending}
            onClick={() =>
              onAnswer({ risk: choice.risk, note: note.trim() || undefined })
            }
          />
        ))}
      </div>

      {replay ? (
        <p className="text-ink-muted mt-3 text-xs leading-5">
          Recorded run: each button plays the real recording made with that
          answer.
        </p>
      ) : (
        <input
          value={note}
          onChange={(event) => setNote(event.target.value)}
          disabled={sending}
          maxLength={200}
          placeholder="Optional note from the chef"
          aria-label="Optional note from the chef"
          className="border-ink/30 text-ink placeholder:text-ink-muted focus-visible:border-pen mt-3 min-h-11 w-full border bg-transparent px-3 text-base outline-none"
        />
      )}

      {sending && (
        <p className="text-ink-muted mt-2 font-mono text-xs" role="status">
          Sending the kitchen&apos;s answer…
        </p>
      )}
    </div>
  );
}

/** One of the three answers, sized for a thumb at the pass. */
function RiskButton({
  choice,
  disabled,
  onClick,
}: {
  choice: RiskChoice;
  disabled: boolean;
  onClick: () => void;
}) {
  const { Icon } = choice;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`flex min-h-14 flex-col items-start justify-center border-2 px-3 py-2 text-left transition-colors disabled:opacity-40 ${choice.className}`}
    >
      <span className="flex items-center gap-2 font-mono text-sm font-semibold tracking-wider uppercase">
        <Icon className="size-4" aria-hidden="true" />
        {choice.label}
      </span>
      <span className="text-ink-muted text-xs">{choice.hint}</span>
    </button>
  );
}

/**
 * On a Gemma recording the kitchen's answer is fixed: show what the chef said
 * when it was recorded, and let the replay continue.
 */
export function RecordedKitchenAnswer({
  question,
  step,
  onContinue,
}: {
  question: string;
  step: TraceStep;
  onContinue: () => void;
}) {
  const answer =
    typeof step.result?.answer === "string" ? step.result.answer : "—";
  const questionRef = useFocusOnArrival();

  return (
    <div className="border-pen mt-6 border-l-2 pl-4">
      <p className="text-pen flex items-center gap-2 font-mono text-xs tracking-wider uppercase">
        <ChefHat className="size-4" aria-hidden="true" />
        The agent asked the kitchen
      </p>
      <p
        ref={questionRef}
        tabIndex={-1}
        className="text-ink mt-2 font-semibold outline-none"
      >
        {question}
      </p>
      <p className="text-ink-muted mt-3 text-xs">
        Recorded answer from the chef
      </p>
      <blockquote className="text-pen text-sm italic">“{answer}”</blockquote>
      <button
        type="button"
        onClick={onContinue}
        className="bg-ink text-paper mt-3 min-h-11 px-5 font-mono text-xs tracking-wider uppercase"
      >
        Continue the recording
      </button>
    </div>
  );
}
