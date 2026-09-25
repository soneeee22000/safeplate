import type { ReactNode } from "react";
import {
  History,
  Laptop,
  Loader,
  Radio,
  RotateCcw,
  type LucideIcon,
} from "lucide-react";
import { WAKE_BUDGET_MS } from "@/lib/orchestrator";
import type { AgentConnection } from "@/lib/use-agent-connection";
import type { RecordedWith } from "@/lib/replays";

const WAKE_BUDGET_SECONDS = Math.round(WAKE_BUDGET_MS / 1000);

interface ModeBannerProps {
  connection: AgentConnection;
  /** The engine that recorded the replay on screen, when one is playing. */
  replayRecordedWith: RecordedWith | null;
  onSkip: () => void;
  onRetry: () => void;
  /** Play a recorded Gemma run, so the model in the loop is one tap away. */
  onWatchGemma?: () => void;
}

/** "Recorded run · …" badge text for a recording. */
export function recordedBadge(recordedWith: RecordedWith): string {
  return recordedWith === "gemma"
    ? "Recorded run · Gemma 4 E2B"
    : "Recorded run · rules mode";
}

/**
 * Says plainly what is answering: the hosted agent in rules mode, Gemma on a
 * local machine, or a recording. Never lets a replay pass for a live run.
 */
export function ModeBanner({
  connection,
  replayRecordedWith,
  onSkip,
  onRetry,
  onWatchGemma,
}: ModeBannerProps) {
  if (connection.kind === "connecting") {
    return (
      <Banner
        tone="muted"
        Icon={Loader}
        spin
        title="Checking the live agent…"
      />
    );
  }
  if (connection.kind === "waking") {
    return (
      <Banner
        tone="confirm"
        Icon={Loader}
        spin
        title={`Waking the live agent (free tier, up to ${WAKE_BUDGET_SECONDS} s)…`}
        detail="The hosted agent sleeps when idle. Recorded runs are ready if you would rather not wait."
      >
        <BannerButton onClick={onSkip}>Show recorded runs</BannerButton>
      </Banner>
    );
  }
  if (connection.kind === "live" && replayRecordedWith) {
    return (
      <Banner
        tone="confirm"
        Icon={History}
        title={recordedBadge(replayRecordedWith)}
        detail={`A recording is on the ticket, not the live agent. Pick a case to run it live${connection.mode === "rules" ? " in rules mode" : " with Gemma"}.`}
      />
    );
  }
  if (connection.kind === "live") {
    return <LiveBanner mode={connection.mode} onWatchGemma={onWatchGemma} />;
  }
  return (
    <OfflineBanner
      connection={connection}
      recordedWith={replayRecordedWith}
      onRetry={onRetry}
    />
  );
}

/** The live agent answered /health. */
function LiveBanner({
  mode,
  onWatchGemma,
}: {
  mode: "rules" | "gemma";
  onWatchGemma?: () => void;
}) {
  if (mode === "gemma") {
    return (
      <Banner
        tone="verified"
        Icon={Laptop}
        title="Live · Gemma 4 E2B on this machine"
        detail="Gemma hears and speaks. Code decides every verdict."
      />
    );
  }
  return (
    <Banner
      tone="verified"
      Icon={Radio}
      title="Live · rules mode — Gemma runs locally"
      detail="Gemma 4 E2B is 7.2 GB and runs on a laptop, so this hosted agent reads the request and writes the reply with fixed rules. The decisions are the same code either way. Replies are in English (plus hand-checked safety lines where available); Gemma replies in the diner's language, as the recorded runs show."
    >
      {onWatchGemma && (
        <BannerButton onClick={onWatchGemma}>
          <History className="size-4" aria-hidden="true" />
          Watch a recorded Gemma run
        </BannerButton>
      )}
    </Banner>
  );
}

/** No live agent: say why, and which recording is playing. */
function OfflineBanner({
  connection,
  recordedWith,
  onRetry,
}: {
  connection: Extract<AgentConnection, { kind: "offline" }>;
  recordedWith: RecordedWith | null;
  onRetry: () => void;
}) {
  const title = recordedWith
    ? recordedBadge(recordedWith)
    : "Live agent offline — replaying recorded runs";
  const why =
    connection.reason === "unconfigured"
      ? "This build has no live agent configured."
      : connection.reason === "skipped"
        ? "You chose not to wait for the live agent."
        : connection.reason === "lost"
          ? "The live agent stopped answering."
          : "The live agent did not answer.";

  return (
    <Banner
      tone="confirm"
      Icon={History}
      title={title}
      detail={`${why} Every replay is a real recorded run, badged with the engine that produced it.`}
    >
      {connection.reason !== "unconfigured" && (
        <BannerButton onClick={onRetry}>
          <RotateCcw className="size-4" aria-hidden="true" />
          Try the live agent again
        </BannerButton>
      )}
    </Banner>
  );
}

const TONES = {
  muted: "border-console-line text-muted-foreground",
  confirm: "border-confirm text-confirm-lit",
  verified: "border-verified text-verified-lit",
} as const;

/** The banner frame shared by every state. */
function Banner({
  tone,
  Icon,
  spin = false,
  title,
  detail,
  children,
}: {
  tone: keyof typeof TONES;
  Icon: LucideIcon;
  spin?: boolean;
  title: string;
  detail?: string;
  children?: ReactNode;
}) {
  return (
    <div className={`border px-3 py-3 ${TONES[tone]}`} role="status">
      <p className="flex items-center gap-2 font-mono text-xs leading-5 font-semibold">
        <Icon
          className={`size-4 shrink-0 ${spin ? "animate-spin" : ""}`}
          aria-hidden="true"
        />
        {title}
      </p>
      {detail && (
        <p className="text-muted-foreground mt-1.5 text-xs leading-5">
          {detail}
        </p>
      )}
      {children}
    </div>
  );
}

/** A small action inside a banner, still 44px tall. */
function BannerButton({
  onClick,
  children,
}: {
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="border-console-line text-paper hover:border-paper mt-2 flex min-h-11 items-center gap-2 border px-3 font-mono text-xs tracking-wider uppercase"
    >
      {children}
    </button>
  );
}
