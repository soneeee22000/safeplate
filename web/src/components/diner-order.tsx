"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { History, Radio } from "lucide-react";
import { TicketLine } from "@/components/evidence-ticket";
import { ModeBanner, recordedBadge } from "@/components/verify/mode-banner";
import recordedCases from "@/data/symphony-cases.json";
import {
  POLL_INTERVAL_MS,
  checkHealth,
  orchestrator,
  type AgentMode,
  type CaseRequest,
  type RunState,
} from "@/lib/orchestrator";
import {
  VERDICT_PRESENTATION,
  isRtl,
  type Trace,
  type TraceStep,
} from "@/lib/trace";

const MENU_NAME = "Demo menu";

/** Printed unchanged on all three labels. It describes the site, not the dish. */
const FACILITY_DECLARATION =
  "Élaboré dans un atelier qui utilise : gluten, céleri, moutarde, arachides, " +
  "poisson, œufs, soja, lait, fruits à coque, sésame.";

interface DinerLanguage {
  code: string;
  /** The language written in its own script — the only label a diner can pick out. */
  endonym: string;
  english: string;
  /** A question a diner would really ask, shown in the input. */
  example: string;
}

const LANGUAGES: readonly DinerLanguage[] = [
  {
    code: "auto",
    endonym: "Auto-detect",
    english: "From your question",
    example: "Ask in your own words, and name what you cannot eat.",
  },
  {
    code: "my",
    endonym: "မြန်မာ",
    english: "Burmese",
    example: "ကျွန်တော် အခွံမာသီး မစားနိုင်ဘူး။ ဒီဟင်းထဲမှာ ပါသလား။",
  },
  {
    code: "en",
    endonym: "English",
    english: "English",
    example: "I am allergic to nuts. Can I eat this one?",
  },
  {
    code: "ur",
    endonym: "اردو",
    english: "Urdu",
    example: "مجھے گری دار میوے سے الرجی ہے۔ کیا میں یہ کھا سکتا ہوں؟",
  },
  {
    code: "zh",
    endonym: "中文",
    english: "Mandarin",
    example: "我对坚果过敏，这道菜我能吃吗？",
  },
];

interface MenuDish {
  id: string;
  name: string;
  grams: number;
  /** `plat numéro` on the packaging — how the kitchen identifies it. */
  plate: string;
  /** The ingredient list, transcribed from the label rather than translated. */
  ingredients: string;
  /** Allergens the label itself declares in bold. */
  declared: readonly string[];
  /** In the ingredient list, and not declared in bold. */
  undeclared: readonly string[];
}

const MENU: readonly MenuDish[] = [
  {
    id: "paella",
    name: "Paëlla poisson chorizo et poulet",
    grams: 425,
    plate: "JU0T2hac",
    ingredients:
      "Riz, blanc de poulet, cabillaud, chorizo, huile d’olive, poivrons, " +
      "oignons, petits pois, sel, piment doux fumé, safran, poivre.",
    declared: ["fish — cabillaud"],
    undeclared: [],
  },
  {
    id: "bolognaise",
    name: "Pâtes bolognaises spécialité du chef",
    grams: 450,
    plate: "p45jG3yE",
    ingredients:
      "Fusilli, bœuf haché, carottes, purée de tomates, huile d’olive, " +
      "concentré de tomate, emmental, purée d’oignons, Parmesan, échalotes, " +
      "ail, sel, basilic, paprika, céleri, origan, poivre, romarin, laurier.",
    declared: [
      "cereals containing gluten — fusilli",
      "milk — emmental, Parmesan",
      "celery — céleri",
    ],
    undeclared: [],
  },
];

type OrderStatus =
  "idle" | "running" | "awaiting_staff" | "complete" | "failed";

const ORDER_STATUS: Record<RunState["status"], OrderStatus> = {
  running: "running",
  answering: "running",
  awaiting_human: "awaiting_staff",
  complete: "complete",
  failed: "failed",
};

interface OrderView {
  status: OrderStatus;
  steps: TraceStep[];
  trace: Trace | null;
  pendingQuestion?: string;
  error?: string;
}

