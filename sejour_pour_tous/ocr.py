"""Document reading — local Tesseract OCR (image -> French text).

E2B's own vision cannot OCR dense admin text, so a dedicated OCR engine does the reading
and Gemma does the understanding. This is the more reliable production pattern anyway.
Runs fully offline once the French traineddata is present in tessdata/.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytesseract
from PIL import Image

from .config import OCR_LANG, TESSDATA_DIR, TESSERACT_EXE


class DocumentReader:
    """Extracts text from an official document image using local Tesseract."""

    def __init__(self, lang: str = OCR_LANG) -> None:
        """Bind the Tesseract binary and language data for offline use."""
        self._lang = lang
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE
        os.environ["TESSDATA_PREFIX"] = str(TESSDATA_DIR)

    def read(self, image_path: str | Path) -> str:
        """Return the OCR'd text of the document at ``image_path``.

        Raises FileNotFoundError if the image is missing so callers fail loudly rather
        than passing empty text downstream.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Document image not found: {path}")
        text = pytesseract.image_to_string(Image.open(path), lang=self._lang)
        return text.strip()
