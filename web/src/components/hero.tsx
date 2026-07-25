const STATS = [
  { value: "14", label: "EU declarable allergens" },
  { value: "4", label: "languages, or just speak" },
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
          The vegan dish is full of nuts.
        </h1>

        <p className="text-muted-foreground mt-7 max-w-2xl text-lg leading-8">
          Symphony.fr&apos;s <em>Gnocchis pesto vegan</em> contains pignons de
          pin — pine nuts. They are in the ingredient list but not in the bold
          allergen text, and a diner avoiding nuts reads &ldquo;vegan&rdquo; and
          stops reading. That is the lunch this hackathon was served. SafePlate
          hears the diner in their own language, checks the label, asks the
          kitchen what no label can answer, and refuses when it cannot be sure.
        </p>

        <div className="mt-10 flex flex-wrap items-center gap-4">
          <a
            href="/order"
            className="bg-paper text-console hover:bg-paper-shade flex min-h-14 items-center px-8 font-mono text-sm tracking-widest uppercase transition-colors"
          >
            Try it — ask about a dish
          </a>
          <a
            href="/verify"
            className="border-console-line text-muted-foreground hover:border-paper hover:text-paper flex min-h-14 items-center border px-6 font-mono text-sm tracking-widest uppercase transition-colors"
          >
            Staff console
          </a>
        </div>

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
