"use client";

import { useRef, useState } from "react";
import {
  DINER_LANGUAGES,
  EU_ALLERGENS,
  type CaseRequest,
} from "@/lib/orchestrator";

interface CaseFormProps {
  onSubmit: (request: CaseRequest) => void;
  disabled: boolean;
  liveBackend: boolean;
}

const FIELD_CLASSES =
  "border-console-line bg-console-raised text-paper focus-visible:border-paper w-full border px-3 py-3 text-base outline-none";

/**
 * What the server fills in before the agent starts: which allergen the diner
 * asked about, what language to answer in, and a photo of the label.
 */
export function CaseForm({ onSubmit, disabled, liveBackend }: CaseFormProps) {
  const [allergen, setAllergen] = useState<string>(EU_ALLERGENS[0]);
  const [language, setLanguage] = useState<string>(DINER_LANGUAGES[0].code);
  const [image, setImage] = useState<File | undefined>();
  const fileInput = useRef<HTMLInputElement>(null);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    onSubmit({ allergen, diner_language: language, image });
  }

  return (
    <form onSubmit={handleSubmit} className="border-console-line border p-6">
      <h2 className="font-display text-xl font-semibold">Open a case</h2>
      <p className="text-muted-foreground mt-1 text-sm leading-6">
        The diner asked. Photograph the label and let the agent do the rest.
      </p>

      <div className="mt-6 space-y-5">
        <div>
          <label
            htmlFor="allergen"
            className="text-muted-foreground block font-mono text-xs tracking-wider uppercase"
          >
            Allergen asked about
          </label>
          <select
            id="allergen"
            value={allergen}
            onChange={(event) => setAllergen(event.target.value)}
            className={`${FIELD_CLASSES} mt-2`}
          >
            {EU_ALLERGENS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="language"
            className="text-muted-foreground block font-mono text-xs tracking-wider uppercase"
          >
            Answer the diner in
          </label>
          <select
            id="language"
            value={language}
            onChange={(event) => setLanguage(event.target.value)}
            className={`${FIELD_CLASSES} mt-2`}
          >
            {DINER_LANGUAGES.map((item) => (
              <option key={item.code} value={item.code}>
                {item.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="label-photo"
            className="text-muted-foreground block font-mono text-xs tracking-wider uppercase"
          >
            Label photo
          </label>
          <input
            id="label-photo"
            ref={fileInput}
            type="file"
            accept="image/*"
            capture="environment"
            onChange={(event) => setImage(event.target.files?.[0])}
            className={`${FIELD_CLASSES} mt-2 file:mr-3 file:border-0 file:bg-transparent file:font-mono file:text-xs file:uppercase`}
          />
          {!liveBackend && (
            <p className="text-muted-foreground mt-2 text-xs leading-5">
              The orchestrator is not running, so a recorded label stands in for
              the photo.
            </p>
          )}
        </div>
      </div>

      <button
        type="submit"
        disabled={disabled}
        className="bg-paper text-console hover:bg-paper-shade mt-7 min-h-12 w-full px-5 font-mono text-sm tracking-wider uppercase transition-colors disabled:opacity-40"
      >
        {disabled ? "Case in progress" : "Verify this dish"}
      </button>
    </form>
  );
}
