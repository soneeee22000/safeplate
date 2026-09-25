"""The agent loop, and the branches it is not allowed to skip.

We measured Gemma 4 E2B failing to escalate on its own: handed a result
containing an unresolved ingredient, it answered about what it did know and
stopped. A 5B model cannot be trusted to remember to ask for help.

So escalation is control flow. Every `_forced` step below is compelled by this
file, not chosen by the model. Gemma decides what the diner meant and how to say
the answer; it never decides whether the answer is safe.
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from . import config, dishes, intake_rules, menu_symphony, serp
from .allergens import conflicts, expand
from .speech import Intent, SpeechError, understand_audio, understand_text
from .voice import WRITER_GEMMA, WRITER_TRANSLATED, compose_reply, compose_rules_reply, fixed_reply

#: Rules mode has no model to transcribe with, so spoken input cannot be heard.
AUDIO_NEEDS_GEMMA = "audio needs Gemma — run locally"

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
    status: str = "running"          # running | awaiting_human | answering | complete | failed
    verdict: str | None = None       # verified | needs_confirmation | do_not_serve
    pending_question: str | None = None
    intent: Intent | None = None
    assessment: dishes.Assessment | None = None
    packaged_report: menu_symphony.LabelReport | None = None
    statements: list[serp.Statement] = field(default_factory=list)
    kitchen_answer: str | None = None
    steps: list[Step] = field(default_factory=list)
    explanation: str = ""
    explanation_en: str = ""
    error: str | None = None
    started: float = field(default_factory=time.time)
    #: Held only while an answer claims the run, so two answers cannot both land.
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def add(self, step: Step) -> Step:
        step.n = len(self.steps) + 1
        self.steps.append(step)
        return step

    def as_trace(self) -> dict[str, Any]:
        """The shape the interface renders — same schema as `fixtures/*.json`."""
        dish = self.assessment.dish if self.assessment else None
        if self.packaged_report is not None:
            dish = self.packaged_report.dish
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
                {"source": item.source, "url": item.url, "text": item.text,
                 "trusted": item.trusted}
                for item in self.statements
            ],
            "explanation": self.explanation,
            "explanation_en": self.explanation_en,
        }


def _timed(action: Callable[[], Any]) -> tuple[Any, int]:
    started = time.perf_counter()
    value = action()
    return value, int((time.perf_counter() - started) * 1000)


def rules_mode() -> bool:
    """True when the loop runs with no model: keyword intake, assembled replies."""
    return config.SAFEPLATE_MODE == config.MODE_RULES


def _hear(audio: bytes | None, text: str | None, audio_format: str) -> Intent:
    """The diner's request, through Gemma or, in rules mode, through keyword rules."""
    if rules_mode():
        if audio:
            raise SpeechError(AUDIO_NEEDS_GEMMA)
        return intake_rules.understand_text(text or "")
    if audio:
        return understand_audio(audio, audio_format=audio_format)
    return understand_text(text or "")


def _heard_step(intent: Intent, *, audio: bool, elapsed: int) -> Step:
    """The trace entry for intake, naming the engine that actually did it."""
    result = {"utterance": intent.utterance, "language": intent.language,
              "dish": intent.dish, "avoid": intent.avoid,
              "request_type": intent.request_type}
    if rules_mode():
        return Step(
            n=0, tool="understand_request", engine="rule",
            title="Rules read the typed request",
            reasoning="No model on this host. The dish and the allergens are matched "
                      "against the same tables the loop decides with; anything not "
                      "recognised is left empty, so the loop asks instead of guessing.",
            args={"input": "text"}, result=result, duration_ms=elapsed,
            note="Rules mode — keyword matching, no model.",
        )
    return Step(
        n=0, tool="understand_request", engine="gemma",
        title="Gemma hears the diner",
        reasoning="One call transcribes the audio and extracts the request. The model "
                  "resolves 'without the fish sauce' against the dish it just heard named.",
        args={"input": "audio" if audio else "text"}, result=result, duration_ms=elapsed,
        note=None if audio else "Typed input — same extraction path.",
    )


