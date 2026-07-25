import type { Metadata } from "next";
import { DinerOrder } from "@/components/diner-order";
import { SiteFooter, SiteHeader } from "@/components/site-chrome";

export const metadata: Metadata = {
  title: "Order for yourself — SafePlate",
  description:
    "The diner's screen: ask about a dish in your own language and get choices, not a verdict.",
};

export default function OrderPage() {
  return (
    <div id="top">
      <SiteHeader />
      <main className="mx-auto max-w-6xl px-6 py-12">
        <header className="mb-10">
          <p className="text-muted-foreground font-mono text-xs tracking-[0.25em] uppercase">
            Ordering companion
          </p>
          <h1 className="font-display mt-4 max-w-2xl text-3xl leading-tight font-bold tracking-tight text-balance sm:text-4xl">
            Ask about the food yourself.
          </h1>
          <p className="text-muted-foreground mt-4 max-w-2xl leading-7">
            At the table or at the counter, with a waiter or without one. It
            hands you what the dish contains, what cannot be changed, and what
            nobody here can confirm — then you decide.
          </p>
        </header>

        <DinerOrder />
      </main>
      <SiteFooter />
    </div>
  );
}
