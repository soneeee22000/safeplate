import type { Metadata } from "next";
import { LiveConsole } from "@/components/live-console";
import { SiteFooter, SiteHeader } from "@/components/site-chrome";

export const metadata: Metadata = {
  title: "Verify a dish",
  description:
    "The server's screen: a diner asks if they can eat a dish, the agent checks it, asks the kitchen one question, and answers or refuses with a reason.",
};

/** /verify — the single place the live agent runs. */
export default function VerifyPage() {
  return (
    <div id="top">
      <SiteHeader />
      <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-12">
        <header className="mb-8 sm:mb-10">
          <p className="text-muted-foreground font-mono text-xs tracking-[0.25em] uppercase">
            Front of house
          </p>
          <h1 className="font-display mt-4 max-w-2xl text-3xl leading-tight font-bold tracking-tight text-balance sm:text-4xl">
            Verify a dish.
          </h1>
          <p className="text-muted-foreground mt-4 max-w-2xl leading-7">
            You are the server holding the phone. The diner asks, in their own
            language, whether they can eat a dish. The agent checks the dish
            table and the EU-14 allergens, looks up packaged ingredients, and
            puts one question to the kitchen. Then it answers, or refuses with a
            reason. It never calls a dish safe by default.
          </p>
        </header>

        <LiveConsole />
      </main>
      <SiteFooter />
    </div>
  );
}
