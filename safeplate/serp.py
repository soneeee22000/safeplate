"""Manufacturer allergen declarations, via SerpApi.

Nutrition endpoints are the wrong tool here: a product can be fully described
nutritionally and say nothing about traces of nuts. This searches for the
declaration itself. Every result is kept, but only one from the manufacturer or
a major retailer is marked `trusted` — and only a trusted statement counts as
evidence. Anything else is context the interface can show, never a confirmation.

Every non-empty response is cached to `fixtures/serp/` on the way past, so the
demo runs with the network off and a repeated query costs nothing. An empty
result is never cached: it would be read back as "searched, found nothing" on
every later run, long after a retry might have found the declaration.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from .allergens import EU_14, normalise
from .config import PROJECT_ROOT

SERP_URL = "https://serpapi.com/search"
CACHE_DIR: Path = PROJECT_ROOT / "fixtures" / "serp"
REQUEST_TIMEOUT_SECONDS = 20
RESULT_COUNT = 5

#: Retailers and manufacturers whose allergen statements count as evidence,
#: matched against the registrable name of a host ("tesco" in www.tesco.com or
#: bevasarlas.tesco.hu), never as a substring. Anything else is kept but marked
#: untrusted, and an untrusted-only result is unconfirmed.
TRUSTED_HINTS = (
    "carrefour", "auchan", "leclerc", "monoprix", "intermarche", "casino",
    "tesco", "sainsburys", "waitrose", "ocado", "amazon",
    "openfoodfacts", "thaikitchen", "squid", "redboat", "healthyboy",
)

#: Second-level labels that sit under a country code ("co.uk", "com.au"), so the
#: name before them is the registrable one.
SECOND_LEVEL_SUFFIXES = frozenset({"co", "com", "org", "net", "gov", "ac"})
COUNTRY_CODE_LENGTH = 2

#: What a declaration looks like: an ingredient or allergen list, or a
#: "contains" statement.
DECLARATION_MARKERS = re.compile(
    r"\b(ingredients?|allergens?|allergy advice|ingrédients?|allergènes?)\s*[:(]"
    r"|\b(contains|may contain|contient|peut contenir)\b",
    re.IGNORECASE,
)

#: What a retailer's disclaimer looks like. A snippet that says the information
#: may change is the retailer declining to vouch for it, not a declaration.
DISCLAIMER_MARKERS = (
    "may change", "subject to change", "may be subject to", "should always read",
    "not rely", "peuvent changer", "susceptibles de changer",
)


@dataclass
class Statement:
    source: str
    url: str
    text: str
    declares: list[str]
    #: False by default, so a record from before the flag existed is never promoted.
    trusted: bool = False


class SerpUnavailable(RuntimeError):
    """Raised when no key is configured and nothing is cached."""


def api_keys() -> list[str]:
    """Every configured SerpApi key, primary first.

    A second key is supported because the free plan caps at 250 searches a month
    and a demo is a bad moment to discover the cap. The fallback is only reached
    when the first key is rejected or out of quota — never to double the budget.
    """
    names = ("SERPAPI_KEY", "SERPAPI_KEY_FALLBACK")
    return [value for name in names if (value := os.environ.get(name, "").strip())]


def _cache_path(query: str) -> Path:
    digest = hashlib.sha256(query.encode()).hexdigest()[:16]
    return CACHE_DIR / f"{digest}.json"


def _declared_allergens(text: str) -> list[str]:
    """Pull EU-14 allergens out of a free-text declaration, deterministically."""
    lowered = text.lower()
    found = {allergen for allergen in EU_14 if allergen in lowered}
    for word in ("anchovy", "anchovies", "fish sauce", "shrimp", "peanut", "milk",
                 "soy", "wheat", "sesame", "egg", "molluscs", "crustacean"):
        if word in lowered:
            found.add(normalise(word))
    return sorted(found)


def _registrable_name(host: str) -> str:
    """The label a host is registered under: "tesco" for bevasarlas.tesco.hu.

    A brand top-level domain (www.e.leclerc) has no registrable name below it,
    so the brand label itself is returned.
    """
    labels = host.lower().removeprefix("www.").split(".")
    if len(labels) < 2:
        return labels[0]
    suffix_length = 1
    is_country_code = len(labels[-1]) == COUNTRY_CODE_LENGTH
    if len(labels) >= 3 and is_country_code and labels[-2] in SECOND_LEVEL_SUFFIXES:
        suffix_length = 2
    if labels[-1] in TRUSTED_HINTS:
        return labels[-1]
    return labels[-1 - suffix_length]


def _is_trusted_host(host: str) -> bool:
    """True when the host belongs to a manufacturer or retailer we accept as evidence."""
    return _registrable_name(host) in TRUSTED_HINTS


def _declares_something(statement: Statement) -> bool:
    """True when a statement's text is a declaration, not a disclaimer or advert."""
    lowered = statement.text.lower()
    if any(marker in lowered for marker in DISCLAIMER_MARKERS):
        return False
    return bool(statement.declares) or bool(DECLARATION_MARKERS.search(statement.text))


