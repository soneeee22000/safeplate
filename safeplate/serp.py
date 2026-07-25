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

    api_key = os.environ.get("SERPAPI_KEY", "").strip()
    if not api_key:
        raise SerpUnavailable(
            "SERPAPI_KEY is not set and this query is not cached. "
            "Put the key in a .env file — see .env.example."
        )

    url = f"{SERP_URL}?{urllib.parse.urlencode({'engine': 'google', 'q': query, 'num': RESULT_COUNT, 'api_key': api_key})}"
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read())
    except (urllib.error.URLError, OSError) as error:
        raise SerpUnavailable(f"SerpApi unreachable: {error}") from error

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
