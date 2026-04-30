from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import json
import os
import re


class OCRMode(StrEnum):
    OFF = "off"
    QUICK = "quick"
    DEEP = "deep"
    MAP_DEEP = "map_deep"


def normalize_ocr_mode(mode: str | None, *, map_candidate: bool = False) -> str:
    requested = (mode or os.getenv("GEOTRACE_OCR_MODE", "quick")).strip().lower()
    if requested in {"map", "maps", "navigation"}:
        requested = OCRMode.MAP_DEEP.value
    if requested not in {item.value for item in OCRMode}:
        requested = OCRMode.QUICK.value
    if map_candidate and requested == OCRMode.DEEP.value:
        return OCRMode.MAP_DEEP.value
    return requested


@dataclass(frozen=True)
class OCRCacheKey:
    file_sha256: str
    mode: str
    force: bool
    language: str
    version: str = "v9-visual-coordinate-fallback"

    def filename(self) -> str:
        raw = f"{self.file_sha256}.{self.mode}.{self.force}.{self.language}.{self.version}.ocr.json"
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)


def read_ocr_cache(cache_dir: Path, key: OCRCacheKey) -> dict | None:
    path = cache_dir / key.filename()
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def write_ocr_cache(cache_dir: Path, key: OCRCacheKey, payload: dict) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / key.filename()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