const IDLE_VIEW: OrderView = { status: "idle", steps: [], trace: null };

type BackendState = "probing" | "live" | "offline";

type DinerDecision = "different_dish" | "ask_staff" | "order_anyway";

interface DinerChoice {
  id: DinerDecision;
  label: string;
  detail: string;
  /** What the diner is told once the choice is taken. */
  consequence: string;
}

const CHOICES: readonly DinerChoice[] = [
  {
    id: "different_dish",
    label: "Choose a different dish",
    detail: "Go back to the three dishes and ask about another one.",
    consequence: "",
  },
  {
    id: "ask_staff",
    label: "Ask a member of staff",
    detail: "A person can answer what the agent could not.",
    consequence:
      "Show this screen to a member of staff. It carries the dish, the plate " +
      "number and what could not be confirmed, so nobody has to answer from memory.",
  },
  {
    id: "order_anyway",
    label: "Order it and tell the kitchen",
    detail: "You accept what was not confirmed.",
    consequence:
      "Nothing has been cleared. Tell the person taking the order what you " +
      "cannot eat, so it reaches the pass with the dish. The risk stays yours.",
  },
];

function reason(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "the orchestrator did not answer";
}

function toView(state: RunState): OrderView {
  const status = ORDER_STATUS[state.status];
  return {
    status,
    steps: state.trace.steps,
    trace: status === "complete" ? state.trace : null,
    pendingQuestion: state.pending_question,
    error: state.error,
  };
}

interface OrderRun {
  view: OrderView;
  start: (request: CaseRequest) => Promise<void>;
  answerStaff: (text: string) => Promise<void>;
  reset: () => void;
}

/** A recorded run, with the request that produced it. */
type RecordedCase = Trace & { request: string };

/** Every Symphony recording was made with Gemma 4 E2B loaded. */
const RECORDED: RecordedCase[] = recordedCases as unknown as RecordedCase[];

/** The badge for whatever is producing the ticket on screen. */
function sourceLabel(mode: AgentMode | null): string {
  if (!mode) return recordedBadge("gemma");
  return mode === "gemma" ? "Live · Gemma 4 E2B" : "Live · rules mode";
}

const REPLAY_STEP_MS = 900;

/**
 * Pick the recorded run that best answers what was asked.
 *
 * Scored on shared words rather than matched exactly, because the diner types
 * their own sentence and the recorded request is only ever an approximation of
 * it. Returns null when nothing overlaps, which the caller reports honestly
 * instead of replaying an unrelated case.
 */
function bestRecorded(request: string, dishName: string): RecordedCase | null {
  const words = new Set(
    `${request} ${dishName}`
      .toLowerCase()
      .replace(/[^\p{L}\s]/gu, " ")
      .split(/\s+/)
      .filter((word) => word.length > 3),
  );

  let best: RecordedCase | null = null;
  let bestScore = 0;
  for (const candidate of RECORDED) {
    const target =
      `${candidate.request} ${candidate.dish} ${candidate.allergen}`.toLowerCase();
    let score = 0;
    for (const word of words) if (target.includes(word)) score += 1;
    if (score > bestScore) {
      best = candidate;
      bestScore = score;
    }
  }
  return bestScore >= 2 ? best : null;
}

/**
 * One case: run live against the orchestrator, or replay a recorded one.
 *
 * The staff console replays to show what the agent does. Doing the same here
 * needed care, because a diner reading a verdict must never mistake a recording
 * for a check that just happened — so replay is labelled as a recording
 * everywhere it appears, and a request nothing was recorded for says so rather
 * than showing the nearest unrelated answer.
 */
