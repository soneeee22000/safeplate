"""Gemma says the answer, in the language the diner spoke.

The verdict is already fixed by the time this runs. That separation is the whole
design: the model is trusted to be clear and kind in Ukrainian, and not trusted
to decide whether someone can safely eat.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .config import GENERATION_TEMPERATURE, MODEL_NAME
from .speech import SpeechError, _content, _post

if TYPE_CHECKING:
    from .loop import Run

SYSTEM_PROMPT = """\
You write the short message a waiter shows to a diner about their food request.

Rules:
- State the outcome first, plainly. Never bury it.
- Give the reason in one or two sentences, in ordinary words.
- If the answer is no because an ingredient is essential to the dish, say so as a
  fact about the food, not as a rule the restaurant is imposing.
- Offer the alternative if one was given.
- Never say a dish is safe. Never add an allergen or a fact you were not given.
- If an ingredient is listed as CANNOT REMOVE, you must NOT offer the dish without
  it, or with "less" of it, or with it "on the side". It cannot come out at all.
  Offer a different dish instead, or nothing.
- No greetings, no apologies, no emoji. Four sentences at most.
"""

#: Phrases that turn a refusal into an offer. Checked against the generated text,
#: because the model demonstrably writes them anyway.
OFFER_PATTERNS = (
    "we can offer", "we can make", "we can prepare", "we can serve",
    "can be made without", "can be prepared without", "instead we can",
    "without any added", "without the added", "we could make", "we can do",
)

VERDICT_OPENERS = {
    "verified": "The request can be met.",
    "needs_confirmation": "We cannot confirm this yet.",
    "do_not_serve": "We cannot serve this as requested.",
}


def _facts(run: "Run") -> str:
    """Everything the model is allowed to use, and nothing else."""
    lines: list[str] = [
        f"Outcome: {VERDICT_OPENERS.get(run.verdict or '', 'Unresolved')}",
    ]

    if run.intent:
        lines.append(f"The diner said: {run.intent.utterance}")
        lines.append(f"They are avoiding: {', '.join(run.intent.avoid) or 'unspecified'}")

    assessment = run.assessment
    if assessment and assessment.dish:
        lines.append(f"Dish: {assessment.dish.name}")
        for finding in assessment.blocking:
            lines.append(
                f"CANNOT REMOVE {finding.ingredient.name}: {finding.ingredient.why}"
            )
        for finding in assessment.adjustable:
            substitute = finding.ingredient.substitute or f"omit the {finding.ingredient.name}"
            lines.append(f"Can adjust {finding.ingredient.name} — {substitute}")
    elif assessment and assessment.unknown_dish:
        lines.append("This dish is not in our verified list, so nothing can be confirmed.")

    for statement in run.statements:
        lines.append(f"Source {statement.source}: {statement.text}")

    if run.kitchen_answer:
        lines.append(f"The kitchen said: {run.kitchen_answer}")

    return "\n".join(lines)


def _write(facts: str, language: str) -> str:
    reply = _post(
        {
            "model": MODEL_NAME,
            "temperature": GENERATION_TEMPERATURE,
            "stream": False,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Write the message in {language}.\n\nFacts:\n{facts}",
                },
            ],
        }
    )
    return _content(reply)


def contradicts_refusal(text: str, run: "Run") -> bool:
    """True when the generated message offers what the loop already refused.

    Measured, not hypothetical: handed `do_not_serve` and the reason that fish
    sauce is structural to pad thai, E2B wrote *"We can offer you the Pad Thai
    without any added fish sauce instead."* — the exact sentence that would put
    an allergic diner in an ambulance.

    A language model is never the last line of defence, and that has to include
    its own prose. This check is deterministic; failing it discards the text.
    """
    if run.verdict != "do_not_serve":
        return False

    # Any offer to make, serve or adjust *this* dish contradicts a refusal —
    # whether the block came from a structural ingredient or from the kitchen.
    # Two measured failures, not one:
    #   structural  -> "We can offer you the Pad Thai without any added fish sauce"
    #   cross-contact -> "We can omit the crushed peanuts from the dish if you like"
    # The second is subtler and just as dangerous: it implies the refusal lifts.
    lowered = text.lower()
    return any(pattern in lowered for pattern in OFFER_PATTERNS)


def compose_reply(run: "Run") -> tuple[str, str]:
    """Return the message in the diner's language, and the same in English.

    Falls back to a plain assembled message if the model is unreachable or if it
    writes something that contradicts the verdict.
    """
    facts = _facts(run)
    language = run.intent.language if run.intent else "en"

    try:
        english = _write(facts, "English")
        if contradicts_refusal(english, run):
            return _fallback(run), _fallback(run)

        if language.startswith("en"):
            return english, english

        original = _write(facts, language)
        if contradicts_refusal(original, run):
            return _fallback(run), english
        return original, english
    except SpeechError:
        message = _fallback(run)
        return message, message


def _fallback(run: "Run") -> str:
    """The message assembled from facts alone, with no model in the loop.

    Used when generation is unavailable *or* when it contradicted the verdict.
    Less graceful, and never wrong.
    """
    parts = [VERDICT_OPENERS.get(run.verdict or "", "Unresolved.")]
    if run.assessment:
        for finding in run.assessment.blocking:
            parts.append(finding.ingredient.why)
            parts.append(
                f"The {finding.ingredient.name} cannot be left out, so this dish is not "
                "possible for you. We can suggest something else from the menu."
            )
        for finding in run.assessment.adjustable:
            if finding.ingredient.substitute:
                parts.append(f"Alternative: {finding.ingredient.substitute}.")
    if run.kitchen_answer:
        parts.append(f"The kitchen said: {run.kitchen_answer}")
    return " ".join(parts)
