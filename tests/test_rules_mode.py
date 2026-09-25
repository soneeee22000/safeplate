"""Rules mode: the whole loop, with no model anywhere in it.

Gemma 4 E2B is a 7.2 GB download that runs on a laptop, not on a free host. Rules
mode swaps the two things the model does — hearing and speaking — for keyword
matching and hand-assembled sentences, and leaves every safety decision exactly
where it already was. These tests make any model call an error, so a rules-mode
run that quietly reaches Ollama fails loudly instead of looking fine.
"""

from __future__ import annotations

from typing import Any, NoReturn

import pytest
from fastapi.testclient import TestClient

from safeplate import api, config, dishes, intake_rules, languages, loop, serp, speech, voice
from safeplate.speech import Intent


def _model_called(*args: Any, **kwargs: Any) -> NoReturn:
    raise AssertionError("a model was called in rules mode")


def _no_lookup(product: str, *, brand: str = "") -> NoReturn:
    raise serp.SerpUnavailable("offline in tests")


@pytest.fixture(autouse=True)
def rules_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rules mode on, and every path to the model turned into a failure."""
    monkeypatch.setattr(config, "SAFEPLATE_MODE", config.MODE_RULES)
    for module in (speech, voice):
        monkeypatch.setattr(module, "_post", _model_called)
    for name in ("understand_text", "understand_audio", "compose_reply"):
        monkeypatch.setattr(loop, name, _model_called)
    for name in ("understand_text", "understand_audio"):
        monkeypatch.setattr(speech, name, _model_called)
    monkeypatch.setattr(voice, "compose_reply", _model_called)
    monkeypatch.setattr(loop.serp, "lookup_product", _no_lookup)


def _run(text: str) -> loop.Run:
    run = loop.Run(run_id="SP-RULES")
    loop.begin(run, text=text)
    return run


# --- intake ------------------------------------------------------------------


def test_fish_allergy_pad_thai_is_heard_as_a_modification() -> None:
    intent = intake_rules.understand_text(
        "I'm allergic to fish, can I have the pad thai without fish sauce?"
    )
    assert isinstance(intent, Intent)
    assert intent.dish == "pad thai"
    assert "fish" in intent.avoid
    assert intent.request_type == "modification"
    assert intent.language == "en"


def test_a_question_without_a_removal_cue_is_a_question() -> None:
    intent = intake_rules.understand_text("Is there any sesame in the falafel?")
    assert intent.dish == "falafel plate"
    assert intent.avoid == ["sesame"]
    assert intent.request_type == "question"


@pytest.mark.parametrize(
    ("text", "dish"),
    [
        ("Can I get the falafel without sesame?", "falafel plate"),
        ("a margherita with no cheese please", "margherita pizza"),
        ("caesar without anchovy", "caesar salad"),
        ("pâtes carbonara sans oeuf", "carbonara"),
        ("pesto pasta, I'm coeliac", "pesto pasta"),
        ("the gnocchi pesto vegan, no pine nuts", "gnocchis pesto vegan"),
        ("la paella sans poisson", "paella poisson chorizo et poulet"),
        ("bolognese with no celery", "pates bolognaises"),
    ],
)
def test_dish_is_found_the_way_the_loop_routes_it(text: str, dish: str) -> None:
    assert intake_rules.understand_text(text).dish == dish


def test_every_alias_names_a_real_dish() -> None:
    assert set(intake_rules.DISH_ALIASES.values()) <= set(dishes.DISHES)


def test_no_dish_named_is_none_not_a_guess() -> None:
    assert intake_rules.understand_text("I am allergic to peanuts").dish is None


def test_dish_name_words_are_not_read_as_allergens() -> None:
    """'pasta' is a gluten synonym and 'poisson' is fish; naming the dish is not avoiding it."""
    assert intake_rules.understand_text("the pesto pasta without pine nuts").avoid == [
        "pine nuts"
    ]
    assert intake_rules.understand_text("paella poisson chorizo et poulet sans lait").avoid == [
        "milk"
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("sans arachides dans le pad thai", ["peanuts"]),
        ("je suis allergique aux fruits de mer, le tom yum", ["shellfish"]),
        ("no tree nuts in the pesto pasta", ["tree nuts"]),
        ("I'm coeliac, the carbonara please", ["gluten"]),
        ("pad thai without peanuts or eggs", ["peanuts", "eggs"]),
    ],
)
def test_avoid_terms_come_back_in_english(text: str, expected: list[str]) -> None:
    assert intake_rules.understand_text(text).avoid == expected


def test_pasta_beside_the_dish_name_orders_it_rather_than_avoiding_gluten() -> None:
    intent = intake_rules.understand_text("pasta carbonara without cheese")
    assert intent.dish == "carbonara"
    assert intent.avoid == ["cheese"]


def test_every_reported_term_is_plain_english_text() -> None:
    """French and accented keys are translated, so the loop never sees 'sésame'."""
    assert all(english.isascii() for _, english in intake_rules.VOCABULARY)
    assert intake_rules.understand_text("le falafel sans sésame").avoid == ["sesame"]


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("Je suis allergique au poisson, le pad thai sans sauce poisson ?", "fr"),
        ("pad thai sans arachides s'il vous plaît", "fr"),
        ("Can I have the pad thai with no peanuts?", "en"),
    ],
)
def test_language_heuristic(text: str, language: str) -> None:
    assert intake_rules.understand_text(text).language == language


def test_nothing_understood_is_not_actionable() -> None:
    intent = intake_rules.understand_text("hello")
    assert not intent.actionable


# --- the loop, end to end -----------------------------------------------------


def test_pad_thai_fish_refuses_with_forced_steps_and_no_model() -> None:
    run = _run("I'm allergic to fish, can I have the pad thai without fish sauce?")

    assert run.status == "complete"
    assert run.verdict == "do_not_serve"
    forced = [step for step in run.steps if step.forced]
    assert {step.tool for step in forced} >= {"lookup_product", "escalate"}
    assert all(step.engine != "gemma" for step in run.steps)
    assert run.steps[0].engine == "rule"
    assert run.steps[-1].tool == "compose_reply"
    assert run.steps[-1].engine == "rule"
    assert run.explanation.startswith(voice.VERDICT_OPENERS["do_not_serve"])
    assert not voice.contradicts_refusal(run.explanation, run)


def test_falafel_sesame_waits_for_the_kitchen_then_unsure_needs_confirmation() -> None:
    run = _run("Can I get the falafel without sesame?")

    assert run.status == "awaiting_human"
    assert run.pending_question and "sesame" in run.pending_question

    loop.answer_kitchen(run, "", risk="unsure")

    assert run.status == "complete"
    assert run.verdict == "needs_confirmation"
    assert all(step.engine != "gemma" for step in run.steps)
    assert run.steps[-1].engine == "rule"


def test_falafel_kitchen_risk_refuses_without_offering_the_dish_back() -> None:
    run = _run("Can I get the falafel without sesame?")
    loop.answer_kitchen(run, "Falafel goes through the shared fryer", risk="risk")

    assert run.verdict == "do_not_serve"
    assert run.explanation.startswith(voice.VERDICT_OPENERS["do_not_serve"])
    assert "alternative" not in run.explanation.lower()
    assert "harissa" not in run.explanation.lower()
    assert "sesame could reach this plate" in run.explanation
    assert "shared fryer" in run.explanation
    assert not voice.contradicts_refusal(run.explanation, run)


@pytest.mark.parametrize(
    ("risk", "expected"),
    [
        ("none", "The kitchen confirmed no risk of sesame on this plate."),
        ("unsure", "The kitchen could not confirm that sesame stays off this plate."),
    ],
)
def test_structured_kitchen_answers_read_as_sentences(risk: str, expected: str) -> None:
    run = _run("Can I get the falafel without sesame?")
    loop.answer_kitchen(run, "", risk=risk)

    assert run.explanation.endswith(expected)
    assert f"The kitchen said: {risk}" not in run.explanation


def test_rules_reply_step_title_names_the_language_in_words() -> None:
    run = _run("Je suis allergique au céleri. Les pâtes bolognaises, c'est possible ?")
    title = run.steps[-1].title

    assert "requested)" not in title
    assert "in English (the diner spoke French)" in title


def test_an_offer_in_a_rules_reply_is_replaced_by_a_bare_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _run("I'm allergic to fish, can I have the pad thai without fish sauce?")
    monkeypatch.setattr(voice, "_fallback", lambda _run: "Alternative: omit the fish sauce.")

    original, english = voice.compose_rules_reply(run)

    assert english == voice.MINIMAL_REFUSAL
    assert not voice.contradicts_refusal(original, run)


def test_unrecognised_allergen_fails_closed() -> None:
    run = _run("Can I have the pad thai please?")
    assert run.verdict == "needs_confirmation"
    assert run.steps[-2].forced_by == "no allergen understood"


def test_audio_in_rules_mode_fails_with_a_clear_error() -> None:
    run = loop.Run(run_id="SP-AUDIO")
    loop.begin(run, audio=b"RIFF....", audio_format="wav")
    assert run.status == "failed"
    assert run.error == loop.AUDIO_NEEDS_GEMMA


# --- replies ------------------------------------------------------------------


def test_reply_in_a_hand_checked_language_uses_the_checked_sentences() -> None:
    run = _run("I'm allergic to fish, can I have the pad thai without fish sauce?")
    assert run.intent is not None
    run.intent.language = "zh"

    original, english = voice.compose_rules_reply(run)

    assert languages.SAFETY_PHRASES["zh"][languages.SPEAK_TO_STAFF] in original
    assert english.startswith(voice.VERDICT_OPENERS["do_not_serve"])


@pytest.mark.parametrize("language", ["fr", "es", "xx"])
def test_reply_without_checked_sentences_is_english(language: str) -> None:
    run = _run("I'm allergic to fish, can I have the pad thai without fish sauce?")
    assert run.intent is not None
    run.intent.language = language

    original, english = voice.compose_rules_reply(run)

    assert original == english


# --- the endpoint -------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    api.RUNS.clear()
    return TestClient(api.app)


def test_health_reports_the_mode(client: TestClient) -> None:
    assert client.get("/health").json()["mode"] == "rules"


def test_api_audio_is_rejected_in_rules_mode(client: TestClient) -> None:
    response = client.post("/api/case", files={"audio": ("a.wav", b"RIFF", "audio/wav")})
    assert response.status_code == 400
    assert response.json()["detail"] == loop.AUDIO_NEEDS_GEMMA


def test_api_text_runs_without_a_model(client: TestClient) -> None:
    response = client.post("/api/case", data={"text": "Can I get the falafel without sesame?"})
    assert response.status_code == 200
    run_id = response.json()["run_id"]
    assert api.RUNS[run_id].status == "awaiting_human"


# --- partial understanding ------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("I'm allergic to sulfite and dairy, can I have the moules marinieres?",
         ["sulfites", "dairy"]),
        ("allergic to crustacean and egg, pad thai please", ["crustaceans", "eggs"]),
        ("I have a mollusc allergy and no dairy, moules marinieres", ["molluscs", "dairy"]),
        ("je suis allergique aux mollusques et au lait, moules marinières",
         ["molluscs", "milk"]),
        ("allergic to lupine and milk, margherita", ["lupine", "milk"]),
        ("I'm allergic to sulphite, moules marinieres please", ["sulphites"]),
        ("allergique au crustacé, le pad thai", ["crustaceans"]),
    ],
)
def test_singular_plural_and_french_allergen_names_are_heard(
        text: str, expected: list[str]) -> None:
    assert intake_rules.understand_text(text).avoid == expected


@pytest.mark.parametrize(
    ("text", "asked", "change"),
    [
        ("I'm allergic to sulfite and dairy, can I have the moules marinieres?",
         "sulfites", "stock"),
        ("allergic to crustacean and egg, pad thai please", "crustaceans",
         "omit and increase tamarind"),
        ("allergic to lupine and milk, margherita", "lupine", "pizza marinara"),
    ],
)
def test_a_recognised_allergen_never_hides_one_that_was_dropped(
        text: str, asked: str, change: str) -> None:
    run = _run(text)
    assert run.status == "awaiting_human"
    question = run.pending_question or ""
    assert asked in question
    assert change in question


@pytest.mark.parametrize(
    "text",
    [
        "I have a mollusc allergy and no dairy, moules marinieres",
        "je suis allergique aux mollusques et au lait, moules marinières",
    ],
)
def test_a_mollusc_allergy_said_in_the_singular_refuses_the_mussels(text: str) -> None:
    assert _run(text).verdict == "do_not_serve"


@pytest.mark.parametrize(
    "text",
    [
        "I'm allergic to kiwi and milk, the margherita please",
        "allergic to quinoa and egg, pad thai please",
        "I have a kiwi allergy and no dairy, margherita",
        "je suis allergique au kiwi et au lait, la margherita",
    ],
)
def test_an_allergy_word_the_rules_cannot_read_fails_closed(text: str) -> None:
    intent = intake_rules.understand_text(text)
    assert intent.unrecognised

    run = _run(text)
    assert run.status == "complete"
    assert run.verdict == "needs_confirmation"
    assert run.steps[-2].forced_by.startswith("allergen not recognised")


@pytest.mark.parametrize(
    "text",
    [
        "I'm allergic to fish, can I have the pad thai without fish sauce?",
        "I'm allergic to peanuts, can I have the pad thai",
        "I have a severe nut allergy, the pesto pasta please",
        "je suis allergique au poisson, le pad thai sans sauce poisson ?",
        "Can I get the falafel without sesame?",
    ],
)
def test_a_fully_understood_allergy_has_nothing_unrecognised(text: str) -> None:
    assert intake_rules.understand_text(text).unrecognised == []


# --- the dish's name only masks the words that named it --------------------------


def test_an_allergen_said_apart_from_the_dish_name_is_kept() -> None:
    intent = intake_rules.understand_text(
        "je suis allergique aux moules et au beurre, moules marinières"
    )
    assert intent.dish == "moules marinieres"
    assert intent.avoid == ["molluscs", "milk"]


def test_moules_allergy_with_the_dish_named_is_refused() -> None:
    run = _run("je suis allergique aux moules et au beurre, moules marinières")
    assert run.verdict == "do_not_serve"


def test_pasta_said_apart_from_the_dish_name_is_kept() -> None:
    intent = intake_rules.understand_text("no pasta for me, I'll have the pesto pasta")
    assert intent.dish == "pesto pasta"
    assert intent.avoid == ["pasta"]
