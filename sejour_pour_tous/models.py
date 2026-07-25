"""Domain models — the typed data that flows through the pipeline.

Plain dataclasses keep the boundaries explicit: OCR produces text, understanding produces
facts, and (later) grounding produces a cited explanation. No business logic here.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DocFacts:
    """Structured facts extracted from a French immigration document.

    All fields are best-effort from the document text alone. A value of None means the
    document did not state it — never a guess.
    """

    document_type: str
    procedure: str | None
    validity_from: str | None
    validity_to: str | None
    authorizes_work: bool | None
    summary: str
    raw_text: str = field(repr=False)


@dataclass(frozen=True)
class Rule:
    """A single versioned rule from the corpus, with its in-force window and provenance.

    ``valid_to`` of None means "still in force". Dates are ISO 'YYYY-MM-DD' strings so the
    as-of filter is a plain lexical comparison in SQL.
    """

    rule_id: str
    procedure: str
    topic: str
    text: str
    source_id: str
    source_url: str
    valid_from: str
    valid_to: str | None


@dataclass(frozen=True)
class Citation:
    """A single grounded source reference (populated once the corpus lands)."""

    source_id: str
    source_url: str
    valid_from: str | None
    valid_to: str | None


@dataclass(frozen=True)
class Explanation:
    """The final, user-facing answer: plain-language guidance plus its provenance.

    ``redacted_claims`` holds any sentence the post-generation guardrail removed because it
    asserted a figure no in-force rule supports. An empty tuple means every number in the
    guidance was traced back to a cited rule.
    """

    facts: DocFacts
    guidance: str
    deadline: str | None
    citations: tuple[Citation, ...]
    refused: bool
    redacted_claims: tuple[str, ...] = ()
