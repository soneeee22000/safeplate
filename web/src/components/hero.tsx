const STATS = [
  { value: "14", label: "EU declarable allergens" },
  { value: "5", label: "tools the agent can call" },
  { value: "0", label: "verdicts left to the model" },
];

export function Hero() {
  return (
    <section className="border-console-line border-b">
      <div className="mx-auto max-w-6xl px-6 pt-16 pb-14 sm:pt-24 sm:pb-20">
        <p className="text-muted-foreground font-mono text-xs tracking-[0.25em] uppercase">
          Gemma 4 Hackathon · Paris · Track 2 — Autonomous Agents
        </p>

        <h1 className="font-display mt-6 max-w-4xl text-4xl leading-[1.05] font-bold tracking-tight text-balance sm:text-6xl lg:text-7xl">
          The label says nothing about the fryer.
        </h1>

        <p className="text-muted-foreground mt-7 max-w-2xl text-lg leading-8">
          A diner asks whether a dish contains peanuts. The label is in French,
          the diner reads Arabic, and the one fact that matters — that the
          falafel shares a fryer with the peanut-crusted chicken — is not
          written anywhere. SafePlate is an agent that goes looking for it, and
          refuses to clear the dish until it has an answer.
        </p>

        <dl className="mt-12 flex flex-wrap gap-x-12 gap-y-6">
          {STATS.map((stat) => (
            <div key={stat.label}>
              <dt className="sr-only">{stat.label}</dt>
              <dd>
                <span className="font-display block text-4xl font-bold tabular-nums">
                  {stat.value}
                </span>
                <span className="text-muted-foreground mt-1 block font-mono text-xs tracking-wider uppercase">
                  {stat.label}
                </span>
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
