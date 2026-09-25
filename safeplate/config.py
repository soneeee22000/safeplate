"""Central configuration — paths, mode, model and HTTP settings in one place.

Kept as module-level constants (no magic values scattered across the code). Paths are
resolved relative to the project root so the package runs from anywhere.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Read `.env` into the environment, without adding a dependency.

    Values already set in the real environment win, so a shell export still
    overrides the file. Missing file is not an error — the SerpApi lookup
    degrades to "unconfirmed", which is a safe state.
    """
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return

    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

# --- Mode ---
# `gemma` hears and speaks through the local model. `rules` runs with no model at
# all, for a free host that cannot hold a 7.2 GB download: typed text only, heard
# by keyword matching and answered in fixed sentences. The safety decisions are
# the same code in both modes; only the hearing and the speaking change.
MODE_GEMMA: str = "gemma"
MODE_RULES: str = "rules"
MODES: tuple[str, ...] = (MODE_GEMMA, MODE_RULES)


def _read_mode() -> str:
    """The mode from `SAFEPLATE_MODE`, refusing to start on a value it does not know.

    A typo silently falling back to either mode would hide which one is live, so
    an unknown value stops the process instead.
    """
    value = os.environ.get("SAFEPLATE_MODE", MODE_GEMMA).strip().lower() or MODE_GEMMA
    if value not in MODES:
        raise ValueError(f"SAFEPLATE_MODE must be one of {MODES}, not {value!r}")
    return value


SAFEPLATE_MODE: str = _read_mode()

# --- Model (offline via Ollama) ---
MODEL_NAME: str = "gemma4:e2b"  # E4B OOMs on 16GB; E2B is the demo model

# --- Generation ---
# Zero is required, not preferred: the agent loop compares tool-call decisions
# across turns, and any sampling makes that comparison meaningless.
GENERATION_TEMPERATURE: float = 0.0

# --- HTTP surface ---
#: The interfaces allowed to call the orchestrator from a browser: the local dev
#: server and the deployed site. Overridden by `SAFEPLATE_CORS_ORIGINS`.
DEFAULT_CORS_ORIGINS: tuple[str, ...] = (
    "http://localhost:3000",
    "https://safeplate-ten.vercel.app",
)
CORS_WILDCARD: str = "*"


def parse_cors_origins(value: str | None) -> tuple[str, ...]:
    """The allowed origins from a comma-separated list, or the defaults when empty.

    A wildcard is refused rather than honoured: an orchestrator that any page on
    the web can drive is not a setting anyone should reach by typing one character.

    Raises:
        ValueError: The list contains `*`.
    """
    if value is None or not value.strip():
        return DEFAULT_CORS_ORIGINS
    origins = tuple(
        origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()
    )
    if not origins:
        return DEFAULT_CORS_ORIGINS
    if CORS_WILDCARD in origins:
        raise ValueError("SAFEPLATE_CORS_ORIGINS must list origins; a wildcard is refused")
    return origins


CORS_ORIGINS: tuple[str, ...] = parse_cors_origins(os.environ.get("SAFEPLATE_CORS_ORIGINS"))