function useOrderRun(live: boolean): OrderRun {
  const [view, setView] = useState<OrderView>(IDLE_VIEW);
  const runIdRef = useRef<string | null>(null);
  const replayRef = useRef<RecordedCase | null>(null);

  const start = useCallback(
    async (request: CaseRequest) => {
      if (!live) {
        const spoken = request.text ?? "";
        const recorded = bestRecorded(spoken, spoken);
        if (!recorded) {
          setView({
            status: "failed",
            steps: [],
            trace: null,
            error:
              "no recorded run matches that question, and nothing was checked. " +
              "Try one of the example questions, or ask a member of staff.",
          });
          return;
        }
        replayRef.current = recorded;
        setView({ status: "running", steps: [], trace: null });
        return;
      }

      setView({ status: "running", steps: [], trace: null });
      try {
        runIdRef.current = await orchestrator.postCase(request);
      } catch (error) {
        setView({
          status: "failed",
          steps: [],
          trace: null,
          error: reason(error),
        });
      }
    },
    [live],
  );

  const poll = useCallback(async () => {
    const runId = runIdRef.current;
    if (!runId) return;
    try {
      setView(toView(await orchestrator.getRun(runId)));
    } catch (error) {
      setView((current) => ({
        ...current,
        status: "failed",
        error: reason(error),
      }));
    }
  }, []);

  // Replay advances one recorded step at a time so the diner can read the
  // agent's working, which is the point of showing it at all.
  const advanceReplay = useCallback(() => {
    const recorded = replayRef.current;
    if (!recorded) return;

    setView((current) => {
      const next = current.steps.length + 1;
      if (next > recorded.steps.length) {
        return { ...current, status: "complete", trace: recorded };
      }
      const steps = recorded.steps.slice(0, next);
      const waiting =
        steps[steps.length - 1]?.tool === "ask_kitchen" &&
        next < recorded.steps.length;
      return {
        status: waiting ? "awaiting_staff" : "running",
        steps,
        trace: null,
        pendingQuestion: waiting
          ? (steps[steps.length - 1].args?.question as string | undefined)
          : undefined,
      };
    });
  }, []);

  useEffect(() => {
    if (view.status !== "running") return;
    const timer = window.setInterval(
      () => (live ? void poll() : advanceReplay()),
      live ? POLL_INTERVAL_MS : REPLAY_STEP_MS,
    );
    return () => window.clearInterval(timer);
  }, [view.status, poll, live, advanceReplay]);

  const answerStaff = useCallback(
    async (text: string) => {
      const recorded = replayRef.current;
      if (!live && recorded) {
        // The typed answer replaces the recorded one on the ticket, so the
        // person answering sees their own words, but the verdict stays the
        // recorded one — it is not being recomputed from what they typed.
        setView((current) => ({
          ...current,
          status: "running",
          steps: current.steps.map((step) =>
            step.tool === "ask_kitchen"
              ? {
                  ...step,
                  result: {
                    ...step.result,
                    answered_by: "staff",
                    answer: text,
                  },
                }
              : step,
          ),
          pendingQuestion: undefined,
        }));
        return;
      }

      const runId = runIdRef.current;
      if (!runId) return;
      try {
        setView(toView(await orchestrator.postAnswer(runId, text)));
      } catch (error) {
        setView((current) => ({
          ...current,
          status: "failed",
          error: reason(error),
        }));
      }
    },
    [live],
  );

  const reset = useCallback(() => {
    runIdRef.current = null;
    setView(IDLE_VIEW);
  }, []);

  return useMemo(
    () => ({ view, start, answerStaff, reset }),
    [view, start, answerStaff, reset],
  );
}

/**
 * The screen the diner holds. Same loop as the staff console, different
 * contract: it never ends on a bare verdict, it ends on a decision the diner
 * makes with the reasons in front of them.
 */
