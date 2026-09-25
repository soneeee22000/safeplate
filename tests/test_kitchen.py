"""The kitchen's answer is the last gate before a dish clears, so it fails closed.

Every kitchen question is phrased so that YES means risk. A free-text answer only
clears a dish when it is an explicit, unhedged "no risk"; anything hedged,
contradictory or unrecognised stays `needs_confirmation`, and any risk marker
refuses outright. A structured answer (`none` / `risk` / `unsure`) removes the
reading step altogether.

No model is needed: Gemma's two calls are replaced with fixed stand-ins.
"""

from __future__ import annotations

import threading
import time
from typing import Any, NoReturn

import pytest
from fastapi.testclient import TestClient

from safeplate import api, loop
from safeplate.speech import Intent


def _intent(dish: str, avoid: list[str]) -> Intent:
    """A fixed hearing of the diner, standing in for Gemma."""
    return Intent(utterance=f"no {', '.join(avoid)} in the {dish}", language="en",
                  dish=dish, avoid=avoid)


@pytest.fixture(autouse=True)
def no_model(monkeypatch: pytest.MonkeyPatch) -> dict[str, Intent]:
    """Replace both Gemma calls so the loop runs deterministically offline."""
    heard: dict[str, Intent] = {"intent": _intent("pad thai", ["peanuts"])}
    monkeypatch.setattr(loop, "understand_text", lambda text: heard["intent"])
    monkeypatch.setattr(loop, "compose_reply", lambda run: ("reply", "reply", "gemma"))
    return heard


def _awaiting(dish: str = "pad thai", avoid: list[str] | None = None,
              heard: dict[str, Intent] | None = None) -> loop.Run:
    """A run stopped at the kitchen question."""
    if heard is not None:
        heard["intent"] = _intent(dish, avoid or ["peanuts"])
    run = loop.Run(run_id="SP-TEST")
    loop.begin(run, text="typed request")
    assert run.status == "awaiting_human", run.as_trace()
    return run


def _verdict(answer: str) -> str | None:
    run = _awaiting()
    loop.answer_kitchen(run, answer)
    assert run.status == "complete"
    return run.verdict


# --- the strings that used to be misread -------------------------------------


@pytest.mark.parametrize("answer", [
    "No idea",
    "I think there is none but let me check",
    "Not sure",
    "Maybe",
    "Probably not",
    "I don't know",
    "Je ne sais pas",
    "hmm",
    "",
])
def test_hedged_or_unrecognised_answers_never_clear(answer: str) -> None:
    assert _verdict(answer) == "needs_confirmation"


def test_contradictory_yes_with_clearance_is_not_read_as_either() -> None:
    assert _verdict("Yes it is fine, totally separate") == "needs_confirmation"


@pytest.mark.parametrize("answer", [
    "nope",
    "No",
    "No.",
    "None at all, dedicated fryer",
    "Non - bac scelle en usine, aucun crustace dans ce plat ni en service",
])
def test_explicit_unhedged_clearance_verifies(answer: str) -> None:
    assert _verdict(answer) == "verified"


@pytest.mark.parametrize("answer", [
    "Yes",
    "oui",
    "No peanuts in it, but the fryer is shared",
    "We can't guarantee it",
    "may contain traces",
    "No, but I think the oil is shared",
])
def test_any_risk_marker_refuses(answer: str) -> None:
    assert _verdict(answer) == "do_not_serve"


def test_no_is_not_found_inside_other_words() -> None:
    assert _verdict("I know the recipe well") == "needs_confirmation"


# --- structured answers ------------------------------------------------------


@pytest.mark.parametrize(("risk", "verdict"), [
    ("none", "verified"),
    ("risk", "do_not_serve"),
    ("unsure", "needs_confirmation"),
])
def test_structured_answer_maps_directly(risk: str, verdict: str) -> None:
    run = _awaiting()
    loop.answer_kitchen(run, risk=risk)
    assert run.verdict == verdict
    assert run.status == "complete"


def test_structured_none_with_a_worrying_note_does_not_clear() -> None:
    run = _awaiting()
    loop.answer_kitchen(run, "shared fryer though", risk="none")
    assert run.verdict == "needs_confirmation"


