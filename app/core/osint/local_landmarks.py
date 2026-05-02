from __future__ import annotations

"""Tiny offline landmark dataset and matcher for CTF GeoLocator.

This is intentionally conservative: it matches textual/OCR aliases and optional local
visual tags only. It does not call external services or claim exact visual recognition.
"""

import json
import os
from pathlib import Path
from typing import Iterable, Any

_DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "osint" / "local_landmarks.json"


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, dict):
        data = data.get("landmarks", [])
    return [item for item in data if isinstance(item, dict)]


def load_local_landmarks() -> list[dict[str, Any]]:
    built_in = _load_json_list(_DATA_PATH)
    custom_path = os.environ.get("GEOTRACE_LANDMARK_INDEX", "").strip()
    if not custom_path:
        return built_in
    custom = _load_json_list(Path(custom_path))
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for item in custom + built_in:
        key = str(item.get("name", "")).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def match_local_landmarks(texts: Iterable[str], visual_tags: Iterable[str] = (), *, limit: int = 8) -> list[dict[str, Any]]:
    blob = "\n".join(str(t or "") for t in texts).lower()
    visual = {str(tag or "").lower() for tag in visual_tags if str(tag or "").strip()}
    matches: list[dict[str, Any]] = []
    for item in load_local_landmarks():
        aliases = [str(x).lower() for x in item.get("aliases", [])]
        tags = {str(x).lower() for x in item.get("visual_tags", [])}
        alias_hits = [alias for alias in aliases if alias and _alias_in_text(alias, blob)]
        visual_hits = sorted(visual.intersection(tags))
        score = 0
        reasons: list[str] = []
        if alias_hits:
            score += min(72, 46 + len(alias_hits) * 12)
            reasons.append("alias/text match: " + ", ".join(alias_hits[:3]))
        if visual_hits:
            score += min(18, len(visual_hits) * 6)
            reasons.append("visual tag overlap: " + ", ".join(visual_hits[:3]))
        if score:
            matches.append(
                {
                    "name": item.get("name", "Unknown landmark"),
                    "country": item.get("country", "Unknown"),
                    "city": item.get("city", "Unknown"),
                    "level": item.get("level", "poi"),
                    "confidence": min(90, score),
                    "reasons": reasons,
                }
            )
    matches.sort(key=lambda row: (-int(row.get("confidence", 0)), str(row.get("name", "")).lower()))
    return matches[:limit]
