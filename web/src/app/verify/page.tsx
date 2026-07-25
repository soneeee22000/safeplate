import type { Metadata } from "next";
import { LiveConsole } from "@/components/live-console";
import { SiteFooter, SiteHeader } from "@/components/site-chrome";

export const metadata: Metadata = {
  title: "Verify a dish — SafePlate",
  description:
    "The operator screen: open a case, watch the agent work, answer the kitchen, read the verdict.",
};

export default function VerifyPage() {
  return (
    <div id="top">
      <SiteHeader />
      <main className="mx-auto max-w-6xl px-6 py-12">
        <header className="mb-10">
          <p className="text-muted-foreground font-mono text-xs tracking-[0.25em] uppercase">
            Operator console
          </p>
          <h1 className="font-display mt-4 max-w-2xl text-3xl leading-tight font-bold tracking-tight text-balance sm:text-4xl">
            Verify a dish.
          </h1>
          <p className="text-muted-foreground mt-4 max-w-2xl leading-7">
            You hold the phone. The diner never touches this, and the chef
            answers one question on your screen.
          </p>
        </header>

        <LiveConsole />
      </main>
      <SiteFooter />
    </div>
  );
}
