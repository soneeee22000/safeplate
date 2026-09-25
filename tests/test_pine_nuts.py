"""Pine nuts are not an EU-14 allergen, and are still never cleared silently.

Regulation (EU) No 1169/2011, Annex II, point 8 names the nuts that must be
declared: almonds, hazelnuts, walnuts, cashews, pecans, Brazil nuts, pistachios
and macadamia nuts. Pine nuts are not on the list. A label that does not bold
"pignons de pin" is therefore compliant, and SafePlate must not say otherwise.

Many tree-nut-allergic diners avoid pine nuts all the same. So pine nuts carry
an advisory rather than an allergen: they never count as a declared EU-14
allergen, and they always hold a nut-allergic diner at `needs_confirmation`.
"""

from __future__ import annotations

from typing import Any, NoReturn

import pytest

from safeplate import allergens, config, dishes, loop, menu_symphony, serp, speech, voice

PINE_NUT_WORDS: tuple[str, ...] = ("pine nut", "pine nuts", "pignon", "pignons de pin")
NUT_ALLERGIC_TERMS: tuple[str, ...] = ("nuts", "tree nuts", "nut", "fruits à coque")


def _model_called(*args: Any, **kwargs: Any) -> NoReturn:
    raise AssertionError("a model was called in rules mode")


def _no_lookup(product: str, *, brand: str = "") -> NoReturn:
    raise serp.SerpUnavailable("offline in tests")


@pytest.fixture
def rules_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the loop with no model, so the verdict comes from the tables alone."""
    monkeypatch.setattr(config, "SAFEPLATE_MODE", config.MODE_RULES)
    for module in (speech, voice):
        monkeypatch.setattr(module, "_post", _model_called)
    monkeypatch.setattr(loop.serp, "lookup_product", _no_lookup)


def _gnocchi_pine_nuts() -> menu_symphony.LabelIngredient:
    tray = menu_symphony.SYMPHONY_MENU["gnocchis pesto vegan"]
    return next(item for item in tray.ingredients if "pignon" in item.name)


@pytest.mark.parametrize("word", PINE_NUT_WORDS)
def test_pine_nuts_are_not_an_eu14_allergen(word: str) -> None:
    assert allergens.normalise(word) not in allergens.EU_14
    assert menu_symphony.to_allergen(word) not in allergens.EU_14


@pytest.mark.parametrize("word", PINE_NUT_WORDS)
def test_pine_nuts_carry_the_tree_nut_adjacent_advisory(word: str) -> None:
    assert allergens.advisories(word) == (allergens.TREE_NUT_ADJACENT,)


def test_the_advisory_says_it_is_not_an_eu14_allergen_and_to_ask() -> None:
    note = allergens.ADVISORIES[allergens.TREE_NUT_ADJACENT].lower()
    assert "not an eu-14 allergen" in note
    assert "ask" in note


def test_a_true_tree_nut_carries_no_advisory() -> None:
    assert allergens.advisories("hazelnut") == ()
    assert allergens.normalise("hazelnut") == "nuts"


@pytest.mark.parametrize("avoid", NUT_ALLERGIC_TERMS)
def test_a_nut_allergy_still_conflicts_with_pine_nuts(avoid: str) -> None:
    assert allergens.conflicts(avoid, [], "pignons de pin")
    assert allergens.conflict_kind(avoid, [], "pignons de pin") == allergens.MATCH_ADVISORY


def test_naming_pine_nuts_is_a_direct_conflict() -> None:
    assert allergens.conflict_kind("pine nuts", [], "pignons de pin") == allergens.MATCH_DIRECT


@pytest.mark.parametrize("avoid", ["milk", "fish", "sesame"])
def test_the_advisory_does_not_reach_unrelated_allergies(avoid: str) -> None:
    assert not allergens.conflicts(avoid, [], "pine nuts")


def test_the_symphony_label_is_compliant_about_pine_nuts() -> None:
    pine_nuts = _gnocchi_pine_nuts()
    assert not set(pine_nuts.allergens) & set(allergens.EU_14)
    assert pine_nuts.declared is False


def test_the_gnocchi_report_flags_an_advisory_not_a_labelling_failure() -> None:
    tray = menu_symphony.SYMPHONY_MENU["gnocchis pesto vegan"]
    report = menu_symphony.report(tray, ["tree nuts"])

    assert [item.ingredient.name for item in report.advisory_conflicts] == ["pignons de pin"]
    assert report.undeclared_conflicts == ()
    assert report.direct_conflicts == ()
    assert report.outcome == "advisory"


def test_pine_nut_explanation_states_the_regulation_honestly() -> None:
    why = menu_symphony.PINE_NUT_WHY.lower()
    assert "not one of the eu-14" in why
    assert "pine nuts are tree nuts" not in why
    assert "compliant" in why


def test_nut_allergic_diner_is_held_on_the_vegan_gnocchi(rules_mode: None) -> None:
    run = loop.Run(run_id="SP-PINE")
    loop.begin(run, text="I have a tree nut allergy. Is the gnocchis pesto vegan ok?")

    assert run.status == "complete"
    assert run.verdict == "needs_confirmation"
    trace = str(run.as_trace()).lower()
    assert "not in the bold allergen text" not in trace
    assert "never bolded" not in trace
    assert "not an eu-14 allergen" in run.explanation_en.lower()


def test_nut_allergic_diner_is_held_on_the_pesto_pasta(rules_mode: None) -> None:
    run = loop.Run(run_id="SP-PESTO")
    loop.begin(run, text="I have a nut allergy, can I have the pesto pasta?")

    assert run.status == "complete"
    assert run.verdict == "needs_confirmation"
    escalate = run.steps[-2]
    assert escalate.tool == "escalate"
    assert "pine nuts" in (escalate.forced_by or "")


def test_pesto_pasta_advisory_is_not_offered_as_a_removal() -> None:
    assessment = dishes.assess("pesto pasta", ["nuts"])
    assert [f.ingredient.name for f in assessment.advisory] == ["pine nuts"]
    assert assessment.adjustable == []
    assert assessment.outcome == "advisory"


def test_diner_who_names_pine_nuts_is_refused_the_pesto_pasta(rules_mode: None) -> None:
    run = loop.Run(run_id="SP-PINE-DIRECT")
    loop.begin(run, text="the pesto pasta without pine nuts")

    assert run.verdict == "do_not_serve"


# --- a peanut allergy is not a tree-nut allergy ------------------------------------


@pytest.mark.parametrize("word", ["peanuts", "peanut", "Peanuts"])
def test_a_peanut_is_only_a_peanut(word: str) -> None:
    assert allergens.expand(word) == ("peanuts",)


def test_peanuts_do_not_meet_the_tree_nut_advisory() -> None:
    assert allergens.conflict_kind("peanuts", [], "pignons de pin") is None


def test_peanut_allergic_diner_is_held_on_the_gnocchi_for_the_workshop(
        rules_mode: None) -> None:
    run = loop.Run(run_id="SP-PEANUT")
    loop.begin(run, text="I'm allergic to peanuts, gnocchi pesto vegan?")

    assert run.verdict == "needs_confirmation"
    assert run.packaged_report is not None
    assert not run.packaged_report.advisory_conflicts
    assert run.steps[-2].forced_by == "workshop declaration covers peanuts"
    assert "pine nut" not in run.explanation_en.lower()