def _extract(payload: dict) -> list[Statement]:
    """Every usable organic result, each marked trusted or not by its host alone."""
    statements: list[Statement] = []
    for result in payload.get("organic_results", [])[:RESULT_COUNT]:
        link = result.get("link", "")
        snippet = result.get("snippet") or ""
        if not link or not snippet:
            continue
        host = urllib.parse.urlparse(link).netloc.lower()
        statements.append(
            Statement(
                source=host.removeprefix("www."),
                url=link,
                text=snippet.strip(),
                declares=_declared_allergens(snippet),
                trusted=_is_trusted_host(host),
            )
        )
    return statements


def _read_cache(path: Path) -> list[Statement] | None:
    """The cached statements, or None when there is nothing worth reading back.

    An empty list left by an older build is a miss, not an answer.
    """
    if not path.exists():
        return None
    records = json.loads(path.read_text(encoding="utf-8"))
    if not records:
        return None
    return [Statement(**item) for item in records]


def lookup_product(product: str, *, brand: str = "") -> list[Statement]:
    """Search for a product's allergen declaration.

    Returns every usable result, each marked `trusted` or not. An empty or
    untrusted-only list is what the loop treats as "unconfirmed", never as "safe".
    """
    query = " ".join(part for part in (brand, product, "allergens ingredients") if part).strip()
    cached = _cache_path(query)

    hit = _read_cache(cached)
    if hit is not None:
        return hit

    keys = api_keys()
    if not keys:
        raise SerpUnavailable(
            "No SerpApi key is set and this query is not cached. "
            "Put the key in a .env file — see .env.example."
        )

    payload, failures = None, []
    for index, api_key in enumerate(keys):
        params = {'engine': 'google', 'q': query, 'num': RESULT_COUNT, 'api_key': api_key}
        url = f"{SERP_URL}?{urllib.parse.urlencode(params)}"
        try:
            with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read())
            break
        except urllib.error.HTTPError as error:
            # 401 is a bad key, 429 is the monthly quota. Both are worth falling
            # through for; anything else is the query's fault, not the key's.
            failures.append(f"key {index + 1}: HTTP {error.code}")
            if error.code not in (401, 403, 429):
                raise SerpUnavailable(f"SerpApi rejected the query: {error.code}") from error
        except (urllib.error.URLError, OSError) as error:
            failures.append(f"key {index + 1}: {error}")

    if payload is None:
        raise SerpUnavailable(f"every SerpApi key failed — {'; '.join(failures)}")

    statements = _extract(payload)
    if not statements:
        return statements
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_text(
        json.dumps([asdict(item) for item in statements], indent=2), encoding="utf-8"
    )
    return statements


def is_confirmed(statements: list[Statement]) -> bool:
    """True only when a trusted source made an actual declaration.

    Confirmed means there is a manufacturer or retailer declaration to show — not
    that the dish is safe. A retailer's "information may change" disclaimer or a
    product blurb is trusted but declares nothing, so it confirms nothing.
    Nothing here ever clears a dish.
    """
    return any(item.trusted and _declares_something(item) for item in statements)


def sources_conflict(statements: list[Statement], allergen: str) -> bool:
    """True when one source declares the allergen and another omits it entirely.

    Disagreement is never averaged. It is grounds to refuse. Untrusted sources
    count too: they can only add a conflict, and a conflict only ever refuses.
    """
    target = normalise(allergen)
    declaring = [item for item in statements if target in item.declares]
    silent = [item for item in statements if target not in item.declares]
    return bool(declaring) and bool(silent)
