from __future__ import annotations

"""Deterministic OSINT entity extraction from already-acquired text."""

import re
from typing import Iterable

from .models import OSINTEntity

_URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>'\"()]+", re.I)
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_USERNAME_RE = re.compile(r"(?<![\w.])@[A-Za-z0-9_\.]{3,32}\b")
_PHONE_RE = re.compile(r"(?:\+?20|0)?1[0125][0-9]{8}\b")
_DATE_RE = re.compile(r"\b(?:20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]20\d{2})\b")
_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?\b")


def _unique_entities(entities: Iterable[OSINTEntity], limit: int = 30) -> list[OSINTEntity]:
    out: list[OSINTEntity] = []
    seen: set[tuple[str, str]] = set()
    for entity in entities:
        value = re.sub(r"\s+", " ", entity.value or "").strip(" ,.;:|()[]{}")
        if not value:
            continue
        key = (entity.entity_type, value.lower())
        if key in seen:
            continue
        seen.add(key)
        entity.value = value
        out.append(entity)
        if len(out) >= limit:
            break
    return out


def extract_osint_entities(texts: Iterable[str], *, source: str = "ocr/context") -> list[OSINTEntity]:
    blob = "\n".join(str(text or "") for text in texts)
    entities: list[OSINTEntity] = []
    for match in _URL_RE.finditer(blob):
        entities.append(OSINTEntity(match.group(0), "url", source, confidence=86, sensitivity="external_pivot"))
    for match in _EMAIL_RE.finditer(blob):
        entities.append(OSINTEntity(match.group(0), "email", source, confidence=88, sensitivity="personal_data"))
    for match in _USERNAME_RE.finditer(blob):
        entities.append(OSINTEntity(match.group(0), "username", source, confidence=74, sensitivity="external_pivot"))
    for match in _PHONE_RE.finditer(blob):
        entities.append(OSINTEntity(match.group(0), "phone_like", source, confidence=70, sensitivity="personal_data"))
    for match in _DATE_RE.finditer(blob):
        entities.append(OSINTEntity(match.group(0), "date", source, confidence=70, sensitivity="timeline_pivot"))
    for match in _TIME_RE.finditer(blob):
        entities.append(OSINTEntity(match.group(0), "time", source, confidence=62, sensitivity="timeline_pivot"))
    return _unique_entities(entities)
