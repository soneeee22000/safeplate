"""Central configuration — paths, model, and OCR settings in one place.

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

# --- Model (offline via Ollama) ---
MODEL_NAME: str = "gemma4:e2b"  # E4B OOMs on 16GB; E2B is the demo model
OLLAMA_HOST: str = "http://127.0.0.1:11434"

# --- Generation ---
# Zero is required, not preferred: the agent loop compares tool-call decisions
# across turns, and any sampling makes that comparison meaningless.
GENERATION_TEMPERATURE: float = 0.0

# Gemma 4 E2B emits a chain-of-thought into Ollama's separate `thinking` field —
# invisible output you still wait for. Disabling it cut latency roughly 3x.
DISABLE_THINKING: bool = True

# --- OCR (local Tesseract) ---
TESSERACT_EXE: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSDATA_DIR: Path = PROJECT_ROOT / "tessdata"
OCR_LANG: str = "eng+fra"  # ingredient panels are rarely in a single language
