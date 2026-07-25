"""Central configuration — paths, model, and OCR settings in one place.

Kept as module-level constants (no magic values scattered across the code). Paths are
resolved relative to the project root so the package runs from anywhere.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

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
