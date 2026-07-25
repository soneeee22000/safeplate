"""Manufacturer allergen declarations, via SerpApi.

Nutrition endpoints are the wrong tool here: a product can be fully described
nutritionally and say nothing about traces of nuts. This searches for the
declaration itself and keeps results from the manufacturer or a major retailer.

Every response is cached to `fixtures/serp/` on the way past, so the demo runs
with the network off and a repeated query costs nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
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

#: Domains whose allergen statements we treat as evidence. Anything else is noise.
TRUSTED_HINTS = (
    "carrefour", "auchan", "leclerc", "monoprix", "intermarche", "casino",
    "tesco", "sainsburys", "waitrose", "ocado", "amazon",
    "openfoodfacts", "thaikitchen", "squid", "redboat", "healthyboy",
)


@dataclass
class Statement:
    source: str
    url: str
    text: str
    declares: list[str]


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


def _extract(payload: dict) -> list[Statement]:
    statements: list[Statement] = []
    for result in payload.get("organic_results", [])[:RESULT_COUNT]:
        link = result.get("link", "")
        snippet = result.get("snippet") or ""
        if not link or not snippet:
            continue
        host = urllib.parse.urlparse(link).netloc.lower()
        if not any(hint in host for hint in TRUSTED_HINTS):
            continue
        statements.append(
            Statement(
                source=host.removeprefix("www."),
                url=link,
                text=snippet.strip(),
                declares=_declared_allergens(snippet),
            )
        )
    return statements


def lookup_product(product: str, *, brand: str = "") -> list[Statement]:
    """Search for a product's allergen declaration.

    Returns an empty list when nothing trustworthy is found — which the loop
    treats as "unconfirmed", never as "safe".
    """
    query = " ".join(part for part in (brand, product, "allergens ingredients") if part).strip()
    cached = _cache_path(query)

    if cached.exists():
        return [Statement(**item) for item in json.loads(cached.read_text(encoding="utf-8"))]

    keys = api_keys()
    if not keys:
        raise SerpUnavailable(
            "No SerpApi key is set and this query is not cached. "
            "Put the key in a .env file — see .env.example."
        )

    payload, failures = None, []
    for index, api_key in enumerate(keys):
        url = f"{SERP_URL}?{urllib.parse.urlencode({'engine': 'google', 'q': query, 'num': RESULT_COUNT, 'api_key': api_key})}"
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
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_text(
        json.dumps([asdict(item) for item in statements], indent=2), encoding="utf-8"
    )
    return statements


def sources_conflict(statements: list[Statement], allergen: str) -> bool:
    """True when one source declares the allergen and another omits it entirely.

    Disagreement is never averaged. It is grounds to refuse.
    """
    target = normalise(allergen)
    declaring = [item for item in statements if target in item.declares]
    silent = [item for item in statements if target not in item.declares]
    return bool(declaring) and bool(silent)
