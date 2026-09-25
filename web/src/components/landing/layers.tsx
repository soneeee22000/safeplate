type Lane = "model" | "code" | "human";

interface LanePresentation {
  name: string;
  owner: string;
  inkClass: string;
  borderClass: string;
  rowClass: string;
}

const LANES: Record<Lane, LanePresentation> = {
  model: {
    name: "Model",
    owner: "Gemma 4 E2B",
    inkClass: "text-gemma-lit",
    borderClass: "border-gemma-lit",
    rowClass: "lg:row-start-1",
  },
  code: {
    name: "Code",
    owner: "Plain Python",
    inkClass: "text-paper",
    borderClass: "border-paper",
    rowClass: "lg:row-start-2",
  },
  human: {
    name: "Human",
    owner: "The kitchen",
    inkClass: "text-confirm-lit",
    borderClass: "border-confirm-lit",
    rowClass: "lg:row-start-3",
  },
};

const LANE_ORDER: Lane[] = ["model", "code", "human"];

interface Step {
  lane: Lane;
  columnClass: string;
  title: string;
  detail: string;
  /** SerpApi is outside evidence the code fetches, so it is drawn apart. */
  serp?: boolean;
  forced?: boolean;
}

/** One pass of the loop, left to right. Ordered because it is a sequence. */
const STEPS: Step[] = [
  {
    lane: "model",
    columnClass: "lg:col-start-2",
    title: "Hear",
    detail: "Turns what the diner says into a dish and an allergen.",
  },
  {
    lane: "code",
    columnClass: "lg:col-start-3",
    title: "Check",
    detail: "The dish table and the EU-14 allergen table.",
  },
  {
    lane: "code",
    columnClass: "lg:col-start-4",
    title: "Look up",
    detail:
      "Packaged ingredient, such as fish sauce? SerpApi fetches what the manufacturer declares.",
    serp: true,
    forced: true,
  },
  {
    lane: "human",
    columnClass: "lg:col-start-5",
    title: "Ask",
    detail: "One question to the chef, who taps No risk, Risk or Unsure.",
    forced: true,
  },
  {
    lane: "code",
    columnClass: "lg:col-start-6",
    title: "Decide",
    detail: "Do not serve, needs confirmation, or can serve with confirmation.",
  },
  {
    lane: "model",
    columnClass: "lg:col-start-7",
    title: "Speak",
    detail:
      "Writes the answer in the diner's language. A reply that contradicts the verdict is discarded.",
  },
];

/** Section 4: which layer does what, drawn as three swim lanes. */
export function Layers() {
  return (
    <section id="layers" className="border-console-line scroll-mt-20 border-b">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-20">
        <h2 className="font-display max-w-3xl text-3xl leading-tight font-bold tracking-tight text-balance sm:text-4xl">
          Three layers. Only one of them decides.
        </h2>
        <p className="text-muted-foreground mt-5 max-w-2xl leading-7">
          The model is at both ends of the loop, never in the middle. Code makes
          every decision and forces the two calls a small model skips: the
          SerpApi lookup and the question to the kitchen.
        </p>

        <div className="mt-12 lg:grid lg:grid-cols-[7rem_repeat(6,minmax(0,1fr))] lg:grid-rows-3 lg:gap-x-3 lg:gap-y-4">
          {LANE_ORDER.map((lane) => (
            <LaneLabel key={lane} lane={lane} />
          ))}
          <ol className="flex flex-col gap-3 lg:contents">
            {STEPS.map((step, index) => (
              <StepCard key={step.title} step={step} position={index + 1} />
            ))}
          </ol>
        </div>

        <p className="text-muted-foreground mt-8 max-w-2xl text-sm leading-6">
          In rules mode the model lane is replaced by fixed rules and fixed
          English sentences, so the agent runs without Gemma. The code and human
          lanes are the same either way.
        </p>
      </div>
    </section>
  );
}

/** Lane header plus the track line the lane's steps sit on (wide screens only). */
function LaneLabel({ lane }: { lane: Lane }) {
  const presentation = LANES[lane];

  return (
    <div
      className={`relative hidden lg:col-span-7 lg:col-start-1 lg:flex lg:items-center ${presentation.rowClass}`}
      aria-hidden="true"
    >
      <div className="w-28 shrink-0">
        <p
          className={`font-display text-lg font-bold ${presentation.inkClass}`}
        >
          {presentation.name}
        </p>
        <p className="text-muted-foreground text-xs">{presentation.owner}</p>
      </div>
      <div className="border-muted-foreground/40 ml-3 flex-1 border-t border-dashed" />
    </div>
  );
}

/** One step, placed in its lane's row and its own column. */
function StepCard({ step, position }: { step: Step; position: number }) {
  const lane = LANES[step.lane];
  const border = step.serp ? "border-serp-lit" : lane.borderClass;
  const ink = step.serp ? "text-serp-lit" : lane.inkClass;

  return (
    <li
      className={`bg-console-raised relative z-[1] border-t-2 p-4 ${border} ${step.columnClass} ${lane.rowClass}`}
    >
      <div className="flex items-baseline justify-between gap-2">
        <p className={`font-display text-lg font-bold ${ink}`}>
          <span className="text-muted-foreground mr-2 font-mono text-xs tabular-nums">
            {position}
          </span>
          {step.title}
        </p>
        <span className={`text-xs lg:hidden ${lane.inkClass}`}>
          {step.serp ? "Code + SerpApi" : lane.name}
        </span>
      </div>
      <p className="text-muted-foreground mt-2 text-sm leading-6">
        {step.detail}
      </p>
      {(step.serp || step.forced) && (
        <p className="mt-3 flex flex-wrap gap-1.5">
          {step.serp && (
            <span className="border-serp-lit text-serp-lit border px-1.5 font-mono text-xs">
              SerpApi
            </span>
          )}
          {step.forced && (
            <span className="border-refuse text-refuse-lit border px-1.5 font-mono text-xs">
              Forced
            </span>
          )}
        </p>
      )}
    </li>
  );
}
