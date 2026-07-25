import { ENGINE_PRESENTATION, type Engine } from "@/lib/trace";

interface ToolSummary {
  name: string;
  engine: Engine;
  does: string;
  survives: string;
}

/**
 * The five tools. Deliberately not numbered: the agent is a loop with forced
 * branches, not a sequence, and numbering them would claim an order the
 * orchestrator does not guarantee.
 */
const TOOLS: ToolSummary[] = [
  {
    name: "read_label",
    engine: "rule",
    does: "Tesseract reads the ingredient panel on-device, in French and English, and reports how confident it is.",
    survives:
      "Below 0.75 confidence the loop refuses to reason over the text and asks for another photo.",
  },
  {
    name: "structure_ingredients",
    engine: "gemma",
    does: "Gemma turns one run-on OCR line into discrete, normalised ingredients — abbreviations, E-numbers, nested parentheticals and all.",
    survives:
      "Anything it cannot resolve is passed on as unresolved rather than guessed at.",
  },
  {
    name: "match_allergens",
    engine: "rule",
    does: "A lookup table built from Regulation (EU) No 1169/2011 decides what is a declarable allergen. Casein resolves to milk, semolina to gluten.",
    survives:
      "The model is never asked whether something is an allergen. That answer is data, not generation.",
  },
  {
    name: "lookup_product",
    engine: "external",
    does: "SerpApi searches the manufacturer's and retailers' own allergen declarations for the exact product.",
    survives:
      "When two sources disagree, the loop escalates. It never averages them.",
  },
  {
    name: "ask_kitchen",
    engine: "human",
    does: "The agent puts a question to a person, because cross-contact is not written on any label and never will be.",
    survives:
      "This is the step that catches shared fryers, shared boards and shared oil.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="border-console-line border-b">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <div className="grid gap-12 lg:grid-cols-[22rem_minmax(0,1fr)] lg:gap-16">
          <div className="lg:sticky lg:top-8 lg:self-start">
            <p className="text-muted-foreground font-mono text-xs tracking-[0.25em] uppercase">
              How it works
            </p>
            <h2 className="font-display mt-5 text-3xl leading-tight font-bold tracking-tight text-balance sm:text-4xl">
              A language model is never the last line of defence.
            </h2>
            <p className="text-muted-foreground mt-5 leading-7">
              Gemma 4 E2B plans the run, reads the label and speaks to the
              diner. It does not decide whether a dish is safe. That call
              belongs to a table you can read, diff and audit — and to a human
              when the table runs out.
            </p>
            <p className="text-muted-foreground mt-4 leading-7">
              We measured E2B failing to escalate on its own when handed an
              unresolved ingredient. So escalation stopped being something we
              hope the model remembers, and became something the orchestrator
              guarantees.
            </p>
          </div>

          <ul className="divide-console-line divide-y">
            {TOOLS.map((tool) => {
              const engine = ENGINE_PRESENTATION[tool.engine];

              return (
                <li key={tool.name} className="py-7 first:pt-0 last:pb-0">
                  <div className="flex flex-wrap items-baseline gap-3">
                    <code className="font-mono text-base font-semibold">
                      {tool.name}
                    </code>
                    <span
                      className={`border px-1.5 font-mono text-[0.65rem] tracking-wider uppercase ${engine.litBorderClass} ${engine.litInkClass}`}
                    >
                      {engine.label}
                    </span>
                  </div>
                  <p className="text-muted-foreground mt-3 leading-7">
                    {tool.does}
                  </p>
                  <p className="border-console-line mt-3 border-l pl-4 text-sm leading-6">
                    {tool.survives}
                  </p>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </section>
  );
}