export function DinerOrder() {
  const [backend, setBackend] = useState<BackendState>("probing");
  const [mode, setMode] = useState<AgentMode | null>(null);
  const [language, setLanguage] = useState<string>(LANGUAGES[0].code);
  const [dishId, setDishId] = useState<string | null>(null);
  const [decision, setDecision] = useState<DinerDecision | null>(null);
  const run = useOrderRun(backend === "live");

  useEffect(() => {
    const controller = new AbortController();
    checkHealth(controller.signal)
      .then((found) => {
        setMode(found);
        setBackend(found ? "live" : "offline");
      })
      .catch(() => setBackend("offline"));
    return () => controller.abort();
  }, []);

  const dish = MENU.find((item) => item.id === dishId) ?? null;
  const busy =
    run.view.status === "running" || run.view.status === "awaiting_staff";

  const chooseDish = useCallback(
    (id: string) => {
      setDishId(id);
      setDecision(null);
      run.reset();
    },
    [run],
  );

  const ask = useCallback(
    (request: CaseRequest) => {
      if (!dish) return;
      // The loop extracts the dish from the utterance, so the tapped card has to
      // travel inside the text — "can I eat this?" names nothing on its own.
      void run.start({
        text: request.text ? `${dish.name}: ${request.text}` : dish.name,
        audio: request.audio,
      });
    },
    [dish, run],
  );

  const decide = useCallback(
    (choice: DinerDecision) => {
      if (choice !== "different_dish") {
        setDecision(choice);
        return;
      }
      setDishId(null);
      setDecision(null);
      run.reset();
    },
    [run],
  );

  return (
    <div className="space-y-10">
      <LanguageChooser value={language} onChange={setLanguage} />

      {backend === "offline" && <OfflineNotice />}
      {backend === "live" && mode && (
        <div className="max-w-xl">
          <ModeBanner
            connection={{ kind: "live", mode }}
            replayRecordedWith={null}
            onSkip={() => undefined}
            onRetry={() => undefined}
          />
        </div>
      )}

      <MenuBoard selectedId={dishId} onSelect={chooseDish} disabled={busy} />

      {dish && (
        <AskBox
          dish={dish}
          language={language}
          onSubmit={ask}
          disabled={busy}
          offline={backend === "offline"}
          canHear={backend === "live" && mode === "gemma"}
        />
      )}

      <section aria-live="polite">
        {run.view.status !== "idle" && dish && (
          <RunTicket
            dish={dish}
            source={backend === "live" ? mode : null}
            view={run.view}
            decision={decision}
            onAnswerStaff={run.answerStaff}
            onDecide={decide}
          />
        )}
      </section>
    </div>
  );
}

function LanguageChooser({
  value,
  onChange,
}: {
  value: string;
  onChange: (code: string) => void;
}) {
  return (
    <section>
      <h2 className="font-mono text-xs tracking-[0.25em] uppercase">
        Your language
      </h2>
      <div className="mt-4 flex flex-wrap gap-2">
        {LANGUAGES.map((option) => (
          <button
            key={option.code}
            type="button"
            onClick={() => onChange(option.code)}
            aria-pressed={option.code === value}
            lang={option.code === "auto" ? undefined : option.code}
            className={`min-h-14 border px-4 py-2 text-left transition-colors ${
              option.code === value
                ? "border-paper bg-paper text-console"
                : "border-console-line text-paper hover:border-paper/60"
            }`}
          >
            <span className="block text-base leading-6">{option.endonym}</span>
            <span className="block font-mono text-xs tracking-wider uppercase opacity-70">
              {option.english}
            </span>
          </button>
        ))}
      </div>
      <p className="text-muted-foreground mt-3 max-w-xl text-sm leading-6">
        This changes the examples on this screen.
      </p>
    </section>
  );
}

function OfflineNotice() {
  return (
    <section className="border-confirm text-confirm-lit border p-5">
      <h2 className="font-display text-lg font-semibold">
        Recorded runs — the agent is not running right now.
      </h2>
      <p className="text-muted-foreground mt-2 max-w-2xl text-sm leading-6">
        Gemma 4 is a 7.2 GB model that runs on a laptop, not on this page. What
        you see below are real Gemma runs of the agent against these labels,
        replayed step by step and badged as recordings — not a live check of
        your food.
      </p>
      <p className="text-confirm-lit mt-2 max-w-2xl text-sm leading-6">
        So nothing here has been checked for you. If you are ordering, ask a
        member of staff about your allergy, and tell them what you cannot eat
        rather than only what you would like.
      </p>
    </section>
  );
}

