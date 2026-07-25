import { EvidenceTicket } from "@/components/evidence-ticket";
import { Hero } from "@/components/hero";
import { HowItWorks } from "@/components/how-it-works";
import { SiteFooter, SiteHeader } from "@/components/site-chrome";
import { Team } from "@/components/team";
import refusalCase from "@/data/trace-refusal.json";
import verifiedCase from "@/data/trace-verified.json";
import type { Trace } from "@/lib/trace";

const CASES: Trace[] = [refusalCase as Trace, verifiedCase as Trace];

export default function Home() {
  return (
    <div id="top">
      <SiteHeader />
      <main>
        <Hero />

        <section id="run" className="border-console-line border-b">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <div className="mb-10 flex flex-wrap items-end justify-between gap-6">
              <div>
                <p className="text-muted-foreground font-mono text-xs tracking-[0.25em] uppercase">
                  A recorded run
                </p>
                <h2 className="font-display mt-5 max-w-2xl text-3xl leading-tight font-bold tracking-tight text-balance sm:text-4xl">
                  Watch it refuse a dish the label called safe.
                </h2>
              </div>
              <p className="text-muted-foreground max-w-sm text-sm leading-6">
                These are real traces, replayed. The agent itself runs locally
                on Gemma 4 E2B with Tesseract and a live SerpApi lookup — a
                7.2&nbsp;GB model that cannot be hosted on this page.
              </p>
            </div>

            <EvidenceTicket cases={CASES} />
          </div>
        </section>

        <HowItWorks />
        <Team />
      </main>
      <SiteFooter />
    </div>
  );
}
