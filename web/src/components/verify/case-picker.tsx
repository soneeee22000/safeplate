"use client";

import { useCallback, useRef, useState } from "react";
import { Mic, Square } from "lucide-react";
import type { AgentMode, CaseRequest } from "@/lib/orchestrator";
import { PRESET_CASES, type PresetCase } from "@/lib/replays";

interface CasePickerProps {
  /** A preset was chosen: run it live, or play its own recording. */
  onPreset: (preset: PresetCase) => void;
  /** Free text or audio from the operator. */
  onRequest: (request: CaseRequest) => void;
  disabled: boolean;
  /** True while the agent is working on a case, as opposed to waiting on anyone. */
  checking: boolean;
  /** The live agent's mode, or null when only recordings can play. */
  liveMode: AgentMode | null;
}

/**
 * What the diner asked. Presets exercise the whole story; free text goes to
 * the live agent verbatim, or to the closest recording when it is offline.
 */
export function CasePicker({
  onPreset,
  onRequest,
  disabled,
  checking,
  liveMode,
}: CasePickerProps) {
  const [text, setText] = useState("");

  return (
    <div className="border-console-line border p-5 sm:p-6">
      <h2 className="font-display text-xl font-semibold">
        What did the diner ask?
      </h2>

      <p className="text-muted-foreground mt-4 font-mono text-xs tracking-widest uppercase">
        Cases
      </p>
      <ul className="mt-2 grid gap-2">
        {PRESET_CASES.map((preset) => (
          <li key={preset.id}>
            <PresetButton
              preset={preset}
              disabled={disabled}
              onClick={() => {
                setText(preset.text);
                onPreset(preset);
              }}
            />
          </li>
        ))}
      </ul>

      <FreeText
        value={text}
        onChange={setText}
        disabled={disabled}
        checking={checking}
        liveMode={liveMode}
        onSubmit={() => onRequest({ text: text.trim() })}
      />

      {liveMode === "gemma" && (
        <Recorder
          disabled={disabled}
          onAudio={(audio) => onRequest({ audio })}
        />
      )}
    </div>
  );
}

/** One preset case: the diner's words and what it demonstrates. */
function PresetButton({
  preset,
  disabled,
  onClick,
}: {
  preset: PresetCase;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="border-console-line hover:border-paper bg-console-raised flex min-h-14 w-full flex-col items-start gap-1 border px-3 py-2.5 text-left transition-colors disabled:opacity-40"
    >
      <span className="text-paper text-sm leading-5">“{preset.text}”</span>
      <span className="text-muted-foreground font-mono text-xs tracking-wider uppercase">
        {preset.shows}
      </span>
    </button>
  );
}

/** The typed request, sent verbatim. */
function FreeText({
  value,
  onChange,
  disabled,
  checking,
  liveMode,
  onSubmit,
}: {
  value: string;
  onChange: (next: string) => void;
  disabled: boolean;
  checking: boolean;
  liveMode: AgentMode | null;
  onSubmit: () => void;
}) {
  return (
    <form
      className="mt-5"
      onSubmit={(event) => {
        event.preventDefault();
        if (value.trim()) onSubmit();
      }}
    >
      <label
        htmlFor="diner-request"
        className="text-muted-foreground font-mono text-xs tracking-widest uppercase"
      >
        Or type it, in the diner&apos;s words
      </label>
      <textarea
        id="diner-request"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={3}
        maxLength={500}
        placeholder="I'm allergic to fish — can I have the pad thai without fish sauce?"
        className="border-console-line bg-console-raised text-paper placeholder:text-muted-foreground focus-visible:border-paper mt-2 w-full resize-none border px-3 py-3 text-base outline-none"
      />
      {!liveMode && (
        <p className="text-confirm-lit mt-1 font-mono text-xs leading-5">
          Demo mode — typed text plays the closest recorded run.
        </p>
      )}
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        className="bg-paper text-console hover:bg-paper-shade mt-3 min-h-12 w-full px-5 font-mono text-sm tracking-wider uppercase transition-colors disabled:opacity-40"
      >
        {checking ? "Checking…" : "Check it"}
      </button>
    </form>
  );
}

/** Voice input, offered only when the live agent has Gemma loaded to hear it. */
function Recorder({
  disabled,
  onAudio,
}: {
  disabled: boolean;
  onAudio: (audio: Blob) => void;
}) {
  const [recording, setRecording] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);

  const start = useCallback(async () => {
    setMicError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      recorder.ondataavailable = (event) => chunks.push(event.data);
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        onAudio(new Blob(chunks, { type: recorder.mimeType }));
      };
      recorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      setMicError("No microphone available. Type the request instead.");
    }
  }, [onAudio]);

  const stop = useCallback(() => {
    recorderRef.current?.stop();
    setRecording(false);
  }, []);

  const Icon = recording ? Square : Mic;
  return (
    <div className="mt-4">
      <button
        type="button"
        onClick={recording ? stop : start}
        disabled={disabled && !recording}
        aria-pressed={recording}
        className={`flex min-h-12 w-full items-center justify-center gap-2 border px-5 font-mono text-xs tracking-wider uppercase disabled:opacity-40 ${
          recording ? "border-refuse text-refuse" : "border-paper text-paper"
        }`}
      >
        <Icon className="size-4" aria-hidden="true" />
        {recording ? "Stop and send" : "Record the diner · Gemma hears it"}
      </button>
      {micError && (
        <p className="text-confirm-lit mt-2 font-mono text-xs">{micError}</p>
      )}
    </div>
  );
}
