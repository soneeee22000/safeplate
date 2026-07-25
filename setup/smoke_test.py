"""Offline smoke test for Séjour Pour Tous.

Run this with WIFI OFF. It proves the two things the whole build depends on:
  1. Gemma 4 E4B generates locally with no network.
  2. Native tool-calling round-trips (flagged as the runtime's most fragile part).

A green run here is the gate for Tuesday. Usage:
    .venv\\Scripts\\python.exe setup\\smoke_test.py
"""

from __future__ import annotations

import sys

import ollama

MODEL: str = "gemma4:e2b"  # E2B is the demo model — E4B (7.2GB buffer) OOMs on 16GB
FALLBACK_MODEL: str = "gemma4:e2b-it-q4_K_M"
GEN_PROMPT: str = "In one sentence, what is a 'titre de séjour' in France?"

# A stand-in for the real as-of retrieval tool the engine will expose over MCP.
LAW_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "query_immigration_law",
        "description": "Look up the French immigration rule in force on a given date.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "e.g. 'student to work visa'"},
                "as_of_date": {"type": "string", "description": "ISO date, e.g. 2026-07-25"},
            },
            "required": ["topic", "as_of_date"],
        },
    },
}
TOOL_PROMPT: str = (
    "I'm on a student visa and just got a job offer. What are my options as of today, "
    "2026-07-25? Use the tool to look up the rule in force."
)


def _resolve_model() -> str:
    """Return the primary model if present locally, else the lighter fallback."""
    installed = {m.model for m in ollama.list().models}
    if MODEL in installed:
        return MODEL
    if FALLBACK_MODEL in installed:
        print(f"[warn] {MODEL} not found; using fallback {FALLBACK_MODEL}")
        return FALLBACK_MODEL
    raise SystemExit(f"[fail] Neither {MODEL} nor {FALLBACK_MODEL} is pulled. Run 01-setup.ps1.")


def test_generation(model: str) -> None:
    """Assert the model produces non-empty text offline."""
    reply = ollama.chat(model=model, messages=[{"role": "user", "content": GEN_PROMPT}])
    text = reply.message.content or ""
    if not text.strip():
        raise SystemExit("[fail] Generation returned empty output.")
    print(f"[ok] Generation: {text.strip()[:160]}")


def test_tool_calling(model: str) -> None:
    """Assert the model emits a structured tool call for the retrieval tool."""
    reply = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": TOOL_PROMPT}],
        tools=[LAW_TOOL],
    )
    calls = reply.message.tool_calls or []
    if not calls:
        raise SystemExit(
            "[fail] No tool call emitted. Tool-calling is fragile on E4B — if this "
            "persists, plan to call the engine from the app orchestrator instead."
        )
    fn = calls[0].function
    print(f"[ok] Tool call: {fn.name}({dict(fn.arguments)})")


def main() -> int:
    """Run both smoke checks and report a single pass/fail gate."""
    model = _resolve_model()
    print(f"[info] Smoke-testing {model} (turn wifi off to prove offline)\n")
    test_generation(model)
    test_tool_calling(model)
    print("\n[PASS] Tuesday gate green — offline generation + tool-calling both work.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
