import falafelRecording from "@/data/trace-falafel-rules.json";
import padThaiRecording from "@/data/trace-padthai-rules.json";
import symphonyRecordings from "@/data/symphony-cases.json";
import type { KitchenRisk, Trace, TraceStep } from "@/lib/trace";

/**
 * Real recorded runs, replayed when the live agent is not reachable.
 *
 * Nothing here is simulated. Every trace was produced by the orchestrator:
 * the Gemma ones on a laptop with Gemma 4 E2B loaded, the rules ones by the
 * keyless rules mode the hosted agent runs. The UI badges each one with the
 * engine that recorded it.
 */

/** Which build of the agent produced a recording. */
export type RecordedWith = "gemma" | "rules";

export interface RecordedCase {
  id: string;
  recordedWith: RecordedWith;
  /** Exactly what was typed when the run was recorded. */
  request: string;
  /**
   * The run as recorded. For a run with a kitchen step and no `outcomes`, the
   * kitchen answer is fixed: it is what the chef said when it was recorded.
   */
  trace: Trace;
  /** One real recording per kitchen answer, so any button replays honestly. */
  outcomes?: Record<KitchenRisk, Trace>;
}

interface SymphonyRecording extends Trace {
  request: string;
}

/** The Gemma run whose request is `request`, from the Symphony recordings. */
function gemmaRecording(request: string): Trace {
  const recordings = symphonyRecordings as unknown as SymphonyRecording[];
  const found = recordings.find((recording) => recording.request === request);
  if (!found) throw new Error(`missing Gemma recording: ${request}`);
  return found;
}

const falafelOutcomes = falafelRecording as unknown as Record<
  KitchenRisk,
  Trace
>;

export const RECORDED_CASES: Record<string, RecordedCase> = {
  "padthai-fish": {
    id: "padthai-fish",
    recordedWith: "rules",
    request:
      "I'm allergic to fish — can I have the pad thai without fish sauce?",
    trace: padThaiRecording as unknown as Trace,
  },
  "falafel-sesame": {
    id: "falafel-sesame",
    recordedWith: "rules",
    request: "Can I get the falafel without sesame?",
    trace: falafelOutcomes.unsure,
    outcomes: falafelOutcomes,
  },
  "paella-shellfish": {
    id: "paella-shellfish",
    recordedWith: "gemma",
    request: "I am allergic to shellfish. Can I eat the paella?",
    trace: gemmaRecording("I am allergic to shellfish. Can I eat the paella?"),
  },
  "bolognese-celery": {
    id: "bolognese-celery",
    recordedWith: "gemma",
    request:
      "Je suis allergique au celeri. Les pates bolognaises, c'est possible ?",
    trace: gemmaRecording(
      "Je suis allergique au celeri. Les pates bolognaises, c'est possible ?",
    ),
  },
};

export interface PresetCase {
  id: string;
  /** What the diner says. Sent verbatim to the live agent. */
  text: string;
  /** What the case demonstrates, in two or three words. */
  shows: string;
  /** The recorded run to play when the live agent is offline. */
  replayId: keyof typeof RECORDED_CASES;
}

/** Cases chosen to exercise the whole story, each checked against rules mode. */
export const PRESET_CASES: PresetCase[] = [
  {
    id: "padthai-fish",
    text: "I'm allergic to fish — can I have the pad thai without fish sauce?",
    shows: "Refusal · forced SerpApi lookup",
    replayId: "padthai-fish",
  },
  {
    id: "falafel-sesame",
    text: "Can I get the falafel without sesame?",
    shows: "Kitchen question",
    replayId: "falafel-sesame",
  },
  {
    id: "paella-crustaceans",
    text: "Je suis allergique aux crustacés, la paella ?",
    shows: "French · kitchen question",
    replayId: "paella-shellfish",
  },
  {
    id: "bolognese-celery",
    text: "Je suis allergique au céleri. Les pâtes bolognaises, c'est possible ?",
    shows: "French · label refusal",
    replayId: "bolognese-celery",
  },
];

/** Keywords that point free text at a recording, dish names before allergens. */
const CLOSEST_RECORDING: [RegExp, keyof typeof RECORDED_CASES][] = [
  [/pad\s*tha/i, "padthai-fish"],
  [/falafel/i, "falafel-sesame"],
  [/pa[eë]lla/i, "paella-shellfish"],
  [/bolo(g)?na/i, "bolognese-celery"],
  [/fish|poisson|nuoc|nam pla/i, "padthai-fish"],
  [/s[eé]sam|tahin/i, "falafel-sesame"],
  [/crust|shell|shrimp|prawn|crevette/i, "paella-shellfish"],
  [/c[eé]l[eé]r/i, "bolognese-celery"],
];

/** The recording nearest to what was typed; the pad thai refusal otherwise. */
export function closestRecording(text: string): RecordedCase {
  const match = CLOSEST_RECORDING.find(([pattern]) => pattern.test(text));
  return RECORDED_CASES[match ? match[1] : "padthai-fish"];
}

/**
 * Steps through a recording one line at a time, pausing at the kitchen.
 *
 * With `outcomes`, the kitchen's button picks which real recording continues.
 * Without them, the recorded chef's answer is shown and the replay continues
 * as recorded: nothing the viewer does changes a fixed verdict.
 */
export class ReplayRun {
  private cursor = 0;
  private current: Trace;

  constructor(readonly recording: RecordedCase) {
    this.current = recording.trace;
  }

  /** True when the kitchen buttons choose between real recordings. */
  get interactive(): boolean {
    return this.recording.outcomes !== undefined;
  }

  /** The kitchen step the replay is paused on, if any. */
  get kitchenStep(): TraceStep | undefined {
    const step = this.current.steps[this.cursor];
    return step?.tool === "ask_kitchen" ? step : undefined;
  }

  get pendingQuestion(): string | undefined {
    const question = this.kitchenStep?.args?.question;
    return typeof question === "string" ? question : undefined;
  }

  get finished(): boolean {
    return this.cursor >= this.current.steps.length;
  }

  /** Steps printed so far. */
  get steps(): TraceStep[] {
    return this.current.steps.slice(0, this.cursor);
  }

  get trace(): Trace {
    return this.current;
  }

  /** Print one more step, unless the kitchen has to answer first. */
  advance(): boolean {
    if (this.finished || this.kitchenStep) return false;
    this.cursor += 1;
    return true;
  }

  /** Pass the kitchen step, switching to the recording for `risk` if there is one. */
  answer(risk?: KitchenRisk): void {
    if (!this.kitchenStep) return;
    if (risk && this.recording.outcomes)
      this.current = this.recording.outcomes[risk];
    this.cursor += 1;
  }
}
