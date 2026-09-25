"""The diner speaks; Gemma hears and works out what is actually being asked.

Ollama's native `/api/chat` silently drops audio fields — it returns 200 and the
model politely asks for the audio it never received. The OpenAI-compatible
endpoint accepts `input_audio` content parts and does deliver them, so this
module talks to that endpoint instead. Verified against gemma4:e2b on Ollama
0.32.3: a spoken English request transcribed correctly in 10.1s.

One call does transcription *and* intent extraction. Splitting them would mean
two round trips through a small model and a lost opportunity: the model resolves
"without the fish sauce" against the dish it just heard named, which a
transcribe-then-parse pipeline has to rediscover.
"""

from __future__ import annotations

import base64
import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from .config import GENERATION_TEMPERATURE, MODEL_NAME

OPENAI_CHAT_URL = "http://127.0.0.1:11434/v1/chat/completions"
REQUEST_TIMEOUT_SECONDS = 240

SYSTEM_PROMPT = """\
You are the intake step of a restaurant allergen agent. A diner is speaking, \
possibly not in English.

Return ONLY a JSON object, no prose, with exactly these keys:
  "utterance"    - verbatim transcription, in the language spoken
  "language"     - ISO 639-1 code of the language spoken
  "dish"         - the dish named, lowercase English, or null
  "avoid"        - array of ingredients or foods to avoid, lowercase English
  "request_type" - one of: "modification", "question", "declaration"
  "notes"        - anything else the kitchen should know, or null

Rules:
- "avoid" holds what the diner cannot or will not eat. Translate to English.
- "avoid" must NEVER be empty when the diner states an allergy or an intolerance.
  "I have a tree nut allergy" -> ["tree nuts"]. "I am coeliac" -> ["gluten"].
  "I cannot eat dairy" -> ["dairy"]. "no shellfish for me" -> ["shellfish"].
  Extract the food even when the sentence is phrased as a condition rather than
  as a request.
- "modification" means they asked for the dish changed. "question" means they \
asked whether something is present. "declaration" means they only stated a \
restriction.
- If you did not clearly hear a dish name, set "dish" to null. Do not guess.
- Never invent an allergen that was not spoken.
"""


class SpeechError(RuntimeError):
    """Raised when the audio could not be turned into a usable request."""


@dataclass
class Intent:
    """What the diner asked for, as structured data the loop can act on."""

    utterance: str
    language: str
    dish: str | None
    avoid: list[str] = field(default_factory=list)
    request_type: str = "question"
    notes: str | None = None
    #: Words the diner gave as allergies that could not be matched to one. The
    #: loop stops on any, rather than check the dish against a partial list.
    unrecognised: list[str] = field(default_factory=list)

    @property
    def actionable(self) -> bool:
        """False when the agent lacks the two things it needs to check anything."""
        return bool(self.dish) and bool(self.avoid)


def _post(payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        OPENAI_CHAT_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise SpeechError(f"Ollama returned {error.code}: {error.read().decode()[:200]}") from error
    except OSError as error:
        raise SpeechError(f"Ollama unreachable at {OPENAI_CHAT_URL}: {error}") from error


def _content(reply: dict[str, Any]) -> str:
    try:
        return reply["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as error:
        raise SpeechError(f"unexpected response shape: {reply}") from error


def _close_unterminated(text: str) -> str:
    """Append the closers a truncated JSON object is missing.

    E2B reliably drops the final brace before its closing code fence — it emits
    `"notes": null` and stops. The content is complete; only the punctuation is
    not, so repairing it beats discarding a good answer.
    """
    depth_curly = depth_square = 0
    in_string = escaped = False

    for character in text:
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if character == "{":
            depth_curly += 1
        elif character == "}":
            depth_curly -= 1
        elif character == "[":
            depth_square += 1
        elif character == "]":
            depth_square -= 1

    return text + ("]" * max(0, depth_square)) + ("}" * max(0, depth_curly))


def _parse_intent(raw: str) -> Intent:
    """Pull the JSON object out of the reply, tolerating fenced or truncated output."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1].removeprefix("json").strip()
    text = text.removesuffix("```").strip()

    start = text.find("{")
    if start == -1:
        raise SpeechError(f"no JSON object in reply: {raw[:200]}")

    candidate = _close_unterminated(text[start:].rstrip().rstrip(","))

    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as error:
        raise SpeechError(f"malformed JSON from model: {candidate[:200]}") from error

    avoid = data.get("avoid") or []
    if isinstance(avoid, str):
        avoid = [avoid]

    return Intent(
        utterance=str(data.get("utterance") or "").strip(),
        language=str(data.get("language") or "en").strip().lower()[:5],
        dish=(str(data["dish"]).strip().lower() if data.get("dish") else None),
        avoid=[str(item).strip().lower() for item in avoid if str(item).strip()],
        request_type=str(data.get("request_type") or "question").strip().lower(),
        notes=(str(data["notes"]).strip() if data.get("notes") else None),
    )


#: Formats Ollama's `input_audio` accepts. Anything else is converted first —
#: handing it webm does not error, it hangs until the request times out, which
#: costs four minutes and looks like a dead model rather than a bad format.
NATIVE_AUDIO_FORMATS = frozenset({"wav", "mp3"})

CONVERT_TIMEOUT_SECONDS = 30


def to_wav(audio: bytes, source_format: str) -> bytes:
    """Transcode browser audio to 16 kHz mono WAV via ffmpeg.

    Browsers record webm/opus or mp4/aac; neither reaches the model intact. Mono
    at 16 kHz is what speech models want and keeps the base64 payload small.

    Returns the input unchanged if ffmpeg is unavailable, so a machine without it
    still fails with the model's own error rather than a missing-binary one.
    """
    if source_format in NATIVE_AUDIO_FORMATS:
        return audio

    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-f", source_format, "-i", "pipe:0",
             "-ac", "1", "-ar", "16000", "-f", "wav", "pipe:1"],
            input=audio, capture_output=True, timeout=CONVERT_TIMEOUT_SECONDS, check=True,
        )
        return result.stdout
    except (OSError, subprocess.SubprocessError):
        return audio


def understand_audio(audio: bytes, *, audio_format: str = "wav") -> Intent:
    """Transcribe spoken audio and extract the diner's request in one call.

    Args:
        audio: Raw audio bytes as captured from the diner.
        audio_format: Container format, e.g. ``wav`` or ``mp3``.

    Returns:
        The structured request.

    Raises:
        SpeechError: If Ollama is unreachable or the reply is not usable JSON.
    """
    audio = to_wav(audio, audio_format.lower())
    encoded = base64.b64encode(audio).decode()
    reply = _post(
        {
            "model": MODEL_NAME,
            "temperature": GENERATION_TEMPERATURE,
            "stream": False,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Transcribe and structure this request."},
                        {
                            "type": "input_audio",
                            "input_audio": {"data": encoded, "format": "wav"},
                        },
                    ],
                },
            ],
        }
    )
    return _parse_intent(_content(reply))


def understand_text(utterance: str) -> Intent:
    """Same extraction for typed input, so the agent works without a microphone."""
    reply = _post(
        {
            "model": MODEL_NAME,
            "temperature": GENERATION_TEMPERATURE,
            "stream": False,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": utterance},
            ],
        }
    )
    return _parse_intent(_content(reply))
