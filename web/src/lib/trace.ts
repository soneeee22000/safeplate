/**
 * The frozen contract between the agent loop and every surface that renders it.
 *
 * The orchestrator emits this shape; the UI never computes a verdict, it only
 * displays one. Keep this file in sync with `fixtures/*.json` at the repo root —
 * both the Python loop and this app validate against the same schema.
 */

/** Which part of the system produced a step. Drives the ink it prints in. */
export type Engine = "gemma" | "rule" | "external" | "human";

/** Terminal states. There is no "probably safe". */
export type Verdict = "verified" | "needs_confirmation" | "do_not_serve";

export interface TraceStep {
  /** 1-indexed position in the run. */
  n: number;
  tool: string;
  engine: Engine;
  /** Short human-readable label for the step. */
  title: string;
  /** Why this call was made — shown under the title. */
  reasoning: string;
  /** True when the orchestrator compelled the call rather than the model choosing it. */
  forced: boolean;
  /** The rule that compelled it, present whenever `forced` is true. */
  forced_by?: string;
  args?: Record<string, unknown>;
  result?: Record<string, unknown>;
  duration_ms: number;
  /** Optional annotation surfaced beneath the step. */
  note?: string;
}

export interface Evidence {
  source: string;
  url: string | null;
  text: string;
}

export interface Trace {
  case_id: string;
  restaurant: string;
  dish: string;
  /** The allergen the diner asked about. */
  allergen: string;
  /** ISO code — Gemma composes `explanation` in this language. */
  diner_language: string;
  verdict: Verdict;
  /** Absent on live runs — the orchestrator reports elapsed time, not wall clock. */
  started_at?: string;
  total_ms: number;
  steps: TraceStep[];
  evidence: Evidence[];
  /** Final text in the diner's language. */
  explanation: string;
  /** The same text in English, for judges and for the staff-facing view. */
  explanation_en: string;
}

interface VerdictPresentation {
  label: string;
  /** One line explaining what the verdict commits the restaurant to. */
  consequence: string;
  className: string;
}

export const VERDICT_PRESENTATION: Record<Verdict, VerdictPresentation> = {
  verified: {
    label: "Safe to serve",
    consequence:
      "Every ingredient resolved and the kitchen ruled out cross-contact.",
    className: "text-verified border-verified",
  },
  needs_confirmation: {
    label: "Needs confirmation",
    consequence: "Something is still unanswered. Do not serve until it is.",
    className: "text-confirm border-confirm",
  },
  do_not_serve: {
    label: "Do not serve",
    consequence:
      "A risk was confirmed, or the evidence could not be reconciled.",
    className: "text-refuse border-refuse",
  },
};

interface EnginePresentation {
  /** What prints this line, in the page's own vocabulary. */
  label: string;
  /** Expanded description used in the legend. */
  description: string;
  /** Text colour class for the ink, printed on paper. */
  inkClass: string;
  /** Border colour class for the ink, printed on paper. */
  borderClass: string;
  /** The same ink lifted for legibility against the dark console. */
  litInkClass: string;
  /** The same border lifted for legibility against the dark console. */
  litBorderClass: string;
}

export const ENGINE_PRESENTATION: Record<Engine, EnginePresentation> = {
  gemma: {
    label: "Gemma 4",
    description: "Planned, read or spoke. The learned part.",
    inkClass: "text-gemma",
    borderClass: "border-gemma",
    litInkClass: "text-gemma-lit",
    litBorderClass: "border-gemma-lit",
  },
  rule: {
    label: "Rule",
    description: "Deterministic. The EU-14 table and the escalation logic.",
    inkClass: "text-ink",
    borderClass: "border-ink",
    litInkClass: "text-paper",
    litBorderClass: "border-paper",
  },
  external: {
    label: "SerpApi",
    description: "Evidence fetched from outside the building.",
    inkClass: "text-confirm",
    borderClass: "border-confirm",
    litInkClass: "text-confirm-lit",
    litBorderClass: "border-confirm-lit",
  },
  human: {
    label: "Kitchen",
    description: "A person answered something no document contains.",
    inkClass: "text-pen",
    borderClass: "border-pen",
    litInkClass: "text-pen-lit",
    litBorderClass: "border-pen-lit",
  },
};

/** Language codes carried by the fixtures, for the explanation toggle. */
export const LANGUAGE_NAMES: Record<string, string> = {
  ar: "Arabic",
  uk: "Ukrainian",
  fr: "French",
  en: "English",
};

/** Right-to-left scripts need their own direction on the explanation block. */
const RTL_LANGUAGES = new Set(["ar", "he", "fa", "ur"]);

export function isRtl(language: string): boolean {
  return RTL_LANGUAGES.has(language);
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Count of steps Gemma itself produced — the Gemma Integration argument, as a number. */
export function countGemmaSteps(trace: Trace): number {
  return trace.steps.filter((step) => step.engine === "gemma").length;
}

/** Count of steps the orchestrator compelled rather than the model choosing. */
export function countForcedSteps(trace: Trace): number {
  return trace.steps.filter((step) => step.forced).length;
}
