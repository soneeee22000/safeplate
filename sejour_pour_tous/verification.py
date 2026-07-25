"""Post-generation guardrail — every figure in the answer must trace to a cited rule.

The system prompt asks the model not to invent fees, deadlines or amounts. A prompt is a
request, not a guarantee, so this module checks the output instead of trusting it: each
number the model emitted is matched against the numbers appearing in the rules actually in
force and in the user's own document. A sentence carrying an unsupported figure is removed
from the answer rather than shown, and reported separately.

Numbers are the right unit to police here because they are what the answer is *for* — the
fee, the filing window, the resource threshold, the decision delay. A hallucinated verb is
survivable; a hallucinated 120 euros sends someone to a préfecture with the wrong money.
"""

from __future__ import annotations

import re
import unicodedata

from .models import DocFacts, Rule

_NUMBER: re.Pattern[str] = re.compile(r"\d+(?:[.,]\d+)?")
# A citation is provenance, not a claim, and source ids carry digits ("service-public
# F17279"). Left in place they read as unsupported figures and get grounded sentences
# redacted, so bracketed spans are removed before any number is extracted.
_CITATION_SPAN: re.Pattern[str] = re.compile(r"\[[^\]]*\]")
_SENTENCE_SPLIT: re.Pattern[str] = re.compile(r"(?<=[.!?။؟])\s+")

# The model sometimes cites its own prompt scaffolding ("Rule 2", "règle 2") instead of the
# source. Rewrite those to the real source id; the words cover the languages we generate in.
_RULE_WORDS: str = "|".join([
    "Rules", "Rule", "rules", "rule", "Règles", "règles", "Règle", "règle",
    "Regel", "Regla", "regla", "Правило", "правило", "القاعدة", "قاعدة",
    "စည်းမျဉ်း",
])
_RULE_REF: re.Pattern[str] = re.compile(rf"(?:{_RULE_WORDS})\s*(\d{{1,2}})")
_EMPTY_BRACKETS: re.Pattern[str] = re.compile(r"[\(\[]\s*(?:and|et|,|;|\s)*\s*[\)\]]")


def _normalise(number: str) -> str:
    """Normalise a numeric token so '100,00' and '100' compare equal — but '100' stays 100.

    Trailing zeros are only insignificant after a decimal separator; stripping them from an
    integer would collapse 100 onto 1 and let an invented figure pass as grounded.
    """
    decimal = number.replace(",", ".")
    if "." not in decimal:
        return decimal
    return decimal.rstrip("0").rstrip(".") or "0"


def _fold_digits(text: str) -> str:
    """Rewrite non-ASCII decimal digits as ASCII so scripts compare against the corpus.

    The answer is generated in the user's language: Burmese renders one hundred as ၁၀၀ and
    the sourced rules are in French. Without folding, every Burmese figure looks ungrounded
    and a correct answer gets redacted.
    """
    return "".join(
        str(unicodedata.decimal(char, char)) if not char.isascii() else char
        for char in text
    )


def _numbers_in(text: str) -> set[str]:
    """Return every asserted number in ``text``, ignoring digits inside citations."""
    claims_only = _fold_digits(_CITATION_SPAN.sub(" ", text))
    return {_normalise(match.group()) for match in _NUMBER.finditer(claims_only)}


def _supported_numbers(rules: list[Rule], facts: DocFacts) -> set[str]:
    """Numbers the answer is allowed to assert: those in the rules and in the document."""
    corpus = " ".join(rule.text for rule in rules)
    document = " ".join(filter(None, [facts.summary, facts.validity_from,
                                      facts.validity_to, facts.raw_text]))
    return _numbers_in(corpus) | _numbers_in(document)


def resolve_rule_references(text: str, rules: list[Rule]) -> str:
    """Rewrite 'Rule 2'-style back-references into the bracketed source they came from."""
    def _replace(match: re.Match[str]) -> str:
        index = int(match.group(1)) - 1
        if 0 <= index < len(rules):
            return f"[{rules[index].source_id}]"
        return match.group()

    resolved = _RULE_REF.sub(_replace, text)
    return re.sub(r"\s{2,}", " ", _EMPTY_BRACKETS.sub("", resolved)).strip()


def enforce_grounding(guidance: str, rules: list[Rule],
                      facts: DocFacts) -> tuple[str, tuple[str, ...]]:
    """Strip any sentence asserting a figure no in-force rule or the document supports.

    Args:
        guidance: The model's raw generated answer.
        rules: The rules that were actually in force and passed to the model.
        facts: The document's own extracted facts.

    Returns:
        The surviving guidance, and the sentences that were removed.
    """
    allowed = _supported_numbers(rules, facts)
    kept: list[str] = []
    redacted: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(guidance.strip()):
        if not sentence.strip():
            continue
        unsupported = _numbers_in(sentence) - allowed
        (redacted if unsupported else kept).append(sentence.strip())
    return " ".join(kept), tuple(redacted)
