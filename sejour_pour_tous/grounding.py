"""Grounded explanation — cite-or-refuse, the trust core.

Given the document facts and the rules in force, produce a plain-language answer in the
user's language. Two hard guarantees:
  1. If no rule covers the document, REFUSE deterministically — never call the model to
     improvise. This is the 'cite or refuse' thesis made structural, not just prompted.
  2. When rules exist, the model is constrained to them and every rule's source is attached
     as a citation, so each claim is traceable.
The deadline is computed from the document's expiry and the renewal-window rule — arithmetic,
not generation, so it cannot be hallucinated.
"""

from __future__ import annotations

from datetime import date

from .config import MODEL_NAME
from .llm import chat
from .models import Citation, DocFacts, Explanation, Rule
from .verification import enforce_grounding, resolve_rule_references

RENEWAL_WINDOW_MONTHS: int = 2
_REFUSAL: str = (
    "I don't have grounded rules for this document, so I won't guess. "
    "Please confirm your situation with your préfecture."
)
_SYSTEM: str = (
    "You help people with French immigration paperwork. Use ONLY the numbered rules given. "
    "Every statement must be supported by a rule. If the rules do not answer something, say "
    "so and tell the person to confirm with their préfecture. Never invent fees, dates, or "
    "documents. Cite by writing the source name in square brackets, e.g. [service-public "
    "F17279] — never refer to a rule by its number. Answer in {lang}, plainly, in three "
    "short sentences."
)
# Non-Latin scripts tokenize far less efficiently; a shared cap would truncate Burmese and
# Arabic mid-sentence. Measured on E2B with thinking disabled.
_MAX_TOKENS: int = 320
_WIDE_SCRIPT_MAX_TOKENS: int = 700
_WIDE_SCRIPT_LANGUAGES: frozenset[str] = frozenset(
    {"Burmese", "Arabic", "Ukrainian", "Russian", "Thai", "Hindi", "Chinese", "Japanese"})


def _parse_fr_date(value: str | None) -> date | None:
    """Parse a DD/MM/YYYY French date, returning None on anything unparseable."""
    if not value:
        return None
    try:
        day, month, year = (int(p) for p in value.strip().split("/"))
        return date(year, month, day)
    except (ValueError, TypeError):
        return None


def _subtract_months(anchor: date, months: int) -> date:
    """Return the date ``months`` calendar months before ``anchor`` (day preserved)."""
    month_index = anchor.month - 1 - months
    year = anchor.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, anchor.day)


def compute_deadline(facts: DocFacts) -> str | None:
    """Compute the renewal filing window from the document expiry, or None if unknown."""
    expiry = _parse_fr_date(facts.validity_to)
    if expiry is None:
        return None
    window_start = _subtract_months(expiry, RENEWAL_WINDOW_MONTHS)
    return (f"Apply between {window_start.strftime('%d/%m/%Y')} and "
            f"{expiry.strftime('%d/%m/%Y')} (within the {RENEWAL_WINDOW_MONTHS} months "
            f"before expiry).")


def _citations(rules: list[Rule]) -> tuple[Citation, ...]:
    """One citation per distinct source, preserving first-seen order."""
    seen: dict[str, Citation] = {}
    for rule in rules:
        seen.setdefault(rule.source_id, Citation(
            rule.source_id, rule.source_url, rule.valid_from, rule.valid_to))
    return tuple(seen.values())


class GroundedExplainer:
    """Produces a cite-or-refuse :class:`Explanation` from facts and in-force rules."""

    def __init__(self, model: str = MODEL_NAME) -> None:
        """Bind the local model used for grounded generation."""
        self._model = model

    def explain(self, facts: DocFacts, rules: list[Rule], lang: str = "English") -> Explanation:
        """Explain what to do, grounded in ``rules`` — or refuse if there are none.

        The model's answer is not trusted as written: rule back-references are resolved to
        real sources, and any sentence asserting an unsupported figure is removed before
        the user ever sees it.
        """
        if not rules:
            return Explanation(facts, _REFUSAL, None, (), refused=True)
        raw = self._generate(facts, rules, lang)
        cited = resolve_rule_references(raw, rules)
        guidance, redacted = enforce_grounding(cited, rules, facts)
        if not guidance:
            return Explanation(facts, _REFUSAL, None, (), refused=True, redacted_claims=redacted)
        return Explanation(facts, guidance, compute_deadline(facts), _citations(rules),
                           refused=False, redacted_claims=redacted)

    def _generate(self, facts: DocFacts, rules: list[Rule], lang: str) -> str:
        """Generate the grounded answer constrained to the provided rules."""
        numbered = "\n".join(f"{i}. [{r.topic}] {r.text} (source: {r.source_id})"
                             for i, r in enumerate(rules, 1))
        prompt = (f"Document: {facts.summary}\n\nRules in force:\n{numbered}\n\n"
                  "Explain what this person must do to renew, including the fee and deadline.")
        cap = _WIDE_SCRIPT_MAX_TOKENS if lang in _WIDE_SCRIPT_LANGUAGES else _MAX_TOKENS
        return chat(_SYSTEM.format(lang=lang), prompt, model=self._model, max_tokens=cap)