function MenuBoard({
  selectedId,
  onSelect,
  disabled,
}: {
  selectedId: string | null;
  onSelect: (id: string) => void;
  disabled: boolean;
}) {
  return (
    <section>
      <h2 className="font-mono text-xs tracking-[0.25em] uppercase">
        {MENU_NAME} (labels transcribed from a Paris shop)
      </h2>
      <ul className="mt-4 grid gap-4 md:grid-cols-3">
        {MENU.map((dish) => (
          <li key={dish.id}>
            <DishCard
              dish={dish}
              selected={dish.id === selectedId}
              onSelect={onSelect}
              disabled={disabled}
            />
          </li>
        ))}
      </ul>
      <p className="text-confirm-lit border-confirm mt-4 max-w-3xl border-l-2 pl-3 text-sm leading-6">
        Every one of these labels carries the same line: {FACILITY_DECLARATION}{" "}
        That is the building, not the recipe — no dish here can be called free
        of those ten.
      </p>
    </section>
  );
}

function DishCard({
  dish,
  selected,
  onSelect,
  disabled,
}: {
  dish: MenuDish;
  selected: boolean;
  onSelect: (id: string) => void;
  disabled: boolean;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(dish.id)}
      aria-pressed={selected}
      disabled={disabled}
      className={`flex h-full min-h-11 w-full flex-col border p-5 text-left transition-colors disabled:opacity-40 ${
        selected
          ? "border-paper bg-console-raised"
          : "border-console-line hover:border-paper/60"
      }`}
    >
      <span className="text-muted-foreground font-mono text-xs tracking-wider uppercase">
        {dish.grams} g · plat {dish.plate}
      </span>
      <span className="font-display mt-2 text-lg leading-6 font-semibold">
        {dish.name}
      </span>
      <span className="text-muted-foreground mt-3 text-xs leading-5" lang="fr">
        {dish.ingredients}
      </span>

      <span className="mt-4 block space-y-1">
        {dish.declared.map((item) => (
          <span
            key={item}
            className="text-confirm-lit block font-mono text-xs leading-5"
          >
            declared · {item}
          </span>
        ))}
        {dish.undeclared.map((item) => (
          <span
            key={item}
            className="text-refuse block font-mono text-xs leading-5"
          >
            not in bold · {item}
          </span>
        ))}
      </span>
    </button>
  );
}

function AskBox({
  dish,
  language,
  onSubmit,
  disabled,
  offline,
  canHear,
}: {
  dish: MenuDish;
  language: string;
  onSubmit: (request: CaseRequest) => void;
  disabled: boolean;
  offline: boolean;
  /** True only when a live agent with Gemma loaded can hear a recording. */
  canHear: boolean;
}) {
  const [text, setText] = useState("");
  const [recording, setRecording] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = useCallback(async () => {
    setMicError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];

      recorder.ondataavailable = (event) => chunksRef.current.push(event.data);
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        onSubmit({
          audio: new Blob(chunksRef.current, { type: recorder.mimeType }),
        });
      };

      recorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      setMicError("No microphone here. Type your question instead.");
    }
  }, [onSubmit]);

  const stopRecording = useCallback(() => {
    recorderRef.current?.stop();
    setRecording(false);
  }, []);

  const example =
    LANGUAGES.find((option) => option.code === language)?.example ?? "";
  const rtl = isRtl(language);

  return (
    <section className="border-console-line border p-6">
      <h2 className="font-display text-xl font-semibold">
        Ask about the {dish.name}.
      </h2>
      <p className="text-muted-foreground mt-1 max-w-2xl text-sm leading-6">
        Say what you cannot eat, in your own words. You do not have to know the
        word for it in French, and you do not have to be right about the dish.
      </p>

      {canHear && (
        <>
          <button
            type="button"
            onClick={recording ? stopRecording : startRecording}
            disabled={disabled}
            aria-pressed={recording}
            className={`mt-5 flex min-h-14 w-full items-center justify-center gap-3 border px-5 font-mono text-sm tracking-wider uppercase transition-colors disabled:opacity-40 ${
              recording
                ? "border-refuse text-refuse"
                : "border-paper text-paper hover:bg-paper hover:text-console"
            }`}
          >
            <span
              className={`h-3 w-3 rounded-full ${recording ? "bg-refuse animate-pulse" : "bg-paper"}`}
              aria-hidden="true"
            />
            {recording ? "Stop and send" : "Speak your question"}
          </button>

          <p className="text-muted-foreground mt-2 text-xs leading-5">
            Name the dish out loud as part of the question. The agent listens to the
            recording itself, not to the card you tapped.
          </p>

          {micError && (
            <p className="text-confirm-lit mt-2 font-mono text-xs leading-5">
              {micError}
            </p>
          )}

          <div className="my-5 flex items-center gap-3">
            <span className="bg-console-line h-px flex-1" aria-hidden="true" />
            <span className="text-muted-foreground font-mono text-xs tracking-widest uppercase">
              or type it
            </span>
            <span className="bg-console-line h-px flex-1" aria-hidden="true" />
          </div>
        </>
      )}

      <form
        className={canHear ? undefined : "mt-5"}
        onSubmit={(event) => {
          event.preventDefault();
          if (text.trim()) onSubmit({ text: text.trim() });
        }}
      >
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={3}
          dir={rtl ? "rtl" : "ltr"}
          lang={language === "auto" ? undefined : language}
          placeholder={example}
          aria-label="Your question about this dish"
          className="border-console-line bg-console-raised text-paper placeholder:text-muted-foreground focus-visible:border-paper w-full resize-none border px-3 py-3 text-base outline-none"
        />

        <button
          type="submit"
          disabled={disabled || !text.trim()}
          className="bg-paper text-console hover:bg-paper-shade mt-3 min-h-12 w-full px-5 font-mono text-sm tracking-wider uppercase transition-colors disabled:opacity-40"
        >
          {disabled && !offline ? "Checking" : "Ask"}
        </button>
      </form>
    </section>
  );
}

