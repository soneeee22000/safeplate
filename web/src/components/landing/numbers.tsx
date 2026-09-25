interface Tally {
  label: string;
  value: string;
  source: string;
}

/** Only numbers with a measurement or a line of code behind them. */
const TALLIES: Tally[] = [
  {
    label: "EU allergens in the table",
    value: "14",
    source: "Regulation (EU) No 1169/2011, Annex II",
  },
  {
    label: "Time for a rule decision",
    value: "< 1 ms",
    source: "Every assess and escalate step in the recorded runs",
  },
  {
    label: "Recorded Gemma 4 E2B run",
    value: "~55 s",
    source:
      "Median of six runs end to end on a laptop: most took 46 to 74 s, one took 128 s",
  },
  {
    label: "Dishes cleared without the kitchen",
    value: "0",
    source: "The only path to a clear runs through ask_kitchen",
  },
];

/** Section 5: the measured numbers, printed as a till receipt. */
export function Numbers() {
  return (
    <section className="border-console-line border-b">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 sm:py-20 lg:grid-cols-[minmax(0,1fr)_32rem] lg:items-center lg:gap-16">
        <div>
          <h2 className="font-display text-3xl leading-tight font-bold tracking-tight text-balance sm:text-4xl">
            What was measured
          </h2>
          <p className="text-muted-foreground mt-5 max-w-md leading-7">
            Every safety decision is a table lookup, so it is fast and gives the
            same answer twice. The slow part is the model hearing and speaking,
            and that runs on a laptop.
          </p>
        </div>

        <div>
          <div className="ticket-edge" aria-hidden="true" />
          <dl className="bg-paper text-ink divide-ink/15 divide-y px-5 py-3 sm:px-7">
            {TALLIES.map((tally) => (
              <div
                key={tally.label}
                className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 py-4"
              >
                <dt className="flex items-baseline gap-3 font-semibold">
                  <span>{tally.label}</span>
                  <span
                    className="border-ink/30 min-w-4 flex-1 border-b border-dotted"
                    aria-hidden="true"
                  />
                </dt>
                <dd className="font-display text-2xl font-bold tabular-nums">
                  {tally.value}
                </dd>
                <dd className="text-ink-muted col-span-2 mt-1 text-xs leading-5">
                  {tally.source}
                </dd>
              </div>
            ))}
          </dl>
          <div className="ticket-edge ticket-edge-bottom" aria-hidden="true" />
        </div>
      </div>
    </section>
  );
}
