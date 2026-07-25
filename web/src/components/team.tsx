interface Member {
  name: string;
  owns: string;
  detail: string;
}

const TEAM: Member[] = [
  {
    name: "Yan",
    owns: "Agent loop · tool registry",
    detail:
      "Built the control flow and the forced-escalation branches — the part that makes the agent reliable without asking the model to be.",
  },
  {
    name: "Afaq",
    owns: "SerpApi · orchestrator",
    detail:
      "Product lookup against manufacturer and retailer declarations, response normalisation, and the fixture cache that lets the demo run offline.",
  },
  {
    name: "Rita",
    owns: "Product · interface",
    detail:
      "The staff journey and the ticket: how a verdict and its evidence reach a server who has ninety seconds and a full room.",
  },
  {
    name: "Pyae",
    owns: "Gemma 4 · EU-14 table · eval",
    detail:
      "Label reading into structured ingredients, the allergen table and its synonyms, and the eval set — including two labels built to be unresolvable, so refusal is measured rather than assumed.",
  },
];

export function Team() {
  return (
    <section id="team" className="border-console-line border-b">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <p className="text-muted-foreground font-mono text-xs tracking-[0.25em] uppercase">
          The team
        </p>
        <h2 className="font-display mt-5 max-w-3xl text-3xl leading-tight font-bold tracking-tight text-balance sm:text-4xl">
          Four people, one day, at 42 Paris.
        </h2>

        <ul className="mt-12 grid gap-x-10 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
          {TEAM.map((member) => (
            <li key={member.name} className="border-paper border-t pt-5">
              <h3 className="font-display text-xl font-semibold">
                {member.name}
              </h3>
              <p className="text-muted-foreground mt-1 font-mono text-xs tracking-wider uppercase">
                {member.owns}
              </p>
              <p className="text-muted-foreground mt-4 text-sm leading-6">
                {member.detail}
              </p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
