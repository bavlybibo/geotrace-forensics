from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Iterable

COMMON_TESSERACT_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\PC\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
)


def _candidate_paths() -> Iterable[str]:
    env_path = os.getenv("GEOTRACE_TESSERACT_CMD") or os.getenv("TESSERACT_CMD")
    if env_path:
        yield env_path
    which = shutil.which("tesseract")
    if which:
        yield which
    yield from COMMON_TESSERACT_PATHS


def resolve_tesseract_binary() -> str:
    """Return a usable Tesseract executable path, or an empty string if it is not available."""
    for candidate in _candidate_paths():
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists() and path.is_file():
            return str(path)
        # shutil.which already resolves bare commands; keep this fallback for custom names.
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return ""


def configure_pytesseract(pytesseract_module) -> str:
    """Configure pytesseract from env/PATH/common Windows locations without hard failing."""
    binary = resolve_tesseract_binary()
    if binary and pytesseract_module is not None:
        try:
            pytesseract_module.pytesseract.tesseract_cmd = binary
        except Exception:
            pass
    return binary
