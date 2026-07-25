"""The agent loop, and the branches it is not allowed to skip.

We measured Gemma 4 E2B failing to escalate on its own: handed a result
containing an unresolved ingredient, it answered about what it did know and
stopped. A 5B model cannot be trusted to remember to ask for help.

So escalation is control flow. Every `_forced` step below is compelled by this
file, not chosen by the model. Gemma decides what the diner meant and how to say
the answer; it never decides whether the answer is safe.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from . import dishes, serp
from .speech import Intent, SpeechError, understand_audio, understand_text
from .voice import compose_reply

CONFIDENCE_FLOOR = 0.75

#: Ingredients that arrive in a jar, where the manufacturer's declaration is the
#: only real evidence of what is inside.
PACKAGED = {"fish sauce", "oyster sauce", "soy sauce", "tahini sauce", "chilli paste",
            "tamarind paste", "shrimp paste", "pesto"}


@dataclass
class Step:
    n: int
    tool: str
    engine: str
    title: str
    reasoning: str
    forced: bool = False
    forced_by: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data = {
            "n": self.n, "tool": self.tool, "engine": self.engine,
            "title": self.title, "reasoning": self.reasoning, "forced": self.forced,
            "args": self.args, "result": self.result, "duration_ms": self.duration_ms,
        }
        if self.forced_by:
            data["forced_by"] = self.forced_by
        if self.note:
            data["note"] = self.note
        return data


@dataclass
class Run:
    """One case, from the diner speaking to a verdict."""

    run_id: str
    status: str = "running"          # running | awaiting_human | complete | failed
    verdict: str | None = None       # verified | needs_confirmation | do_not_serve
    pending_question: str | None = None
    intent: Intent | None = None
    assessment: dishes.Assessment | None = None
    statements: list[serp.Statement] = field(default_factory=list)
    kitchen_answer: str | None = None
    steps: list[Step] = field(default_factory=list)
    explanation: str = ""
    explanation_en: str = ""
    error: str | None = None
    started: float = field(default_factory=time.time)

    def add(self, step: Step) -> Step:
        step.n = len(self.steps) + 1
        self.steps.append(step)
        return step

    def as_trace(self) -> dict[str, Any]:
        """The shape the interface renders — same schema as `fixtures/*.json`."""
        dish = self.assessment.dish if self.assessment else None
        return {
            "case_id": self.run_id,
            "restaurant": "SafePlate demo service",
            "dish": dish.name if dish else (self.intent.dish if self.intent else "unknown"),
            "allergen": ", ".join(self.intent.avoid) if self.intent else "",
            "diner_language": self.intent.language if self.intent else "en",
            "verdict": self.verdict or "needs_confirmation",
            "total_ms": int((time.time() - self.started) * 1000),
            "steps": [step.as_dict() for step in self.steps],
            "evidence": [
                {"source": item.source, "url": item.url, "text": item.text}
                for item in self.statements
            ],
            "explanation": self.explanation,
            "explanation_en": self.explanation_en,
        }


def _timed(action: Callable[[], Any]) -> tuple[Any, int]:
    started = time.perf_counter()
    value = action()
    return value, int((time.perf_counter() - started) * 1000)


def begin(run: Run, *, audio: bytes | None = None, text: str | None = None,
          audio_format: str = "wav") -> Run:
    """Take the diner's request and carry it as far as the loop can go alone.

    Stops at `awaiting_human` when the kitchen has to answer, or at `complete`
    when the table already settles it.
    """
    try:
        intent, elapsed = _timed(
            lambda: understand_audio(audio, audio_format=audio_format)
            if audio else understand_text(text or "")
        )
    except SpeechError as error:
        run.status, run.error = "failed", str(error)
        return run

    run.intent = intent
    run.add(Step(
        n=0, tool="understand_request", engine="gemma",
        title="Gemma hears the diner",
        reasoning="One call transcribes the audio and extracts the request. The model "
                  "resolves 'without the fish sauce' against the dish it just heard named.",
        args={"input": "audio" if audio else "text"},
        result={"utterance": intent.utterance, "language": intent.language,
                "dish": intent.dish, "avoid": intent.avoid,
                "request_type": intent.request_type},
        duration_ms=elapsed,
        note=None if audio else "Typed input — same extraction path.",
    ))

    if not intent.dish:
        return _forced_escalate(
            run, "no dish named",
            "The diner did not name a dish clearly. The agent asks rather than guessing "
            "which one they meant.",
            verdict="needs_confirmation",
        )

    assessment, elapsed = _timed(lambda: dishes.assess(intent.dish, intent.avoid))
    run.assessment = assessment
    dish = assessment.dish

    run.add(Step(
        n=0, tool="assess_dish", engine="rule",
        title="The dish table decides what can come out",
        reasoning="Whether an ingredient is structural is data, not generation. A 5B model "
                  "guessing at culinary structure is exactly what this avoids.",
        args={"dish": intent.dish, "avoid": intent.avoid},
        result={
            "outcome": assessment.outcome,
            "blocking": [
                {"ingredient": f.ingredient.name, "role": f.ingredient.role,
                 "why": f.ingredient.why} for f in assessment.blocking
            ],
            "adjustable": [
                {"ingredient": f.ingredient.name, "role": f.ingredient.role,
                 "substitute": f.ingredient.substitute} for f in assessment.adjustable
            ],
        },
        duration_ms=elapsed,
        note=None if dish else "Dish not in the table.",
    ))

    if assessment.unknown_dish:
        return _forced_escalate(
            run, "dish not in the table",
            f"'{intent.dish}' is not a dish this service knows. The agent will not infer "
            "a recipe it has never seen.",
            verdict="needs_confirmation",
        )

    # A packaged ingredient's real contents live in the manufacturer's declaration,
    # not in our table. Forced, because the model would happily skip it.
    packaged = [f for f in assessment.findings if f.ingredient.name in PACKAGED]
    if packaged:
        _lookup(run, packaged[0].ingredient.name, packaged[0].matched_avoid)

    if assessment.blocking:
        return _forced_escalate(
            run, "structural ingredient cannot be removed",
            "The blocking ingredient is what makes the dish that dish. The honest answer "
            "is no — and saying so is more useful than a modification the kitchen would "
            "have to refuse at the pass.",
            verdict="do_not_serve",
        )

    return _ask_kitchen(run)


def _lookup(run: Run, product: str, avoid: str) -> None:
    try:
        statements, elapsed = _timed(lambda: serp.lookup_product(product))
        run.statements = statements
        conflict = serp.sources_conflict(statements, avoid)
        note = ("Sources disagree — that is grounds to refuse, never to average."
                if conflict else None)
        result: dict[str, Any] = {
            "statements": [
                {"source": s.source, "url": s.url, "text": s.text, "declares": s.declares}
                for s in statements
            ],
            "conflict": conflict,
        }
    except serp.SerpUnavailable as error:
        elapsed, note = 0, "Lookup unavailable — treated as unconfirmed, never as safe."
        result = {"statements": [], "conflict": False, "unavailable": str(error)}

    run.add(Step(
        n=0, tool="lookup_product", engine="external",
        title="SerpApi — what the manufacturer declares",
        reasoning=f"'{product}' arrives in a jar. What is actually in it is the "
                  "manufacturer's declaration, not our table.",
        forced=True, forced_by="a packaged ingredient matched the diner's request",
        args={"product": product},
        result=result, duration_ms=elapsed, note=note,
    ))


def _ask_kitchen(run: Run) -> Run:
    """Always asked. A clean table never clears a dish on its own."""
    assert run.assessment and run.assessment.dish
    dish = run.assessment.dish
    avoid = ", ".join(run.intent.avoid) if run.intent else "the stated allergen"
    changes = ", ".join(
        f.ingredient.substitute or f"omit {f.ingredient.name}"
        for f in run.assessment.adjustable
    ) or "no changes needed"

    question = (
        f"{dish.name}: can you do it as — {changes}? "
        f"And is there cross-contact with {avoid}? Note: {dish.cross_contact_note}."
    )

    run.add(Step(
        n=0, tool="ask_kitchen", engine="human",
        title="The agent asks what no document can answer",
        reasoning="Cross-contact is not written on any label and never will be. Before "
                  "clearing anything, a human has to answer.",
        forced=True, forced_by="cross_contact unknown for the requested allergen",
        args={"question": question},
        result={},
    ))

    run.status = "awaiting_human"
    run.pending_question = question
    return run


def _forced_escalate(run: Run, reason: str, explanation: str, *, verdict: str) -> Run:
    run.add(Step(
        n=0, tool="escalate", engine="rule",
        title="Refuse rather than guess",
        reasoning=explanation,
        forced=True, forced_by=reason,
        args={"verdict": verdict}, result={"verdict": verdict},
    ))
    run.verdict = verdict
    _speak(run)
    run.status = "complete"
    return run


def answer_kitchen(run: Run, answer: str) -> Run:
    """Fold the kitchen's answer in and finish the case."""
    if run.status != "awaiting_human":
        return run

    run.kitchen_answer = answer
    run.pending_question = None
    for step in reversed(run.steps):
        if step.tool == "ask_kitchen":
            step.result = {"answered_by": "chef", "answer": answer}
            break

    # Gemma reads the chef's free-text reply; the loop decides what it means.
    refused = any(
        word in answer.lower()
        for word in ("no", "non", "can't", "cannot", "shared", "same", "yes -", "yes,")
    )
    cleared = any(
        word in answer.lower()
        for word in ("dedicated", "separate", "clean", "no cross", "pas de", "aucun")
    )

    if cleared and not run.assessment.blocking:
        run.verdict = "verified"
    elif refused:
        run.verdict = "do_not_serve"
    else:
        run.verdict = "needs_confirmation"

    run.add(Step(
        n=0, tool="interpret_answer", engine="rule",
        title="The kitchen's answer decides it",
        reasoning="A human said what the documents could not. The verdict follows from "
                  "that answer, not from the model's impression of it.",
        args={"answer": answer},
        result={"verdict": run.verdict},
    ))

    _speak(run)
    run.status = "complete"
    return run


def _speak(run: Run) -> None:
    """Gemma writes the answer the diner actually reads, in their language."""
    started = time.perf_counter()
    original, english = compose_reply(run)
    elapsed = int((time.perf_counter() - started) * 1000)

    run.explanation, run.explanation_en = original, english
    language = run.intent.language if run.intent else "en"
    run.add(Step(
        n=0, tool="compose_reply", engine="gemma",
        title=f"Gemma explains it in the diner's language ({language})",
        reasoning="The verdict was fixed before this ran. Gemma's job is to say it "
                  "clearly and give the reason, not to reach it.",
        args={"verdict": run.verdict, "language": language},
        result={"verdict": run.verdict},
        duration_ms=elapsed,
    ))
