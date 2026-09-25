import Link from "next/link";
import { Award } from "lucide-react";
import { HeroTicket } from "@/components/landing/hero-ticket";
import { REPO_URL } from "@/components/site-chrome";

/** Opening section: the one-line thesis, the scene, and a real refusal ticket. */
export function Hero() {
  return (
    <section className="border-console-line border-b">
      <div className="mx-auto grid max-w-6xl gap-12 px-4 pt-12 pb-16 sm:px-6 sm:pt-20 lg:grid-cols-[minmax(0,1fr)_26rem] lg:items-center lg:gap-16 lg:pb-24">
        <div>
          <p className="text-paper/85 mb-5 font-mono text-xs tracking-widest uppercase sm:text-sm">
            Hackathon project · Allergen agent for restaurant servers
          </p>
          <h1 className="font-display max-w-3xl text-[2.6rem] leading-[1.02] font-bold tracking-tight text-balance sm:text-6xl lg:text-7xl">
            The model hears and speaks. The code decides.
          </h1>
          <p className="text-muted-foreground mt-6 max-w-xl text-lg leading-8">
            Can this diner eat this dish? SafePlate is an allergen agent on
            Gemma 4 E2B. A server holds the phone, a diner asks in their own
            language, and the agent answers or refuses with a reason. It never
            calls a dish safe by default.
          </p>

          <div className="mt-9 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
            <Link
              href="/verify"
              className="bg-paper text-console hover:bg-paper-shade flex min-h-12 items-center justify-center px-6 font-semibold transition-colors"
            >
              Try the demo
            </Link>
            <a
              href={REPO_URL}
              target="_blank"
              rel="noreferrer"
              className="border-console-line hover:border-paper flex min-h-12 items-center justify-center border px-6 font-semibold transition-colors"
            >
              Read the code
            </a>
          </div>
          <p className="text-muted-foreground mt-4 max-w-xl text-sm leading-6">
            The demo replays real recorded runs step by step. Gemma 4 E2B is a
            7.2 GB model that runs on a laptop; clone the repo to run the agent
            yourself.
          </p>

          <p className="text-paper/85 mt-8 flex items-center gap-2 text-sm">
            <Award
              className="text-serp-lit size-4 shrink-0"
              aria-hidden="true"
            />
            SerpApi recognition award · Gemma 4 Hackathon Paris
          </p>
        </div>

        <HeroTicket />
      </div>
    </section>
  );
}
