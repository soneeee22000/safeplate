import {
  ChefHat,
  Code,
  ExternalLink,
  Search,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import {
  formatDuration,
  type LookupStatement,
  type TraceStep,
} from "@/lib/trace";

/** Who produced a line, in the four words the operator screen uses. */
export type StepKind = "model" | "code" | "human" | "serpapi";

interface KindPresentation {
  label: string;
  description: string;
  Icon: LucideIcon;
  /** Chip styling: each kind differs in colour and in fill, not colour alone. */
  chipClass: string;
  titleClass: string;
}

export const STEP_KINDS: Record<StepKind, KindPresentation> = {
  model: {
    label: "Model",
    description: "Gemma 4 E2B heard or spoke. It never decides.",
    Icon: Sparkles,
    chipClass: "border-gemma text-gemma bg-paper",
    titleClass: "text-gemma",
  },
  code: {
    label: "Code",
    description: "Deterministic rules: the dish table, EU-14, escalation.",
    Icon: Code,
    chipClass: "border-ink bg-ink text-paper",
    titleClass: "text-ink",
  },
  human: {
    label: "Human",
    description: "The kitchen answered what no document can.",
    Icon: ChefHat,
    chipClass: "border-pen text-pen border-dashed bg-paper",
    titleClass: "text-pen",
  },
  serpapi: {
    label: "SerpApi",
    description: "Outside evidence on a packaged ingredient.",
    Icon: Search,
    chipClass: "border-serp bg-serp text-paper",
    titleClass: "text-serp",
  },
};

/** Map a step to its kind. A product lookup is SerpApi whatever engine tag it carries. */
export function stepKind(step: TraceStep): StepKind {
  if (step.tool === "lookup_product" || step.engine === "external")
    return "serpapi";
  if (step.engine === "gemma") return "model";
  if (step.engine === "human") return "human";
  return "code";
}

/** The chip naming who produced a line. */
export function KindChip({ kind }: { kind: StepKind }) {
  const { label, Icon, chipClass } = STEP_KINDS[kind];
  return (
    <span
      className={`inline-flex items-center gap-1 border px-1.5 py-0.5 font-mono text-xs tracking-wider uppercase ${chipClass}`}
    >
      <Icon className="size-3" aria-hidden="true" />
      {label}
    </span>
  );
}

/** One line of the ticket: who produced it, why, and what it found. */
export function TraceStepLine({ step }: { step: TraceStep }) {
  const kind = stepKind(step);

  return (
    <li className="printing py-4">
      <div className="flex items-baseline gap-3">
        <span className="text-ink-muted font-mono text-xs tabular-nums">
          {String(step.n).padStart(2, "0")}
        </span>
        <div className="min-w-0 flex-1">
          <StepHeader step={step} kind={kind} />
          <p className="text-ink/80 mt-1 text-sm leading-6">{step.reasoning}</p>
          {step.forced_by && (
            <p className="text-refuse mt-1.5 font-mono text-xs">
              Forced by code — {step.forced_by}
            </p>
          )}
          {kind === "serpapi" && <LookupSources step={step} />}
          {kind === "human" && <KitchenReply step={step} />}
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

/** Title, tool name, chips and duration. */
function StepHeader({ step, kind }: { step: TraceStep; kind: StepKind }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <h3 className={`font-semibold ${STEP_KINDS[kind].titleClass}`}>
        {step.title}
      </h3>
      <code className="text-ink-muted font-mono text-xs">
        {step.tool}
      </code>
      <KindChip kind={kind} />
      {step.forced && (
        <span
          className="border-refuse text-refuse border px-1.5 py-0.5 font-mono text-xs tracking-wider uppercase"
          title={step.forced_by}
        >
          Forced
        </span>
      )}
      <span className="text-ink-muted ml-auto font-mono text-xs tabular-nums">
        {formatDuration(step.duration_ms)}
      </span>
    </div>
  );
}

/** The host of a source URL, or the recorded source name when it has none. */
function hostOf(statement: LookupStatement): string {
  if (!statement.url) return statement.source;
  try {
    return new URL(statement.url).host.replace(/^www\./, "");
  } catch {
    return statement.source;
  }
}

/** The sources a product lookup found, each linked and tagged by trust. */
function LookupSources({ step }: { step: TraceStep }) {
  const statements = (step.result?.statements ?? []) as LookupStatement[];
  const confirmed = step.result?.confirmed === true;

  return (
    <div className="mt-3">
      {statements.length === 0 ? (
        <p className="text-ink-muted text-xs">No sources returned.</p>
      ) : (
        <ul className="border-serp/40 divide-serp/20 divide-y border">
          {statements.map((statement, index) => (
            <SourceItem
              key={`${statement.url}-${index}`}
              statement={statement}
            />
          ))}
        </ul>
      )}
      {!confirmed && (
        <p className="border-serp text-serp mt-2 border-l-2 pl-2 font-mono text-xs leading-5">
          No trusted declaration — treated as unconfirmed, never as safe.
        </p>
      )}
    </div>
  );
}

/** One linked source with its trust tag. */
function SourceItem({ statement }: { statement: LookupStatement }) {
  const host = hostOf(statement);
  const label = (
    <span className="flex items-center gap-1.5 font-mono text-xs">
      <span className="truncate">{host}</span>
      {statement.url && (
        <ExternalLink className="size-3 shrink-0" aria-hidden="true" />
      )}
    </span>
  );

  return (
    <li className="px-3 py-2">
      <div className="flex items-center justify-between gap-3">
        {statement.url ? (
          <a
            href={statement.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-serp flex min-h-11 min-w-0 items-center underline-offset-2 hover:underline"
          >
            {label}
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
        ) : (
          <span className="text-ink min-w-0">{label}</span>
        )}
        <TrustTag trusted={statement.trusted} />
      </div>
      <p className="text-ink/70 mt-0.5 line-clamp-2 text-xs leading-5">
        {statement.text}
      </p>
    </li>
  );
}

/** Trusted means a manufacturer, retailer or product database. */
function TrustTag({ trusted }: { trusted: boolean }) {
  return (
    <span
      className={`shrink-0 border px-1.5 font-mono text-xs tracking-wider uppercase ${
        trusted
          ? "border-serp bg-serp text-paper"
          : "border-ink/30 text-ink-muted"
      }`}
    >
      {trusted ? "Trusted" : "Untrusted"}
    </span>
  );
}

const RISK_WORDS: Record<string, string> = {
  none: "No risk",
  risk: "Risk",
  unsure: "Unsure",
};

/** What the kitchen said, once it has said it. */
function KitchenReply({ step }: { step: TraceStep }) {
  const risk = typeof step.result?.risk === "string" ? step.result.risk : null;
  const answer =
    typeof step.result?.answer === "string" ? step.result.answer : null;
  if (!risk && !answer) return null;
  const note = answer && answer !== risk ? answer : null;

  return (
    <blockquote className="border-pen text-pen mt-2 border-l-2 pl-3 text-sm">
      {risk && (
        <span className="font-mono text-xs tracking-wider uppercase">
          Chef: {RISK_WORDS[risk] ?? risk}
        </span>
      )}
      {note && <span className="block italic">“{note}”</span>}
    </blockquote>
  );
}
