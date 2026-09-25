"""The trace credits whoever actually wrote the reply the diner reads.

When Gemma is unreachable, or writes an offer the loop already refused, the
reply is the fixed sentences in `voice._fallback`. The step must then say a rule
wrote it: a trace that credits the model for a sentence it never produced is
the kind of quiet overclaim this project exists to avoid.
"""

from __future__ import annotations

from typing import Any, NoReturn

import pytest

from safeplate import config, loop, serp, speech, voice
from safeplate.speech import Intent, SpeechError

FISH_PAD_THAI = "I'm allergic to fish, can I have the pad thai without fish sauce?"


def _unreachable(*args: Any, **kwargs: Any) -> NoReturn:
    raise SpeechError("model unreachable")


def _no_lookup(product: str, *, brand: str = "") -> NoReturn:
    raise serp.SerpUnavailable("offline in tests")


@pytest.fixture(autouse=True)
def gemma_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gemma mode, with intake fixed and the lookup offline."""
    monkeypatch.setattr(config, "SAFEPLATE_MODE", config.MODE_GEMMA)
    intent = Intent(utterance=FISH_PAD_THAI, language="en", dish="pad thai",
                    avoid=["fish"], request_type="modification")
    monkeypatch.setattr(loop, "understand_text", lambda text: intent)
    monkeypatch.setattr(loop.serp, "lookup_product", _no_lookup)


def _compose_step(run: loop.Run) -> loop.Step:
    return next(step for step in run.steps if step.tool == "compose_reply")


def test_an_unreachable_model_is_not_credited_with_the_reply(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(voice, "_post", _unreachable)
    monkeypatch.setattr(speech, "_post", _unreachable)
    run = loop.Run(run_id="SP-DOWN")
    loop.begin(run, text=FISH_PAD_THAI)

    step = _compose_step(run)
    assert run.verdict == "do_not_serve"
    assert step.engine == "rule"
    assert "gemma" not in step.title.lower()
    assert run.explanation == voice._fallback(run)


def test_a_reply_that_contradicted_the_refusal_is_credited_to_the_rule(
        monkeypatch: pytest.MonkeyPatch) -> None:
    offer = "We can offer you the Pad Thai without any added fish sauce instead."
    monkeypatch.setattr(voice, "_write", lambda facts, language: offer)
    run = loop.Run(run_id="SP-OFFER")
    loop.begin(run, text=FISH_PAD_THAI)

    step = _compose_step(run)
    assert step.engine == "rule"
    assert offer not in run.explanation


def test_a_reply_gemma_wrote_is_credited_to_gemma(monkeypatch: pytest.MonkeyPatch) -> None:
    written = "We cannot serve this as requested. Fish sauce is the base of the dish."
    monkeypatch.setattr(voice, "_write", lambda facts, language: written)
    run = loop.Run(run_id="SP-GEMMA")
    loop.begin(run, text=FISH_PAD_THAI)

    step = _compose_step(run)
    assert step.engine == "gemma"
    assert run.explanation == written


def test_a_fixed_reply_gemma_translated_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    offer = "We can offer you the Pad Thai without any added fish sauce instead."
    monkeypatch.setattr(voice, "_write", lambda facts, language: offer)
    monkeypatch.setattr(voice, "_translate", lambda text, language: "Nous ne pouvons pas.")
    run = loop.Run(run_id="SP-TRANSLATED")
    loop.begin(run, text=FISH_PAD_THAI)
    assert run.intent is not None
    run.intent.language = "fr"
    run.steps = [step for step in run.steps if step.tool != "compose_reply"]
    loop._speak(run)

    step = _compose_step(run)
    assert step.engine == "gemma"
    assert "translat" in step.title.lower()
    assert run.explanation == "Nous ne pouvons pas."
