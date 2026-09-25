"""The HTTP surface, in rules mode: the contract `web/src/lib/orchestrator.ts` polls.

    POST /api/case                  -> { run_id }
    GET  /api/case/{run_id}         -> { run_id, status, pending_question?, trace }
    POST /api/case/{run_id}/answer  -> { run_id, status, trace }

The case runs after the POST has answered, so a slow model never holds the
request open; the interface polls until the run stops. Starlette's test client
finishes background work before handing the response back, so a poll straight
after opening already sees where the loop stopped.
"""

from __future__ import annotations

import time
from typing import Any, NoReturn

import pytest
from fastapi.testclient import TestClient

from safeplate import api, config, loop, serp, speech, voice

VERCEL_ORIGIN = "https://safeplate-ten.vercel.app"
LOCAL_ORIGIN = "http://localhost:3000"


def _model_called(*args: Any, **kwargs: Any) -> NoReturn:
    raise AssertionError("a model was called in rules mode")


def _no_lookup(product: str, *, brand: str = "") -> NoReturn:
    raise serp.SerpUnavailable("offline in tests")


@pytest.fixture(autouse=True)
def rules_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """No model and no network: every decision comes from the tables."""
    monkeypatch.setattr(config, "SAFEPLATE_MODE", config.MODE_RULES)
    for module in (speech, voice):
        monkeypatch.setattr(module, "_post", _model_called)
    monkeypatch.setattr(loop.serp, "lookup_product", _no_lookup)


@pytest.fixture
def client() -> TestClient:
    api.RUNS.clear()
    return TestClient(api.app)


def _open(client: TestClient, text: str = "Can I get the falafel without sesame?") -> str:
    response = client.post("/api/case", data={"text": text})
    assert response.status_code == 200
    return response.json()["run_id"]


def test_health(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["ok"] is True
    assert body["mode"] == config.MODE_RULES
    assert body["open_runs"] == 0


def test_dishes_lists_the_table(client: TestClient) -> None:
    keys = {dish["key"] for dish in client.get("/api/dishes").json()["dishes"]}
    assert {"pad thai", "falafel plate", "pesto pasta"} <= keys


def test_open_case_returns_only_a_run_id(client: TestClient) -> None:
    response = client.post("/api/case", data={"text": "Can I get the falafel without sesame?"})
    assert response.status_code == 200
    assert set(response.json()) == {"run_id"}


def test_open_case_without_input_is_rejected(client: TestClient) -> None:
    assert client.post("/api/case", data={"text": "   "}).status_code == 400


def test_poll_reaches_the_kitchen_question(client: TestClient) -> None:
    run_id = _open(client)
    state = client.get(f"/api/case/{run_id}").json()

    assert state["run_id"] == run_id
    assert state["status"] == "awaiting_human"
    assert "sesame" in state["pending_question"]
    assert state["trace"]["case_id"] == run_id
    assert [step["tool"] for step in state["trace"]["steps"]][-1] == "ask_kitchen"


def test_poll_unknown_run_is_404(client: TestClient) -> None:
    assert client.get("/api/case/SP-NOPE").status_code == 404


def test_answer_completes_the_case(client: TestClient) -> None:
    run_id = _open(client)
    response = client.post(f"/api/case/{run_id}/answer",
                           json={"answer": "No, dedicated fryer and separate board"})

    assert response.status_code == 200
    state = response.json()
    assert state["status"] == "complete"
    assert state["trace"]["verdict"] == "verified"
    assert "pending_question" not in state


def test_a_crash_inside_the_loop_fails_closed(
        client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(run: loop.Run, **kwargs: Any) -> NoReturn:
        raise RuntimeError("table unreadable")

    monkeypatch.setattr(api.loop, "begin", explode)
    state = client.get(f"/api/case/{_open(client)}").json()

    assert state["status"] == "failed"
    assert state["trace"]["verdict"] != "verified"
    assert "error" in state


def test_oversized_audio_is_refused_before_a_run_exists(
        client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "MAX_AUDIO_BYTES", 8)
    response = client.post("/api/case", files={"audio": ("a.wav", b"RIFF" * 4, "audio/wav")})

    assert response.status_code == 413
    assert api.RUNS == {}


def test_the_cap_evicts_a_finished_case_before_an_open_one(
        client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "MAX_RUNS", 2)
    waiting = _open(client)
    finished = _open(client, "Can I have the pad thai please?")
    assert api.RUNS[finished].status == "complete"
    newest = _open(client)

    assert list(api.RUNS) == [waiting, newest]
    assert client.get(f"/api/case/{waiting}").json()["status"] == "awaiting_human"


def test_the_cap_refuses_a_new_case_rather_than_drop_an_open_question(
        client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "MAX_RUNS", 2)
    first, second = _open(client), _open(client)
    response = client.post("/api/case", data={"text": "Can I get the falafel without sesame?"})

    assert response.status_code == 503
    assert list(api.RUNS) == [first, second]
    answered = client.post(f"/api/case/{first}/answer", json={"risk": "unsure"})
    assert answered.status_code == 200


def test_an_open_case_past_its_age_is_dropped_to_make_room(
        client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "MAX_RUNS", 2)
    stale, fresh = _open(client), _open(client)
    api.RUNS[stale].started = time.time() - api.RUN_TTL_SECONDS - 1
    newest = _open(client)

    assert list(api.RUNS) == [fresh, newest]


def test_expired_runs_are_dropped(client: TestClient) -> None:
    stale = _open(client)
    api.RUNS[stale].started = time.time() - api.RUN_TTL_SECONDS - 1
    fresh = _open(client)

    assert list(api.RUNS) == [fresh]


@pytest.mark.parametrize("origin", [LOCAL_ORIGIN, VERCEL_ORIGIN])
def test_cors_allows_the_known_interfaces(client: TestClient, origin: str) -> None:
    response = client.get("/health", headers={"Origin": origin})
    assert response.headers.get("access-control-allow-origin") == origin


def test_cors_refuses_other_origins(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_cors_origins_come_from_the_environment() -> None:
    parsed = config.parse_cors_origins(" https://a.example/ , http://b.example:3000 ,")
    assert parsed == ("https://a.example", "http://b.example:3000")


def test_cors_defaults_when_unset() -> None:
    assert config.parse_cors_origins(None) == (LOCAL_ORIGIN, VERCEL_ORIGIN)
    assert config.parse_cors_origins("  ") == (LOCAL_ORIGIN, VERCEL_ORIGIN)


def test_cors_wildcard_is_refused() -> None:
    with pytest.raises(ValueError, match="wildcard"):
        config.parse_cors_origins("https://a.example,*")