function RunTicket({
  dish,
  source,
  view,
  decision,
  onAnswerStaff,
  onDecide,
}: {
  dish: MenuDish;
  /** The live agent's mode, or null when the ticket is a recording. */
  source: AgentMode | null;
  view: OrderView;
  decision: DinerDecision | null;
  onAnswerStaff: (text: string) => Promise<void>;
  onDecide: (choice: DinerDecision) => void;
}) {
  return (
    <article className="mx-auto w-full max-w-2xl">
      <div className="ticket-edge" aria-hidden="true" />
      <div className="bg-paper text-ink px-6 py-7 sm:px-9">
        <header className="border-ink/25 border-b pb-4">
          <SourceBadge mode={source} />
          <p className="mt-3 font-mono text-xs tracking-[0.2em] uppercase">
            {MENU_NAME} · plat {dish.plate}
          </p>
          <h3 className="font-display mt-1 text-xl font-semibold">
            {dish.name}
          </h3>
        </header>

        <ol className="divide-ink/15 divide-y">
          {view.steps.map((step) => (
            <TicketLine key={step.n} step={step} />
          ))}
        </ol>

        {view.status === "running" && (
          <p className="text-ink-muted mt-5 font-mono text-xs" role="status">
            checking…
          </p>
        )}

        {view.status === "awaiting_staff" && view.pendingQuestion && (
          <StaffPrompt
            question={view.pendingQuestion}
            onSubmit={onAnswerStaff}
          />
        )}

        {view.status === "failed" && <RunFailed error={view.error} />}

        {view.status === "complete" && view.trace && (
          <Outcome trace={view.trace} decision={decision} onDecide={onDecide} />
        )}
      </div>
      <div className="ticket-edge ticket-edge-bottom" aria-hidden="true" />
    </article>
  );
}

/** Says whether the ticket is the live agent (and in which mode) or a recording. */
function SourceBadge({ mode }: { mode: AgentMode | null }) {
  const Icon = mode ? Radio : History;
  return (
    <p
      className={`inline-flex items-center gap-1.5 border-2 px-2 py-1 font-mono text-xs font-semibold tracking-wider uppercase ${
        mode
          ? "border-verified text-verified-ink"
          : "border-confirm text-confirm-ink"
      }`}
    >
      <Icon className="size-4" aria-hidden="true" />
      {sourceLabel(mode)}
    </p>
  );
}

