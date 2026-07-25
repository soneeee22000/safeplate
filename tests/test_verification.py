"""Unit tests for the post-generation guardrail.

The pitch claims the assistant cannot state a fee no rule supports. These tests are what
make that claim true: they exercise the guardrail directly, with no model in the loop, so
a regression shows up as a red test rather than as a wrong number on a projector.
"""

from __future__ import annotations

from sejour_pour_tous.models import DocFacts, Rule
from sejour_pour_tous.verification import enforce_grounding, resolve_rule_references

PROC = "titre_sejour_etudiant_renewal"

RULES = [
    Rule("fee", PROC, "taxe", "Taxe de renouvellement : 100 €.",
         "Lexcase", "url-a", "2026-01-01", None),
    Rule("window", PROC, "délai", "Déposer dans les 2 mois précédant l'expiration.",
         "service-public F17279", "url-b", "2018-01-01", None),
]

FACTS = DocFacts(
    document_type="Récépissé", procedure="renewal", validity_from="15/01/2026",
    validity_to="14/04/2026", authorizes_work=False,
    summary="Receipt valid until 14/04/2026.", raw_text="RECEPISSE 14/04/2026",
)


def test_supported_figures_survive() -> None:
    """A fee and a window that both appear in the rules pass through untouched."""
    guidance = "The fee is 100 euros. Apply within 2 months of expiry."
    kept, redacted = enforce_grounding(guidance, RULES, FACTS)

    assert redacted == ()
    assert "100 euros" in kept


def test_invented_fee_is_redacted() -> None:
    """A figure no in-force rule supports is removed, not shown to the user."""
    guidance = "Apply within 2 months of expiry. The fee is 250 euros."
    kept, redacted = enforce_grounding(guidance, RULES, FACTS)

    assert "250" not in kept
    assert len(redacted) == 1 and "250" in redacted[0]
    assert "2 months" in kept


def test_document_dates_are_supported() -> None:
    """Figures taken from the user's own document count as grounded."""
    guidance = "Your receipt expires on 14/04/2026."
    kept, redacted = enforce_grounding(guidance, RULES, FACTS)

    assert redacted == ()
    assert "14/04/2026" in kept


def test_fully_unsupported_answer_leaves_nothing() -> None:
    """If every sentence is unsupported the guidance empties, forcing a refusal upstream."""
    kept, redacted = enforce_grounding("The fee is 250 euros. You have 9 months.",
                                       RULES, FACTS)

    assert kept == ""
    assert len(redacted) == 2


def test_rule_back_references_resolve_to_sources() -> None:
    """'Rule 2' scaffolding leaks are rewritten to the source that backs the claim."""
    resolved = resolve_rule_references("Pay the fee (Rule 1). File on time (règle 2).", RULES)

    assert "[Lexcase]" in resolved
    assert "[service-public F17279]" in resolved
    assert "Rule 1" not in resolved and "règle 2" not in resolved


def test_out_of_range_rule_reference_is_left_alone() -> None:
    """A reference to a rule that was never provided is not silently mapped to a source."""
    assert "Rule 9" in resolve_rule_references("See Rule 9.", RULES)


def test_currency_amounts_are_not_mistaken_for_rule_numbers() -> None:
    """'(615 €)' must not be rewritten as a citation."""
    assert "615" in resolve_rule_references("Show resources (615 €).", RULES)


def test_digits_inside_a_citation_are_not_treated_as_claims() -> None:
    """A source id like 'service-public F17279' must not get its own sentence redacted."""
    guidance = ("The application must be filed within 2 months of expiry "
                "[service-public F17279].")
    kept, redacted = enforce_grounding(guidance, RULES, FACTS)

    assert redacted == ()
    assert "F17279" in kept


def test_burmese_numerals_match_the_french_corpus() -> None:
    """A Burmese answer stating ၁၀၀ euros is grounded by a rule that says 100 €."""
    kept, redacted = enforce_grounding("အခကြေးငွေမှာ ၁၀၀ ယူရိုဖြစ်သည်။", RULES, FACTS)

    assert redacted == ()
    assert "၁၀၀" in kept


def test_burmese_invented_figure_is_still_caught() -> None:
    """Digit folding must not blunt the guardrail: ၂၅၀ is unsupported and goes."""
    kept, redacted = enforce_grounding("အခကြေးငွေမှာ ၂၅၀ ယူရိုဖြစ်သည်။", RULES, FACTS)

    assert kept == "" and len(redacted) == 1


def test_trailing_zeros_are_significant_in_integers() -> None:
    """A rule stating 100 € must not license the model to claim 1 € or 1000 €."""
    _, redacted_low = enforce_grounding("The fee is 1 euro.", RULES, FACTS)
    _, redacted_high = enforce_grounding("The fee is 1000 euros.", RULES, FACTS)

    assert len(redacted_low) == 1
    assert len(redacted_high) == 1


def test_decimal_amounts_match_their_integer_rule() -> None:
    """'100,00 €' is the same figure as the rule's '100 €' and must survive."""
    kept, redacted = enforce_grounding("The fee is 100,00 euros.", RULES, FACTS)

    assert redacted == () and "100,00" in kept
