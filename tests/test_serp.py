"""The manufacturer lookup fails closed, and never poisons its own cache.

An empty search result once landed in `fixtures/serp/` as `[]`, and every later
run read that file back as a real answer: the lookup looked as though it had
been done and found nothing, for as long as the file existed. An empty result is
now never written, and an empty cache file is treated as a miss.

Results from hosts outside the trusted list are kept as context but marked
`trusted: False`. Only a trusted declaration counts as evidence, and even then
it never clears a dish on its own — the kitchen is still asked.

No network: the HTTP call is replaced in every test.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from safeplate import loop, serp
from safeplate.speech import Intent


def _payload(*results: tuple[str, str]) -> dict[str, Any]:
    """A SerpApi response carrying the given (link, snippet) organic results."""
    return {"organic_results": [{"link": link, "snippet": snippet} for link, snippet in results]}


class _FakeResponse(io.BytesIO):
    """Stands in for the object `urlopen` returns, context manager included."""

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


@pytest.fixture
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the cache at a temporary folder and supply a dummy key."""
    monkeypatch.setattr(serp, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("SERPAPI_KEY", "test-key")
    monkeypatch.delenv("SERPAPI_KEY_FALLBACK", raising=False)
    return tmp_path


@pytest.fixture
def http(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replace the HTTP call; tests set `payload` and read `calls`."""
    state: dict[str, Any] = {"payload": _payload(), "calls": 0}

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        state["calls"] += 1
        return _FakeResponse(json.dumps(state["payload"]).encode())

    monkeypatch.setattr(serp.urllib.request, "urlopen", fake_urlopen)
    return state


# --- the cache ---------------------------------------------------------------


def test_empty_result_is_not_cached(cache_dir: Path, http: dict[str, Any]) -> None:
    """Nothing found is not an answer worth remembering."""
    assert serp.lookup_product("fish sauce") == []
    assert list(cache_dir.iterdir()) == []


def test_empty_result_is_retried_next_time(cache_dir: Path, http: dict[str, Any]) -> None:
    """Because nothing was cached, the next run searches again."""
    serp.lookup_product("fish sauce")
    serp.lookup_product("fish sauce")
    assert http["calls"] == 2


def test_empty_cache_file_is_a_miss(cache_dir: Path, http: dict[str, Any]) -> None:
    """A `[]` left by an older build is ignored, not read back as evidence."""
    serp._cache_path("fish sauce allergens ingredients").write_text("[]", encoding="utf-8")
    http["payload"] = _payload(
        ("https://www.tesco.com/fish-sauce", "Ingredients: Anchovy extract (fish), salt."),
    )
    statements = serp.lookup_product("fish sauce")
    assert http["calls"] == 1
    assert [item.source for item in statements] == ["tesco.com"]


def test_non_empty_result_is_cached(cache_dir: Path, http: dict[str, Any]) -> None:
    """A real result is written once and read back without another search."""
    http["payload"] = _payload(
        ("https://www.tesco.com/fish-sauce", "Ingredients: Anchovy extract (fish), salt."),
    )
    first = serp.lookup_product("fish sauce")
    second = serp.lookup_product("fish sauce")
    assert http["calls"] == 1
    assert first == second
    assert len(list(cache_dir.iterdir())) == 1


def test_cache_hit_is_read_without_a_key(cache_dir: Path, http: dict[str, Any],
                                         monkeypatch: pytest.MonkeyPatch) -> None:
    """The offline demo path: a cached query needs neither network nor key."""
    monkeypatch.delenv("SERPAPI_KEY")
    record = [{"source": "tesco.com", "url": "https://www.tesco.com/x",
               "text": "Contains fish.", "declares": ["fish"], "trusted": True}]
    serp._cache_path("tahini sauce allergens ingredients").write_text(
        json.dumps(record), encoding="utf-8")
    statements = serp.lookup_product("tahini sauce")
    assert http["calls"] == 0
    assert statements == [serp.Statement(**record[0])]


def test_cache_written_before_the_trusted_flag_reads_as_untrusted(
        cache_dir: Path, http: dict[str, Any]) -> None:
    """An old record has no `trusted` field; it must not be promoted by default."""
    record = [{"source": "tesco.com", "url": "https://www.tesco.com/x",
               "text": "Contains fish.", "declares": ["fish"]}]
    serp._cache_path("fish sauce allergens ingredients").write_text(
        json.dumps(record), encoding="utf-8")
    [statement] = serp.lookup_product("fish sauce")
    assert statement.trusted is False


def test_cache_never_holds_the_key(cache_dir: Path, http: dict[str, Any]) -> None:
    """The key travels in the request URL; it must not reach the fixture."""
    http["payload"] = _payload(
        ("https://www.tesco.com/fish-sauce", "Ingredients: Anchovy extract (fish), salt."),
    )
    serp.lookup_product("fish sauce")
    for path in cache_dir.iterdir():
        assert "test-key" not in path.read_text(encoding="utf-8")


def test_no_key_and_no_cache_is_unavailable(cache_dir: Path, http: dict[str, Any],
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a key the lookup raises, and the loop reads that as unconfirmed."""
    monkeypatch.delenv("SERPAPI_KEY")
    with pytest.raises(serp.SerpUnavailable):
        serp.lookup_product("fish sauce")


# --- trust -------------------------------------------------------------------


def test_untrusted_hosts_are_kept_but_marked(cache_dir: Path, http: dict[str, Any]) -> None:
    """A recipe blog is context, not a declaration."""
    http["payload"] = _payload(
        ("https://www.tesco.com/fish-sauce", "Ingredients: Anchovy extract (fish), salt."),
        ("https://someblog.example/fish-sauce", "Fish sauce is made from anchovies."),
    )
    statements = serp.lookup_product("fish sauce")
    assert [(item.source, item.trusted) for item in statements] == [
        ("tesco.com", True), ("someblog.example", False),
    ]


def test_trust_is_matched_on_the_host_not_the_path(cache_dir: Path,
                                                    http: dict[str, Any]) -> None:
    """A retailer's name in someone else's URL path earns no trust."""
    http["payload"] = _payload(
        ("https://someblog.example/tesco-fish-sauce", "Anchovy, salt."),
    )
    [statement] = serp.lookup_product("fish sauce")
    assert statement.trusted is False


def test_is_confirmed_needs_a_trusted_statement() -> None:
    """Empty and untrusted-only results are both unconfirmed."""
    trusted = serp.Statement("tesco.com", "u", "Contains fish.", ["fish"], trusted=True)
    untrusted = serp.Statement("blog.example", "u", "Contains fish.", ["fish"], trusted=False)
    assert serp.is_confirmed([]) is False
    assert serp.is_confirmed([untrusted]) is False
    assert serp.is_confirmed([untrusted, trusted]) is True


# --- disagreement --------------------------------------------------------------


def test_sources_conflict_when_one_declares_and_another_is_silent() -> None:
    """Disagreement is grounds to refuse, never to average."""
    declaring = serp.Statement("tesco.com", "u", "Contains sesame.", ["sesame"], trusted=True)
    silent = serp.Statement("ocado.com", "u", "Chickpeas, oil.", [], trusted=True)
    assert serp.sources_conflict([declaring, silent], "sesame") is True


def test_sources_agree_when_all_declare() -> None:
    """Two sources declaring the same allergen are not in conflict."""
    first = serp.Statement("tesco.com", "u", "Contains sesame.", ["sesame"], trusted=True)
    second = serp.Statement("ocado.com", "u", "Sesame seed paste.", ["sesame"], trusted=True)
    assert serp.sources_conflict([first, second], "sesame") is False


def test_no_statements_is_no_conflict() -> None:
    """Nothing to disagree about — which is unconfirmed, not agreement."""
    assert serp.sources_conflict([], "fish") is False


# --- the loop reads an unconfirmed lookup as unconfirmed ----------------------


def _run_with_lookup(monkeypatch: pytest.MonkeyPatch, dish: str, avoid: list[str],
                     statements: list[serp.Statement]) -> loop.Run:
    """Run the loop offline with a fixed lookup result."""
    intent = Intent(utterance="typed", language="en", dish=dish, avoid=avoid)
    monkeypatch.setattr(loop, "understand_text", lambda text: intent)
    monkeypatch.setattr(loop, "compose_reply", lambda run: ("reply", "reply", "gemma"))
    monkeypatch.setattr(serp, "lookup_product", lambda product, **_: statements)
    run = loop.Run(run_id="SP-SERP")
    loop.begin(run, text="typed")
    return run


def _lookup_step(run: loop.Run) -> loop.Step:
    return next(step for step in run.steps if step.tool == "lookup_product")


@pytest.mark.parametrize("statements", [
    [],
    [serp.Statement("someblog.example", "u", "Tahini is just sesame.", ["sesame"],
                    trusted=False)],
])
def test_unconfirmed_lookup_never_clears(monkeypatch: pytest.MonkeyPatch,
                                         statements: list[serp.Statement]) -> None:
    """Empty or untrusted-only evidence is labelled unconfirmed and the kitchen is asked."""
    run = _run_with_lookup(monkeypatch, "falafel plate", ["sesame"], statements)
    step = _lookup_step(run)
    assert step.result["confirmed"] is False
    assert "unconfirmed" in (step.note or "").lower()
    assert run.status == "awaiting_human"
    assert run.verdict is None


def test_trusted_lookup_is_confirmed_but_still_asks(monkeypatch: pytest.MonkeyPatch) -> None:
    """A real declaration is evidence; it is still not a clearance."""
    statements = [serp.Statement("tesco.com", "u", "Contains sesame.", ["sesame"],
                                 trusted=True)]
    run = _run_with_lookup(monkeypatch, "falafel plate", ["sesame"], statements)
    assert _lookup_step(run).result["confirmed"] is True
    assert run.status == "awaiting_human"


def test_trace_evidence_carries_trust(monkeypatch: pytest.MonkeyPatch) -> None:
    """The interface can tell a retailer's declaration from a blog snippet."""
    statements = [
        serp.Statement("tesco.com", "u", "Contains sesame.", ["sesame"], trusted=True),
        serp.Statement("someblog.example", "u", "Sesame.", ["sesame"], trusted=False),
    ]
    run = _run_with_lookup(monkeypatch, "falafel plate", ["sesame"], statements)
    assert [item["trusted"] for item in run.as_trace()["evidence"]] == [True, False]


# --- what counts as a declaration ------------------------------------------------


TESCO_DISCLAIMER = serp.Statement(
    "bevasarlas.tesco.hu", "u",
    "... ingredients, nutrition content, dietary and allergens may change. You should "
    "always read the product label and not rely solely on the information provided ...",
    [], trusted=True,
)
AMAZON_MARKETING = serp.Statement(
    "amazon.co.uk", "u",
    "Tamarind paste is a pure, high quality Indian tamarind concentrate.", [], trusted=True,
)


def test_a_retailer_disclaimer_is_not_a_declaration() -> None:
    assert serp.is_confirmed([TESCO_DISCLAIMER]) is False


def test_marketing_copy_is_not_a_declaration() -> None:
    assert serp.is_confirmed([AMAZON_MARKETING, TESCO_DISCLAIMER]) is False


@pytest.mark.parametrize("text", [
    "Ingredients: Tamarind (92%), water, salt.",
    "Contains sesame.",
    "Allergens: none declared.",
])
def test_a_trusted_ingredient_or_allergen_statement_confirms(text: str) -> None:
    statement = serp.Statement("tesco.com", "u", text, [], trusted=True)
    assert serp.is_confirmed([statement]) is True


def test_the_cached_tamarind_lookup_is_unconfirmed() -> None:
    statements = serp.lookup_product("tamarind paste")
    assert serp.is_confirmed(statements) is False


@pytest.mark.parametrize(("host", "trusted"), [
    ("www.tesco.com", True),
    ("bevasarlas.tesco.hu", True),
    ("www.amazon.co.uk", True),
    ("world.openfoodfacts.org", True),
    ("www.e.leclerc", True),
    ("amazon.evil.example", False),
    ("squidward.example", False),
    ("casinoroyale.example", False),
    ("mytesco.example", False),
])
def test_trust_is_matched_on_the_registrable_domain(host: str, trusted: bool) -> None:
    assert serp._is_trusted_host(host) is trusted


# --- a disagreement between sources ------------------------------------------------


CONFLICTING = [
    serp.Statement("tesco.com", "u", "Contains sesame.", ["sesame"], trusted=True),
    serp.Statement("ocado.com", "u", "Ingredients: chickpeas, oil.", [], trusted=True),
]


def test_a_conflict_on_an_ingredient_left_off_does_not_decide_the_case(
        monkeypatch: pytest.MonkeyPatch) -> None:
    run = _run_with_lookup(monkeypatch, "falafel plate", ["sesame"], CONFLICTING)
    step = _lookup_step(run)
    assert step.result["conflict"] is True
    assert "left off" in (step.note or "")
    assert "grounds to refuse" not in (step.note or "")
    assert run.status == "awaiting_human"


def test_a_conflict_on_a_packaged_ingredient_that_stays_refuses(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loop, "PACKAGED", {*loop.PACKAGED, "pine nuts"})
    run = _run_with_lookup(monkeypatch, "pesto pasta", ["nuts"], [
        serp.Statement("tesco.com", "u", "Contains nuts.", ["nuts"], trusted=True),
        serp.Statement("ocado.com", "u", "Ingredients: pine kernels.", [], trusted=True),
    ])
    step = _lookup_step(run)
    assert step.result["conflict"] is True
    assert "grounds to refuse" in (step.note or "")
    assert run.status == "complete"
    assert run.verdict == "do_not_serve"
    assert run.steps[-2].forced_by == "sources disagree about an ingredient that stays"