def begin(run: Run, *, audio: bytes | None = None, text: str | None = None,
          audio_format: str = "wav") -> Run:
    """Take the diner's request and carry it as far as the loop can go alone.

    Stops at `awaiting_human` when the kitchen has to answer, or at `complete`
    when the table already settles it.
    """
    try:
        intent, elapsed = _timed(lambda: _hear(audio, text, audio_format))
    except SpeechError as error:
        run.status, run.error = "failed", str(error)
        return run

    run.intent = intent
    run.add(_heard_step(intent, audio=bool(audio), elapsed=elapsed))

    if not intent.dish:
        return _forced_escalate(
            run, "no dish named",
            "The diner did not name a dish clearly. The agent asks rather than guessing "
            "which one they meant.",
            verdict="needs_confirmation",
        )

    # Measured failure: handed "I have a tree nut allergy", E2B once returned an
    # empty `avoid` and the run carried on checking a dish against nothing — it
    # reached the kitchen question without an allergen to ask about. A case with
    # no allergen cannot be checked, so it stops here rather than looking as
    # though it was.
    if not intent.avoid:
        return _forced_escalate(
            run, "no allergen understood",
            "The agent did not catch what the diner cannot eat, and will not check a "
            "dish against nothing. The question has to be asked again.",
            verdict="needs_confirmation",
        )

    # Understanding some of the allergens is not understanding the request. A
    # diner allergic to "sulfite and dairy" who is checked for dairy alone is
    # checked against the wrong list, and a plain "no" would clear the wine.
    if intent.unrecognised:
        return _forced_escalate(
            run, f"allergen not recognised — {', '.join(intent.unrecognised)}",
            "The diner named something they cannot eat that the agent could not match to "
            "an allergen. Checking only the ones it did catch would look like a full "
            "check, so the question has to be asked again.",
            verdict="needs_confirmation",
        )

    # A sealed frozen tray is a different problem from a dish a chef assembles:
    # nothing can be left out of it, and the workshop declaration on every label
    # covers ten allergen classes at once. See `route_packaged` for which wins.
    packaged = route_packaged(intent.dish)
    if packaged is not None:
        return _assess_packaged(run, packaged, intent)

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
            "advisory": [
                {"ingredient": f.ingredient.name, "role": f.ingredient.role}
                for f in assessment.advisory
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
    disputed = bool(packaged) and _lookup(run, packaged[0], assessment)

    if assessment.blocking:
        return _forced_escalate(
            run, "structural ingredient cannot be removed",
            "The blocking ingredient is what makes the dish that dish. The honest answer "
            "is no — and saying so is more useful than a modification the kitchen would "
            "have to refuse at the pass.",
            verdict="do_not_serve",
        )

    if disputed:
        return _forced_escalate(
            run, "sources disagree about an ingredient that stays",
            f"'{packaged[0].ingredient.name}' stays on the plate, and the declarations "
            "found for it disagree about the diner's allergen. Disagreement is not "
            "averaged; it is grounds to refuse.",
            verdict="do_not_serve",
        )

    if assessment.advisory:
        return _escalate_advisory(run, [f.ingredient.name for f in assessment.advisory])

    return _ask_kitchen(run)


def _escalate_advisory(run: Run, names: list[str]) -> Run:
    """Hold a case on an ingredient no regulation settles, instead of clearing it.

    Pine nuts are the case in point: not an EU-14 allergen, so nothing obliges a
    label to flag them, and still avoided by many tree-nut-allergic diners. Only
    the diner can say which they are, so the kitchen is not asked to decide it.
    """
    listed = ", ".join(names)
    return _forced_escalate(
        run, f"advisory ingredient — {listed} (not an EU-14 allergen)",
        f"{listed}: not an EU-14 allergen, so no label or table is wrong to leave it "
        "unflagged. Many diners with this allergy avoid it all the same, so a person "
        "has to ask the diner rather than the table clearing the dish.",
        verdict="needs_confirmation",
    )


def route_packaged(dish_name: str | None) -> menu_symphony.PackagedDish | None:
    """The Symphony plat a heard dish name refers to, or None for the dish table.

    Symphony.fr is the onboarded restaurant, but its keywords overlap ordinary
    dishes ("pesto", "pâtes"). A name that fully matches a dish-table entry
    therefore stays with the table; only then are the trays consulted.
    """
    if dishes.strong_match(dish_name) is not None:
        return None
    return menu_symphony.lookup(dish_name)


def _assess_packaged(run: Run, dish: menu_symphony.PackagedDish, intent: Intent) -> Run:
    """Decide a Symphony tray from its own label, and never above what it can prove.

    The ceiling here is deliberate. Every Symphony label carries the same workshop
    declaration — gluten, celery, mustard, peanuts, fish, eggs, soy, milk, nuts,
    sesame — so for any of those ten the strongest honest verdict is
    `needs_confirmation`. A `verified` is unreachable, by construction rather than
    by the model's discretion.
    """
    report, elapsed = _timed(lambda: menu_symphony.report(dish, intent.avoid))
    run.packaged_report = report

    run.add(Step(
        n=0, tool="read_label", engine="rule",
        title=f"The label decides — {dish.name}",
        reasoning="Symphony trays arrive sealed and reheated. What is in them is what the "
                  "manufacturer printed, and nothing can be left out at the pass.",
        args={"dish": dish.name, "avoid": intent.avoid},
        result={
            "outcome": report.outcome,
            "label_conflicts": [
                {"ingredient": item.ingredient.name, "declared_in_bold": item.declared,
                 "advisory": item.advisory}
                for item in report.label_conflicts
            ],
            "shared_facility_matches": list(report.shared_facility_matches),
            "vegan_misreads": list(report.vegan_misreads),
        },
        duration_ms=elapsed,
        note=" ".join(report.vegan_misreads) or None,
    ))

    if report.direct_conflicts:
        return _refuse_label_conflict(run, report)

    if report.advisory_conflicts:
        return _escalate_advisory(run, [
            f"{item.ingredient.name} ({item.ingredient.gloss})"
            for item in report.advisory_conflicts
        ])

    if report.shared_facility_matches:
        covered = ", ".join(report.shared_facility_matches)
        return _forced_escalate(
            run, f"workshop declaration covers {covered}",
            "The label says this is made in a workshop that also handles this allergen. "
            "That is the manufacturer declining to guarantee it, so we decline too.",
            verdict="needs_confirmation",
        )

    return _ask_kitchen_packaged(run, dish, intent)


def _refuse_label_conflict(run: Run, report: menu_symphony.LabelReport) -> Run:
    """Refuse a sealed tray that contains what the diner cannot eat."""
    explanation = ("The ingredient is in the tray. It cannot be removed from a sealed "
                   "dish, so the answer is no.")
    if report.undeclared_conflicts:
        reason = ("a declarable allergen is on the label but not in the bold allergen "
                  "text")
        explanation += (" The label never bolded it, so the diner would not have found "
                        "it by reading the allergen text carefully.")
    elif report.declared_conflicts:
        reason = "the label declares it outright"
    else:
        reason = "the label lists an ingredient the diner named"
    return _forced_escalate(run, reason, explanation, verdict="do_not_serve")


def _ask_kitchen_packaged(run: Run, dish: menu_symphony.PackagedDish, intent: Intent) -> Run:
    """Even outside the workshop declaration, a person confirms before anything clears."""
    avoid = ", ".join(intent.avoid) or "the stated allergen"
    # Phrased so "yes" always means risk, matching the other kitchen question.
    # Two questions with opposite polarity cannot share one reading of the answer,
    # and getting that backwards clears a dish that should be refused.
    question = (
        f"{dish.name}: the label does not list {avoid} and the workshop declaration does "
        f"not cover it. Is there ANY way {avoid} could reach this plate in service?"
    )

    run.add(Step(
        n=0, tool="ask_kitchen", engine="human",
        title="The agent asks what no label can answer",
        reasoning="The workshop line is silent on this allergen, which is not the same as "
                  "the workshop promising its absence. A human confirms.",
        forced=True, forced_by="label silent on the requested allergen",
        args={"question": question}, result={},
    ))

    run.status = "awaiting_human"
    run.pending_question = question
    return run


def _lookup_note(conflict: bool, confirmed: bool, *, stays: bool,
                 product: str) -> str | None:
    """What the trace says about a finished lookup, most serious first."""
    if conflict and stays:
        return "Sources disagree — that is grounds to refuse, never to average."
    if conflict:
        return (f"Sources disagree — but the {product} is being left off or substituted, "
                "so the disagreement does not decide this case.")
    if not confirmed:
        return ("No manufacturer or retailer declaration found — treated as "
                "unconfirmed, never as safe.")
    return None


def _lookup(run: Run, finding: dishes.Finding, assessment: dishes.Assessment) -> bool:
    """Look up a packaged ingredient's declaration and put it on the trace.

    Returns:
        True when the sources disagree about an ingredient that stays on the
        plate, which the caller must refuse on. A disagreement about one that
        is being left off or substituted is recorded, and decides nothing.
    """
    product, avoid = finding.ingredient.name, finding.matched_avoid
    stays = finding not in assessment.adjustable
    conflict = False
    try:
        statements, elapsed = _timed(lambda: serp.lookup_product(product))
        run.statements = statements
        conflict = serp.sources_conflict(statements, avoid)
        confirmed = serp.is_confirmed(statements)
        note = _lookup_note(conflict, confirmed, stays=stays, product=product)
        result: dict[str, Any] = {
            "statements": [
                {"source": s.source, "url": s.url, "text": s.text, "declares": s.declares,
                 "trusted": s.trusted}
                for s in statements
            ],
            "conflict": conflict,
            "confirmed": confirmed,
        }
    except serp.SerpUnavailable as error:
        elapsed, note = 0, "Lookup unavailable — treated as unconfirmed, never as safe."
        result = {"statements": [], "conflict": False, "confirmed": False,
                  "unavailable": str(error)}

    run.add(Step(
        n=0, tool="lookup_product", engine="external",
        title="SerpApi — what the manufacturer declares",
        reasoning=f"'{product}' arrives in a jar. What is actually in it is the "
                  "manufacturer's declaration, not our table.",
        forced=True, forced_by="a packaged ingredient matched the diner's request",
        args={"product": product},
        result=result, duration_ms=elapsed, note=note,
    ))
    return conflict and stays


def _ask_kitchen(run: Run) -> Run:
    """Always asked. A clean table never clears a dish on its own."""
    if run.assessment is None or run.assessment.dish is None:
        return _forced_escalate(
            run, "no assessed dish to ask about",
            "The kitchen can only be asked about a dish the table has assessed.",
            verdict="needs_confirmation",
        )
    dish = run.assessment.dish
    avoid = ", ".join(run.intent.avoid) if run.intent else "the stated allergen"
    changes = ", ".join(
        f.ingredient.substitute or f"omit {f.ingredient.name}"
        for f in run.assessment.adjustable
    )
    # The change is stated as an instruction, never asked, so the one question
    # left keeps the rule that YES means risk. "Can you do it as X? And is there
    # cross-contact?" made a bare "yes" mean opposite things at once.
    instruction = f"Prepare it with these changes: {changes}. " if changes else ""

    question = (
        f"{dish.name}: {instruction}Is there ANY way {avoid} could reach this plate — "
        f"shared oil, fryer, board, utensils, or a pre-made component? "
        f"Note: {dish.cross_contact_note}."
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


#: A structured kitchen answer, mapped straight to the verdict it earns.
RISK_VERDICTS = {
    "none": "verified",
    "risk": "do_not_serve",
    "unsure": "needs_confirmation",
}

#: The kitchen confirming a risk. Every question is phrased "is there any way X
#: could reach this plate", so any of these refuses, whatever else was said.
RISK_STEMS = ("shar", "partag", "risk", "risqu", "possib", "contamin")
RISK_PHRASES = (
    "same", "meme", "can't guarantee", "cannot guarantee", "can not guarantee",
    "no guarantee", "not guaranteed", "may contain", "might contain",
    "peut contenir", "not separate", "not dedicated", "not sealed", "sometimes",
    "parfois",
)

#: A bare YES answers the question "is there any way": it means risk.
YES_WORDS = ("yes", "yeah", "yep", "yup", "oui", "ouais")

#: Anything short of certainty. Hedged answers never clear a dish.
HEDGE_PHRASES = (
    "no idea", "not sure", "unsure", "check", "think", "maybe", "perhaps",
    "probably", "don't know", "dont know", "do not know", "not certain",
    "should be", "should not", "shouldn't", "might", "guess", "believe",
    "normally", "usually", "hopefully", "sais pas", "pas sur", "je pense",
    "je crois", "peut etre", "verifier", "verifie", "normalement", "probablement",
)

#: The kitchen ruling the risk out: the words a clearance has to lead with.
CLEARANCE_WORDS = frozenset({
    "no", "nope", "nah", "non", "none", "never", "nothing", "aucun", "aucune", "jamais",
    "rien",
})

#: Equipment kept apart. Clears only when nothing before it negates it: "no
#: separate fryer" and "we don't have a dedicated fryer" both admit the risk.
SEGREGATION_WORDS = frozenset({
    "dedicated", "separate", "separated", "sealed", "dedie", "dediee", "separe", "separee",
    "scelle", "scellee",
})

#: Words that flip a segregation word that follows them in the same clause.
NEGATORS = frozenset({
    "no", "not", "never", "none", "nothing", "dont", "don't", "doesnt", "doesn't", "isnt",
    "isn't", "arent", "aren't", "wasnt", "wasn't", "cant", "can't", "cannot", "without",
    "pas", "sans", "ne", "jamais", "aucun", "aucune",
})

#: The only other words a clearance may contain. This is a whitelist on purpose:
#: "no, but...", "no clue", "no, ask the manager" and "never cleaned" all start
#: like a clearance, and each is rejected by a word that is simply not on it.
FILLER_WORDS = frozenset({
    "a", "an", "the", "and", "at", "all", "it", "its", "it's", "in", "this", "that", "for",
    "of", "on", "with", "is", "are", "we", "use", "have", "our", "own", "totally",
    "completely", "fully", "entirely", "always", "whatsoever", "here",
    "dish", "plate", "fryer", "fryers", "board", "boards", "wok", "woks", "pan", "pans",
    "pot", "oil", "utensil", "utensils", "knife", "knives", "station", "equipment", "tray",
    "kitchen", "factory", "service",
    "le", "la", "les", "l", "un", "une", "de", "du", "des", "d", "en", "et",
    "dans", "ce", "cet", "cette", "ni", "plat", "bac", "usine", "friteuse", "planche",
    "huile", "poele", "ustensiles", "cuisine", "tout", "nous", "avons", "utilisons",
})

#: Where one clause of an answer ends and the next begins.
CLAUSE_BREAK = re.compile(r"[,.;:!?()/\-–—]+")


def _plain(answer: str) -> str:
    """Lowercase with accents stripped and curly apostrophes made straight."""
    decomposed = unicodedata.normalize("NFKD", answer.lower().replace("’", "'"))
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _answer_words(text: str) -> list[str]:
    """The words of already-plain text, apostrophes kept so "don't" stays one word."""
    return re.findall(r"[a-z0-9']+", text)


def _normalise_answer(answer: str) -> str:
    """Lowercase, strip accents and punctuation, and pad with spaces for matching."""
    return f" {' '.join(_answer_words(_plain(answer)))} "


def _says(text: str, phrases: tuple[str, ...]) -> bool:
    """Whole-word match, so "no" is never found inside "know" or "not"."""
    return any(f" {phrase} " in text for phrase in phrases)


def _names_the_allergen(term: str, avoid: list[str] | None) -> bool:
    """True when an allergen word in the answer may be one the diner avoids.

    With no avoid list to compare against, every allergen word is treated as
    the diner's: an answer that names an allergen is never read as a clearance
    unless it is provably about a different one.
    """
    if not avoid:
        return True
    return any(conflicts(avoided, list(expand(term)), term) for avoided in avoid)


def _clause_clears(words: list[str], allergen_indices: set[int]) -> bool:
    """True when one clause is nothing but a clearance, with no negated segregation."""
    if not any(word in CLEARANCE_WORDS or word in SEGREGATION_WORDS for word in words):
        return False
    negated = False
    for index, word in enumerate(words):
        if word in SEGREGATION_WORDS and negated:
            return False
        negated = negated or word in NEGATORS
        allowed = word in CLEARANCE_WORDS or word in SEGREGATION_WORDS or word in FILLER_WORDS
        if not allowed and index not in allergen_indices:
            return False
    return True


def _pure_clearance(answer: str, avoid: list[str] | None) -> bool:
    """True only for a short answer that is a clearance and nothing else.

    Every clause has to carry a clearance or segregation word, every word has to
    be on the whitelist or name an allergen other than the diner's, and nothing
    may negate a segregation word. Anything else is not an answer to rely on.
    """
    clauses = [_answer_words(part) for part in CLAUSE_BREAK.split(_plain(answer))]
    clauses = [words for words in clauses if words]
    if not clauses:
        return False
    for words in clauses:
        mentions = intake_rules.allergen_mentions(words)
        if any(_names_the_allergen(term, avoid) for _, _, term in mentions):
            return False
        indices = {index for start, end, _ in mentions for index in range(start, end)}
        if not _clause_clears(words, indices):
            return False
    return True


def _classify_answer(answer: str, avoid: list[str] | None = None) -> str:
    """Read free text as `risk`, `hedge`, `contradiction`, `clear` or `unknown`.

    Order is the safety rule: risk beats a hedge, and a hedge beats a clearance.
    A YES alongside a clearance ("yes it is fine, totally separate") is the chef
    answering a different question than the one asked, so it clears nothing.
    `clear` is kept for an answer that is purely a clearance and does not name
    the diner's allergen; see `_pure_clearance`.
    """
    text = _normalise_answer(answer)
    words = text.split()
    mentions_clearance = any(w in CLEARANCE_WORDS or w in SEGREGATION_WORDS for w in words)
    said_yes = _says(text, YES_WORDS)

    if _says(text, RISK_PHRASES) or any(w.startswith(RISK_STEMS) for w in words):
        return "risk"
    if said_yes and not mentions_clearance:
        return "risk"
    if "?" in answer or _says(text, HEDGE_PHRASES):
        return "hedge"
    if said_yes:
        return "contradiction"
    return "clear" if _pure_clearance(answer, avoid) else "unknown"


def _read_kitchen_answer(run: Run, answer: str, risk: str | None = None) -> str:
    """Turn the kitchen's answer into a verdict, erring towards refusal.

    A structured `risk` decides on its own, except that a `none` whose note is
    anything but a pure clearance stays `needs_confirmation`. Free text clears
    only on an explicit, unhedged "no risk"; anything nobody understood stays
    `needs_confirmation`, because it is not an answer.
    """
    blocked = bool(run.assessment and run.assessment.blocking)
    avoid = run.intent.avoid if run.intent else None
    if risk is not None:
        verdict = RISK_VERDICTS[risk]
        if verdict == "verified" and answer.strip():
            if _classify_answer(answer, avoid) != "clear":
                return "needs_confirmation"
        return "needs_confirmation" if verdict == "verified" and blocked else verdict

    reading = _classify_answer(answer, avoid)
    if reading == "risk":
        return "do_not_serve"
    if reading == "clear" and not blocked:
        return "verified"
    return "needs_confirmation"


class NotAwaitingAnswer(RuntimeError):
    """Raised when an answer arrives for a run that is not waiting for one."""


def _claim(run: Run) -> None:
    """Take the run for this answer, or refuse; atomic, so only one answer lands.

    The status moves off `awaiting_human` before any slow work, so a second
    answer arriving while the first is still being composed finds nothing to
    answer instead of overwriting the verdict.
    """
    with run.lock:
        if run.status != "awaiting_human":
            raise NotAwaitingAnswer(f"{run.run_id} is {run.status}, not awaiting an answer")
        run.status = "answering"
        run.pending_question = None


def answer_kitchen(run: Run, answer: str = "", *, risk: str | None = None) -> Run:
    """Fold the kitchen's answer in and finish the case.

    Args:
        run: A run stopped at `awaiting_human`.
        answer: The chef's free text, or the optional note on a structured answer.
        risk: `none`, `risk` or `unsure` when the kitchen answered with a choice.

    Raises:
        ValueError: `risk` is given but is not one of the three accepted values.
        NotAwaitingAnswer: the run is not waiting for an answer, including when
            another answer has already claimed it.
    """
    if risk is not None and risk not in RISK_VERDICTS:
        raise ValueError(f"risk must be one of {sorted(RISK_VERDICTS)}, not {risk!r}")
    _claim(run)

    recorded = answer or (risk or "")
    run.kitchen_answer = recorded
    for step in reversed(run.steps):
        if step.tool == "ask_kitchen":
            step.result = {"answered_by": "chef", "answer": recorded}
            if risk is not None:
                step.result["risk"] = risk
            break

    run.verdict = _read_kitchen_answer(run, answer, risk)
    _record_interpretation(run, answer, risk)
    try:
        _speak(run)
    except Exception as error:  # noqa: BLE001 - a failed reply must still end the case
        _speak_failed(run, error)
    run.status = "complete"
    return run


def _speak_failed(run: Run, error: Exception) -> None:
    """End a case whose reply could not be written, without leaving it cleared.

    A refusal stands: the kitchen said what it said. A clearance does not,
    because nobody has told the diner, and a verdict no one explained is not one
    to serve on.
    """
    run.error = f"the reply could not be written: {error}"
    if run.verdict == "verified":
        run.add(Step(
            n=0, tool="escalate", engine="rule",
            title="Refuse rather than guess",
            reasoning="The reply to the diner could not be written, so the clearance is "
                      "not passed on. A person confirms before anything is served.",
            forced=True, forced_by="the reply could not be written",
            args={"verdict": "needs_confirmation"}, result={"verdict": "needs_confirmation"},
        ))
        run.verdict = "needs_confirmation"
    run.explanation = run.explanation_en = fixed_reply(run)
    language = run.intent.language if run.intent else "en"
    run.add(Step(
        n=0, tool="compose_reply", engine="rule",
        title=f"Reply failed — fixed sentences state the verdict ({language} requested)",
        reasoning="Writing the reply raised an error. The verdict is stated with the "
                  "fixed English sentences instead.",
        args={"verdict": run.verdict, "language": language},
        result={"verdict": run.verdict}, note=run.error,
    ))


def _record_interpretation(run: Run, answer: str, risk: str | None) -> None:
    """Put the rule's reading of the kitchen's answer on the trace."""
    args: dict[str, Any] = {"answer": answer}
    if risk is not None:
        args["risk"] = risk
    run.add(Step(
        n=0, tool="interpret_answer", engine="rule",
        title="The kitchen's answer decides it",
        reasoning="A human said what the documents could not. The verdict follows from "
                  "that answer, not from the model's impression of it.",
        args=args,
        result={"verdict": run.verdict},
    ))


def _reply_label(writer: str | None, language: str) -> tuple[str, str, str]:
    """The engine, title and reasoning that credit whoever wrote the reply.

    `writer` is None in rules mode, where no model is on the host at all.
    """
    if writer is None:
        return (
            "rule", f"Fixed sentences state the verdict ({language} requested)",
            "No model on this host. The reply is assembled from the facts, with "
            "hand-checked safety sentences where the diner's language has them "
            "and English otherwise.",
        )
    if writer == WRITER_GEMMA:
        return (
            "gemma", f"Gemma explains it in the diner's language ({language})",
            "The verdict was fixed before this ran. Gemma's job is to say it "
            "clearly and give the reason, not to reach it.",
        )
    if writer == WRITER_TRANSLATED:
        return (
            "gemma", f"Fixed sentences state the verdict; Gemma translated them ({language})",
            "Gemma's own reply offered what the loop had refused, so it was discarded. "
            "The fixed sentences were translated instead, and the translation checked "
            "against the refusal again.",
        )
    return (
        "rule", f"Model unavailable or overruled — fixed sentences state the verdict "
                f"({language} requested)",
        "Gemma could not be reached, or wrote something that contradicted the verdict. "
        "The reply is the fixed sentences, exactly as assembled from the facts.",
    )


def _speak(run: Run) -> None:
    """Write the answer the diner actually reads, in their language where possible."""
    started = time.perf_counter()
    writer: str | None = None
    if rules_mode():
        original, english = compose_rules_reply(run)
    else:
        original, english, writer = compose_reply(run)
    elapsed = int((time.perf_counter() - started) * 1000)

    run.explanation, run.explanation_en = original, english
    language = run.intent.language if run.intent else "en"
    engine, title, reasoning = _reply_label(writer, language)
    run.add(Step(
        n=0, tool="compose_reply", engine=engine,
        title=title, reasoning=reasoning,
        args={"verdict": run.verdict, "language": language},
        result={"verdict": run.verdict},
        duration_ms=elapsed,
    ))
