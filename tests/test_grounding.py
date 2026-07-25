"""Unit tests for the cite-or-refuse guarantees and deadline arithmetic.

These cover the structural safety of the grounding layer without invoking the model:
deterministic refusal, computed (not hallucinated) deadlines, and source deduplication.
"""

from __future__ import annotations

from sejour_pour_tous.grounding import GroundedExplainer, compute_deadline
from sejour_pour_tous.models import DocFacts, Rule

PROC = "titre_sejour_etudiant_renewal"


def _facts(validity_to: str | None = "14/04/2026") -> DocFacts:
    """A minimal récépissé fact set for testing."""
    return DocFacts(
        document_type="Récépissé", procedure="renewal", validity_from="15/01/2026",
        validity_to=validity_to, authorizes_work=False, summary="receipt", raw_text="…",
    )


def test_refuses_with_no_rules() -> None:
    """No in-force rules => deterministic refusal, no citations, no model call."""
    result = GroundedExplainer().explain(_facts(), rules=[])

    assert result.refused is True
    assert result.citations == ()
    assert "préfecture" in result.guidance


def test_deadline_is_two_months_before_expiry() -> None:
    """Deadline window is computed from the expiry, not generated."""
    text = compute_deadline(_facts("14/04/2026"))
    assert text is not None and "14/02/2026" in text and "14/04/2026" in text


def test_deadline_none_without_expiry() -> None:
    """No expiry on the document => no invented deadline."""
    assert compute_deadline(_facts(validity_to=None)) is None


def test_citations_dedupe_by_source() -> None:
    """Two rules from the same source collapse to a single citation."""
    rules = [
        Rule("a", PROC, "taxe", "100 €", "SP", "url", "2026-01-01", None),
        Rule("b", PROC, "délai", "2 mois", "SP", "url", "2018-01-01", None),
    ]
    result = GroundedExplainer().explain(_facts(), rules)  # note: calls model for guidance
    assert len(result.citations) == 1
    assert result.refused is False