def test_structured_note_is_recorded_on_the_trace() -> None:
    run = _awaiting()
    loop.answer_kitchen(run, "dedicated wok", risk="none")
    assert run.verdict == "verified"
    assert run.kitchen_answer == "dedicated wok"
    interpret = next(s for s in run.steps if s.tool == "interpret_answer")
    assert interpret.args["risk"] == "none"


def test_unknown_structured_value_is_rejected() -> None:
    run = _awaiting()
    with pytest.raises(ValueError):
        loop.answer_kitchen(run, risk="fine")
    assert run.status == "awaiting_human"


# --- the question itself -----------------------------------------------------


def test_generic_question_is_phrased_so_yes_means_risk() -> None:
    run = _awaiting()
    question = run.pending_question or ""
    assert "Is there ANY way peanuts could reach this plate" in question
    assert "shared oil, fryer, board, utensils, or a pre-made component?" in question
    assert "can you do it as" not in question.lower()


def test_requested_change_is_an_instruction_not_a_question(
        no_model: dict[str, Intent]) -> None:
    run = _awaiting(heard=no_model)
    question = run.pending_question or ""
    change = question.split("Is there ANY way")[0]
    assert "omit crushed peanuts" in change
    assert "?" not in change


def test_question_without_changes_has_no_instruction(no_model: dict[str, Intent]) -> None:
    run = _awaiting("carbonara", ["bacon"], heard=no_model)
    question = run.pending_question or ""
    assert "no changes needed" not in question
    assert question.startswith("Spaghetti carbonara: Is there ANY way bacon")


# --- the endpoint ------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    api.RUNS.clear()
    return TestClient(api.app)


def _open(client: TestClient) -> str:
    response = client.post("/api/case", data={"text": "no peanuts in the pad thai"})
    assert response.status_code == 200
    run_id = response.json()["run_id"]
    assert api.RUNS[run_id].status == "awaiting_human"
    return run_id


def _answer(client: TestClient, **kwargs: Any) -> Any:
    return client.post(f"/api/case/{_open(client)}/answer", **kwargs)


def test_api_free_text_json_stays_backward_compatible(client: TestClient) -> None:
    response = _answer(client, json={"answer": "No idea"})
    assert response.status_code == 200
    assert response.json()["trace"]["verdict"] == "needs_confirmation"


def test_api_structured_json(client: TestClient) -> None:
    response = _answer(client, json={"risk": "risk", "note": "shared fryer"})
    assert response.status_code == 200
    assert response.json()["status"] == "complete"
    assert response.json()["trace"]["verdict"] == "do_not_serve"


def test_api_structured_form_field(client: TestClient) -> None:
    response = _answer(client, data={"risk": "none"})
    assert response.status_code == 200
    assert response.json()["trace"]["verdict"] == "verified"


def test_api_form_free_text(client: TestClient) -> None:
    response = _answer(client, data={"answer": "nope"})
    assert response.status_code == 200
    assert response.json()["trace"]["verdict"] == "verified"


@pytest.mark.parametrize("body", [
    {"json": {"risk": "fine"}},
    {"json": {"answer": "   "}},
    {"json": {}},
    {"data": {"risk": "maybe"}},
])
def test_api_rejects_unusable_answers(client: TestClient, body: dict[str, Any]) -> None:
    response = _answer(client, **body)
    assert response.status_code in (400, 422)


def test_api_unknown_run_is_404(client: TestClient) -> None:
    response = client.post("/api/case/SP-NOPE/answer", json={"risk": "none"})
    assert response.status_code == 404


# --- clearances that admit the risk ------------------------------------------


@pytest.mark.parametrize("answer", [
    "We don't have a dedicated fryer",
    "There is no separate fryer",
    "No, except the fryer",
    "Non, sauf la friteuse",
    "No, but the oil is reused for the satay",
    "nope, the sauce has peanut oil in it",
    "No. The peanut sauce is made on that board too",
    "Never cleaned between orders",
    "None of our fryers are separate",
    "no, not really",
    "No clue",
    "No way to tell",
    "No, I cannot say",
    "no comment",
    "no one can tell",
    "No, ask the manager",
    "No, not that I know of",
    "No, but we fry it in peanut oil",
    "No peanuts",
    "No, the fryer",
])
def test_a_clearance_word_inside_a_longer_answer_does_not_clear(answer: str) -> None:
    assert _verdict(answer) == "needs_confirmation"


