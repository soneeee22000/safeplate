import type { Metadata } from "next";
import Link from "next/link";
import { FlaskConical } from "lucide-react";
import { DinerOrder } from "@/components/diner-order";
import { SiteFooter, SiteHeader } from "@/components/site-chrome";

export const metadata: Metadata = {
  title: "Diner view (experiment)",
  description:
    "An experimental diner's screen: ask about a dish, then show the answer to your server.",
};

/** /order — an experimental diner-facing view, kept out of the main nav. */
export default function OrderPage() {
  return (
    <div id="top">
      <SiteHeader />
      <main className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
        <aside className="border-confirm-lit mb-10 flex gap-3 border p-4">
          <FlaskConical
            className="text-confirm-lit mt-0.5 size-5 shrink-0"
            aria-hidden="true"
          />
          <div className="text-sm leading-6">
            <p>
              <span className="text-confirm-lit font-semibold">
                Experiment.
              </span>{" "}
              This diner-facing view departs from the main flow, where the
              server holds the phone. It replays recorded Gemma runs, and every
              ticket is badged as a recording.
            </p>
            <Link
              href="/verify"
              className="hover:text-paper inline-flex min-h-11 items-center underline underline-offset-2"
            >
              Open the server&apos;s screen, the main demo
            </Link>
          </div>
        </aside>
        <header className="mb-10">
          <p className="text-muted-foreground font-mono text-xs tracking-[0.25em] uppercase">
            Ordering companion
          </p>
          <h1 className="font-display mt-4 max-w-2xl text-3xl leading-tight font-bold tracking-tight text-balance sm:text-4xl">
            Ask about a dish, then show your server.
          </h1>
          <p className="text-muted-foreground mt-4 max-w-2xl leading-7">
            It hands you what the dish contains, what cannot be changed, and
            what nobody here can confirm. Show the screen to your server, who
            takes the question to the kitchen.
          </p>
        </header>

        <DinerOrder />
      </main>
      <SiteFooter />
    </div>
  );
}
