import padThaiRecording from "@/data/trace-padthai-rules.json";
import type { Trace } from "@/lib/trace";

const SAFE_REPLY = (padThaiRecording as unknown as Trace).explanation;

const MODEL_REOFFER =
  "We can offer you the Pad Thai without any added fish sauce instead.";

const GUARD_SNIPPET = `def contradicts_refusal(text, run):
    if run.verdict != "do_not_serve":
        return False
    lowered = text.lower()
    if not any(p in lowered for p in OFFER_PATTERNS):
        return False
    return not any(p in lowered for p in ALTERNATIVE_PHRASES)`;

const LOOP_SNIPPET = `if assessment.unknown_dish:
    return _forced_escalate(...)   # needs_confirmation
disputed = packaged and _lookup(run, packaged[0], ...)  # SerpApi
if assessment.blocking:
    return _forced_escalate(...)   # do_not_serve
if disputed:
    return _forced_escalate(...)   # do_not_serve
return _ask_kitchen(run)           # the only way to clear`;

/** A short excerpt of real source, labelled with the file it came from. */
function CodeExcerpt({ file, code }: { file: string; code: string }) {
  return (
    <figure className="border-console-line bg-console-raised min-w-0 border">
      <figcaption className="border-console-line text-muted-foreground border-b px-4 py-2 font-mono text-xs">
        {file}
      </figcaption>
      <pre
        tabIndex={0}
        aria-label={`${file} excerpt`}
        className="focus-visible:outline-paper overflow-x-auto px-4 py-4 font-mono text-[0.8rem] leading-6 focus-visible:outline-2"
      >
        <code>{code}</code>
      </pre>
    </figure>
  );
}

/** Section 3: the two measured failures that shaped the design. */
export function Finding() {
  return (
    <section className="border-console-line border-b">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-20">
        <h2 className="font-display max-w-3xl text-3xl leading-tight font-bold tracking-tight text-balance sm:text-4xl">
          The model offered the dish the system had just refused.
        </h2>
        <p className="text-muted-foreground mt-5 max-w-2xl leading-7">
          In testing, Gemma was handed the verdict &ldquo;do not serve&rdquo;
          and the reason: fish sauce is structural to pad thai. It wrote the
          sentence below anyway. A stronger prompt did not stop it, so a
          deterministic check now reads every reply before the diner does.
        </p>

        <div className="mt-10 grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
          <div className="flex flex-col gap-4">
            <div className="border-refuse border-l-2 pl-4">
              <p className="text-muted-foreground text-sm">
                What Gemma wrote, discarded
              </p>
              <p className="decoration-refuse mt-1 text-lg leading-7 line-through decoration-2">
                &ldquo;{MODEL_REOFFER}&rdquo;
              </p>
            </div>
            <div className="border-paper border-l-2 pl-4">
              <p className="text-muted-foreground text-sm">
                What the diner got, assembled from facts
              </p>
              <p className="mt-1 leading-7">{SAFE_REPLY}</p>
            </div>
          </div>
          <CodeExcerpt file="safeplate/voice.py (abridged)" code={GUARD_SNIPPET} />
        </div>

        <div className="border-console-line mt-14 grid grid-cols-[minmax(0,1fr)] gap-6 border-t pt-12 lg:grid-cols-2">
          <div>
            <h3 className="font-display text-2xl leading-tight font-bold tracking-tight text-balance">
              E2B didn&apos;t escalate on its own, so escalation is control
              flow.
            </h3>
            <p className="text-muted-foreground mt-4 leading-7">
              Given an ingredient it could not resolve, the model answered about
              what it did know and stopped. So the loop never asks it whether to
              look something up or call the kitchen. Plain code forces both, and
              the only path that clears a dish runs through the kitchen.
            </p>
          </div>
          <CodeExcerpt
            file="safeplate/loop.py (abridged)"
            code={LOOP_SNIPPET}
          />
        </div>
      </div>
    </section>
  );
}
