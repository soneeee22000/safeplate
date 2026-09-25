/** Section 6: a hedged, three-line note on who would buy this. Not validated. */
export function ProductNote() {
  return (
    <section className="border-console-line border-b">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-20">
        <h2 className="font-display text-2xl leading-tight font-bold tracking-tight sm:text-3xl">
          If this were a product
        </h2>
        <div className="text-muted-foreground mt-5 flex max-w-2xl flex-col gap-3 leading-7">
          <p>
            The buyer would likely be a restaurant group&apos;s food-safety
            lead. EU Regulation 1169/2011 already requires restaurants to give
            allergen information when asked.
          </p>
          <p>
            The job would be giving the same careful answer on every shift, in
            the diner&apos;s language, with a record of why.
          </p>
          <p>
            None of this has been tested with a restaurant. It is a hackathon
            project.
          </p>
        </div>
      </div>
    </section>
  );
}