function RunFailed({ error }: { error?: string }) {
  return (
    <div className="border-refuse mt-5 border-l-2 pl-3">
      <p className="text-refuse font-mono text-sm">
        The check stopped: {error ?? "unknown error"}.
      </p>
      <p className="text-ink/80 mt-1 text-sm leading-6">
        Nothing was cleared and nothing here is an answer. Ask a member of staff
        before you order.
      </p>
    </div>
  );
}

function StaffPrompt({
  question,
  onSubmit,
}: {
  question: string;
  onSubmit: (text: string) => Promise<void>;
}) {
  const [answer, setAnswer] = useState("");

  const send = useCallback(() => {
    const text = answer.trim();
    if (!text) return;
    setAnswer("");
    void onSubmit(text);
  }, [answer, onSubmit]);

  return (
    <div className="border-pen mt-6 border-l-2 pl-4">
      <p className="text-pen font-mono text-xs tracking-wider uppercase">
        This needs a person
      </p>
      <p className="text-ink mt-2 font-semibold">{question}</p>
      <p className="text-ink-muted mt-1 text-xs leading-5">
        Show this to a member of staff. Only the kitchen knows what shares a
        pan, and nothing is cleared until they say.
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        <input
          value={answer}
          onChange={(event) => setAnswer(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") send();
          }}
          placeholder="What the kitchen said"
          aria-label="The kitchen’s answer"
          className="border-ink/30 text-ink placeholder:text-ink-muted focus-visible:border-pen min-h-12 min-w-0 flex-1 border bg-transparent px-3 text-base outline-none"
        />
        <button
          type="button"
          onClick={send}
          className="bg-ink text-paper min-h-12 px-5 font-mono text-xs tracking-wider uppercase"
        >
          Send
        </button>
      </div>
    </div>
  );
}

function Outcome({
  trace,
  decision,
  onDecide,
}: {
  trace: Trace;
  decision: DinerDecision | null;
  onDecide: (choice: DinerDecision) => void;
}) {
  const verdict = VERDICT_PRESENTATION[trace.verdict];
  const cleared = trace.verdict === "verified";
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

      <p
        dir={rtl ? "rtl" : "ltr"}
        lang={trace.diner_language}
        className="border-gemma bg-paper-shade/60 mt-7 border-l-2 px-4 py-3 text-sm leading-7 whitespace-pre-line"
      >
        {trace.explanation}
      </p>
      <p className="text-ink-muted mt-2 px-4 text-xs leading-6" lang="en">
        {trace.explanation_en}
      </p>

      <p className="text-ink-muted mt-4 text-xs leading-5" lang="fr">
        On every label here: {FACILITY_DECLARATION}
      </p>

      <ChoicePanel cleared={cleared} decision={decision} onDecide={onDecide} />
    </>
  );
}

function ChoicePanel({
  cleared,
  decision,
  onDecide,
}: {
  cleared: boolean;
  decision: DinerDecision | null;
  onDecide: (choice: DinerDecision) => void;
}) {
  const taken = CHOICES.find((choice) => choice.id === decision) ?? null;

  return (
    <section className="border-ink/25 mt-7 border-t pt-5">
      <h4 className="font-display text-lg font-semibold">
        {cleared
          ? "Cleared as far as it can be. What happens next is still yours."
          : "This could not be cleared. Here is what you can do."}
      </h4>

      <ul className="mt-4 space-y-2">
        {CHOICES.map((choice) => (
          <li key={choice.id}>
            <button
              type="button"
              onClick={() => onDecide(choice.id)}
              aria-pressed={choice.id === decision}
              className={`min-h-11 w-full border px-4 py-3 text-left transition-colors ${
                choice.id === decision
                  ? "border-ink bg-ink text-paper"
                  : "border-ink/30 text-ink hover:border-ink"
              }`}
            >
              <span className="block font-semibold">{choice.label}</span>
              <span className="mt-0.5 block text-xs leading-5 opacity-80">
                {choice.detail}
              </span>
            </button>
          </li>
        ))}
      </ul>

      {taken && (
        <p className="border-pen text-ink mt-4 border-l-2 pl-3 text-sm leading-6">
          {taken.consequence}
        </p>
      )}
    </section>
  );
}
