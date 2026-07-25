"""Central configuration — paths, model, and OCR settings in one place.

Kept as module-level constants (no magic values scattered across the code). Paths are
resolved relative to the project root so the package runs from anywhere.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# --- Model (offline via Ollama) ---
MODEL_NAME: str = "gemma4:e2b"  # E4B OOMs on 16GB; E2B is the demo model

# --- OCR (local Tesseract) ---
TESSERACT_EXE: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSDATA_DIR: Path = PROJECT_ROOT / "tessdata"
OCR_LANG: str = "fra"

# --- Data (versioned corpus lands Wed) ---
CORPUS_DIR: Path = PROJECT_ROOT / "data" / "corpus"

# --- Generation ---
GENERATION_TEMPERATURE: float = 0.1  # low: grounded extraction, not creativity
