"use client";

import { useCallback, useRef, useState } from "react";

export interface CaseRequest {
  text?: string;
  audio?: Blob;
}

interface RequestFormProps {
  onSubmit: (request: CaseRequest) => void;
  disabled: boolean;
  liveBackend: boolean;
}

const EXAMPLES = [
  "I'm allergic to fish. Can you make the pad thai without fish sauce?",
  "My son has a peanut allergy — can he eat the pad thai?",
  "I can't eat sesame. Is the falafel plate okay?",
  "Je ne mange pas de produits laitiers, la carbonara c'est possible ?",
];

/**
 * What the diner says, in their own words. Not a dropdown: "can you do it
 * without the fish sauce" is a request a menu filter cannot represent, and
 * working out what it means is Gemma's job.
 */
export function RequestForm({
  onSubmit,
  disabled,
  liveBackend,
}: RequestFormProps) {
  const [text, setText] = useState("");
  const [recording, setRecording] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = useCallback(async () => {
    setMicError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];

      recorder.ondataavailable = (event) => chunksRef.current.push(event.data);
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        onSubmit({
          audio: new Blob(chunksRef.current, { type: recorder.mimeType }),
        });
      };

      recorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      setMicError("No microphone available. Type the request instead.");
    }
  }, [onSubmit]);

  const stopRecording = useCallback(() => {
    recorderRef.current?.stop();
    setRecording(false);
  }, []);

  return (
    <div className="border-console-line border p-6">
      <h2 className="font-display text-xl font-semibold">
        What did the diner say?
      </h2>
      <p className="text-muted-foreground mt-1 text-sm leading-6">
        Any language. Gemma hears it, works out the dish and the restriction,
        and starts the check.
      </p>

      <button
        type="button"
        onClick={recording ? stopRecording : startRecording}
        disabled={disabled}
        aria-pressed={recording}
        className={`mt-5 flex min-h-14 w-full items-center justify-center gap-3 border px-5 font-mono text-sm tracking-wider uppercase transition-colors disabled:opacity-40 ${
          recording
            ? "border-refuse text-refuse"
            : "border-paper text-paper hover:bg-paper hover:text-console"
        }`}
      >
        <span
          className={`h-3 w-3 rounded-full ${recording ? "bg-refuse animate-pulse" : "bg-paper"}`}
          aria-hidden="true"
        />
        {recording ? "Stop and send" : "Hold the phone up · record"}
      </button>

      {micError && (
        <p className="text-confirm-lit mt-2 font-mono text-xs leading-5">
          {micError}
        </p>
      )}

      <div className="my-5 flex items-center gap-3">
        <span className="bg-console-line h-px flex-1" aria-hidden="true" />
        <span className="text-muted-foreground font-mono text-[0.65rem] tracking-widest uppercase">
          or type it
        </span>
        <span className="bg-console-line h-px flex-1" aria-hidden="true" />
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (text.trim()) onSubmit({ text: text.trim() });
        }}
      >
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={3}
          placeholder="I'm allergic to fish. Can you make the pad thai without fish sauce?"
          aria-label="What the diner said"
          className="border-console-line bg-console-raised text-paper placeholder:text-muted-foreground focus-visible:border-paper w-full resize-none border px-3 py-3 text-base outline-none"
        />

        <button
          type="submit"
          disabled={disabled || !text.trim()}
          className="bg-paper text-console hover:bg-paper-shade mt-3 min-h-12 w-full px-5 font-mono text-sm tracking-wider uppercase transition-colors disabled:opacity-40"
        >
          {disabled ? "Checking" : "Check it"}
        </button>
      </form>

      <div className="mt-6">
        <p className="text-muted-foreground font-mono text-[0.65rem] tracking-widest uppercase">
          Try one
        </p>
        <ul className="mt-2 space-y-1">
          {EXAMPLES.map((example) => (
            <li key={example}>
              <button
                type="button"
                onClick={() => setText(example)}
                disabled={disabled}
                className="text-muted-foreground hover:text-paper py-1 text-left text-xs leading-5 transition-colors disabled:opacity-40"
              >
                {example}
              </button>
            </li>
          ))}
        </ul>
      </div>

      {!liveBackend && (
        <p className="border-confirm text-confirm-lit mt-5 border-l-2 pl-3 font-mono text-xs leading-5">
          Orchestrator offline — a recorded case will play instead.
        </p>
      )}
    </div>
  );
}