def test_an_answer_naming_the_diners_allergen_does_not_clear(
        no_model: dict[str, Intent], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loop.serp, "lookup_product", _offline)
    run = _awaiting("falafel plate", ["sesame"], heard=no_model)
    loop.answer_kitchen(run, "No, but we fry it in sesame oil")
    assert run.verdict == "needs_confirmation"


def test_structured_none_whose_note_admits_no_dedicated_equipment_does_not_clear() -> None:
    run = _awaiting()
    loop.answer_kitchen(run, "we don't have a dedicated fryer", risk="none")
    assert run.verdict == "needs_confirmation"


def _offline(product: str, **_: Any) -> Any:
    raise loop.serp.SerpUnavailable("offline in tests")


# --- one answer per case ------------------------------------------------------


def _slow_reply(delay: float) -> Any:
    def compose(run: loop.Run) -> tuple[str, str, str]:
        time.sleep(delay)
        return "reply", "reply", "gemma"
    return compose


def test_a_second_answer_while_the_first_is_composing_is_rejected(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loop, "compose_reply", _slow_reply(0.3))
    run = _awaiting()
    outcomes: dict[str, str] = {}

    def answer(name: str, risk: str) -> None:
        try:
            loop.answer_kitchen(run, risk=risk)
            outcomes[name] = "accepted"
        except loop.NotAwaitingAnswer:
            outcomes[name] = "rejected"

    first = threading.Thread(target=answer, args=("risk", "risk"))
    second = threading.Thread(target=answer, args=("none", "none"))
    first.start()
    time.sleep(0.05)
    second.start()
    first.join()
    second.join()

    assert outcomes == {"risk": "accepted", "none": "rejected"}
    assert run.verdict == "do_not_serve"
    assert run.status == "complete"
    assert [s.tool for s in run.steps].count("interpret_answer") == 1


def test_answering_a_finished_case_is_rejected() -> None:
    run = _awaiting()
    loop.answer_kitchen(run, risk="risk")
    with pytest.raises(loop.NotAwaitingAnswer):
        loop.answer_kitchen(run, risk="none")
    assert run.verdict == "do_not_serve"


def test_a_crash_while_composing_never_leaves_a_verified_case_open(
        monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(run: loop.Run) -> NoReturn:
        raise RuntimeError("tts down")

    monkeypatch.setattr(loop, "compose_reply", explode)
    run = _awaiting()
    loop.answer_kitchen(run, "no")

    assert run.status == "complete"
    assert run.verdict == "needs_confirmation"
    assert run.as_trace()["verdict"] == "needs_confirmation"
    assert run.explanation
    assert run.steps[-1].tool == "compose_reply"
    assert run.steps[-1].engine == "rule"


def test_a_crash_while_composing_keeps_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(run: loop.Run) -> NoReturn:
        raise RuntimeError("tts down")

    monkeypatch.setattr(loop, "compose_reply", explode)
    run = _awaiting()
    loop.answer_kitchen(run, risk="risk")

    assert run.status == "complete"
    assert run.verdict == "do_not_serve"


def test_api_second_answer_is_a_conflict(client: TestClient) -> None:
    run_id = _open(client)
    assert client.post(f"/api/case/{run_id}/answer", json={"risk": "risk"}).status_code == 200
    response = client.post(f"/api/case/{run_id}/answer", json={"risk": "none"})
    assert response.status_code == 409
    assert api.RUNS[run_id].verdict == "do_not_serve"


def test_api_concurrent_answers_keep_the_first(
        client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loop, "compose_reply", _slow_reply(0.5))
    run_id = _open(client)
    codes: dict[str, int] = {}

    def post(risk: str) -> None:
        codes[risk] = client.post(f"/api/case/{run_id}/answer", json={"risk": risk}).status_code

    first = threading.Thread(target=post, args=("risk",))
    second = threading.Thread(target=post, args=("none",))
    first.start()
    time.sleep(0.1)
    second.start()
    first.join()
    second.join()

    assert codes == {"risk": 200, "none": 409}
    run = api.RUNS[run_id]
    assert run.verdict == "do_not_serve"
    assert [s.tool for s in run.steps].count("compose_reply") == 1
