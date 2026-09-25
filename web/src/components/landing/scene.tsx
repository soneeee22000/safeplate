import symphonyRecordings from "@/data/symphony-cases.json";
import { recordedBadge } from "@/components/verify/mode-banner";
import type { Trace } from "@/lib/trace";

interface RecordedRequest extends Trace {
  request: string;
}

const CELERY_REQUEST =
  "Je suis allergique au celeri. Les pates bolognaises, c'est possible ?";

const RECORDING = (symphonyRecordings as unknown as RecordedRequest[]).find(
  (recording) => recording.request === CELERY_REQUEST,
);

interface Beat {
  who: string;
  what: string;
}

/** The scene at the table. A real sequence, so the beats are ordered. */
const BEATS: Beat[] = [
  {
    who: "The diner",
    what: "asks in their own language, out loud or typed, whether they can eat a dish.",
  },
  {
    who: "The agent",
    what: "checks the dish table and the EU-14 allergens, looks up packaged ingredients with SerpApi, and puts one question to the kitchen when the dish could be cleared.",
  },
  {
    who: "The server",
    what: "reads back the answer in the diner's language, or a refusal with the reason. Most often: do not serve, I can't confirm.",
  },
];

/** Section 2: who is at the table, and one real exchange from a recording. */
export function Scene() {
  return (
    <section className="border-console-line border-b">
      <div className="mx-auto grid max-w-6xl gap-12 px-4 py-16 sm:px-6 sm:py-20 lg:grid-cols-2 lg:gap-16">
        <div>
          <h2 className="font-display text-3xl leading-tight font-bold tracking-tight text-balance sm:text-4xl">
            A diner asks. The server holds the phone.
          </h2>
          <ol className="mt-8 flex flex-col gap-6">
            {BEATS.map((beat, index) => (
              <li key={beat.who} className="flex gap-4">
                <span className="border-console-line text-muted-foreground flex size-8 shrink-0 items-center justify-center border font-mono text-sm tabular-nums">
                  {index + 1}
                </span>
                <p className="leading-7">
                  <span className="font-semibold">{beat.who}</span>{" "}
                  <span className="text-muted-foreground">{beat.what}</span>
                </p>
              </li>
            ))}
          </ol>
        </div>

        {RECORDING && <Exchange recording={RECORDING} />}
      </div>
    </section>
  );
}

/** The diner's question and the agent's reply, as recorded with Gemma. */
function Exchange({ recording }: { recording: RecordedRequest }) {
  return (
    <figure className="bg-console-raised border-console-line self-start border p-5 sm:p-7">
      <p className="text-gemma-lit font-mono text-xs">
        {recordedBadge("gemma")}
      </p>

      <div className="mt-5">
        <p className="text-muted-foreground text-sm">Diner, in French</p>
        <p lang="fr" className="font-display mt-1 text-xl leading-snug">
          &ldquo;Je suis allergique au céleri. Les pâtes bolognaises, c&apos;est
          possible&nbsp;?&rdquo;
        </p>
      </div>

      <div className="border-console-line mt-6 border-t pt-6">
        <p className="text-muted-foreground text-sm">
          Agent, back in French. The verdict was fixed by code first.
        </p>
        <p lang="fr" className="mt-1 leading-7">
          {recording.explanation}
        </p>
        <p className="text-muted-foreground mt-3 text-sm leading-6">
          {recording.explanation_en}
        </p>
      </div>

      <figcaption className="border-console-line mt-6 border-t pt-5">
        <span className="bg-paper border-refuse text-refuse font-display inline-block -rotate-2 border-[3px] px-3 py-1 text-lg font-bold uppercase">
          Do not serve
        </span>
      </figcaption>
    </figure>
  );
}
