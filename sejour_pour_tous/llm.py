"""Local Gemma access over Ollama's HTTP API — thinking disabled.

Gemma 4 E2B emits a full chain-of-thought on every call. Ollama routes those tokens to a
separate ``thinking`` field the user never sees, so they cost seconds and produce nothing;
capping ``num_predict`` makes it worse, returning empty content once the budget is spent
before the answer starts. Passing ``think: false`` removed roughly two thirds of the
latency in measurement (understanding 37.5s -> 12.5s, explanation 23s -> 13.3s).

The installed ``ollama`` Python client (0.4.7) has no ``think`` parameter, so this module
speaks to the daemon directly with the standard library. No new dependency, and nothing
leaves the machine: the endpoint is loopback.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from .config import GENERATION_TEMPERATURE, MODEL_NAME

OLLAMA_CHAT_URL: str = "http://127.0.0.1:11434/api/chat"
KEEP_ALIVE: str = "30m"  # hold the 7.2GB model in RAM across a demo
REQUEST_TIMEOUT_SECONDS: int = 180


class LocalModelError(RuntimeError):
    """Raised when the local Ollama daemon is unreachable or returns an error."""


def chat(system: str, user: str, *, model: str = MODEL_NAME,
         as_json: bool = False, max_tokens: int | None = None) -> str:
    """Return the model's reply to ``user`` under ``system``, with thinking disabled.

    Args:
        system: System prompt constraining the model's behaviour.
        user: The user turn.
        model: Ollama model tag to run.
        as_json: Force JSON-shaped output (used for fact extraction).
        max_tokens: Optional generation cap. Safe only because thinking is off.

    Raises:
        LocalModelError: If the daemon cannot be reached or replies with an error.
    """
    options: dict[str, object] = {"temperature": GENERATION_TEMPERATURE}
    if max_tokens is not None:
        options["num_predict"] = max_tokens
    payload: dict[str, object] = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "stream": False,
        "think": False,
        "keep_alive": KEEP_ALIVE,
        "options": options,
    }
    if as_json:
        payload["format"] = "json"
    return _post(payload)


def warm_up(model: str = MODEL_NAME) -> None:
    """Load the model into RAM ahead of a demo so the first real call is not slow."""
    chat("Reply with OK.", "OK", model=model, max_tokens=4)


def _post(payload: dict[str, object]) -> str:
    """POST the chat payload to the local daemon and return the message content."""
    request = urllib.request.Request(
        OLLAMA_CHAT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError) as exc:
        raise LocalModelError(f"Local model unreachable at {OLLAMA_CHAT_URL}: {exc}") from exc
    if "error" in body:
        raise LocalModelError(str(body["error"]))
    return (body.get("message", {}).get("content") or "").strip()
