from __future__ import annotations

"""Generate manual OSINT search pivots from OCR and map/location clues.

v12.9 expands the query builder beyond generic phrase searches. It creates safer,
manual pivots for exact OCR phrases, phone numbers, coordinates, domains, map labels,
and candidate places. No query is executed automatically.
"""

import re
from typing import Iterable

_STOP = {"unknown", "unavailable", "none", "n/a", "google maps", "map", "maps", "route"}
_PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{4}\b")
_COORD_RE = re.compile(r"\b-?\d{1,2}\.\d{4,}\s*,\s*-?\d{1,3}\.\d{4,}\b")
_DOMAIN_RE = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", re.I)
_ARABIC_RE = re.compile(r"[\u0600-\u06ff]")


def _clean(value: str) -> str:
    value = re.sub(r"\s+", " ", str(value or "")).strip(" -:|•·,.;")
    return value


def _unique(values: Iterable[str], limit: int = 12) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = _clean(raw)
        if len(value) < 3 or value.lower() in _STOP:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
        if len(out) >= limit:
            break
    return out


def _region_hint(region_profile: str) -> str:
    region = str(region_profile or "").lower()
    if "egypt" in region:
        return "Egypt"
    if "gulf" in region or "middle east" in region:
        return "Middle East"
    if "united kingdom" in region:
        return "UK"
    if "united states" in region:
        return "USA"
    return "Google Maps"


def _query_variants(term: str, region_hint: str) -> list[str]:
    queries: list[str] = []
    if _COORD_RE.search(term):
        coord = _COORD_RE.search(term).group(0)
        queries.extend([coord, f'"{coord}"', f'"{coord}" "Google Maps"'])
        return queries
    phones = _PHONE_RE.findall(term)
    if phones:
        for phone in phones[:2]:
            queries.extend([f'"{phone}"', f'"{phone}" "address"', f'"{phone}" "{region_hint}"'])
    domains = _DOMAIN_RE.findall(term)
    if domains:
        for domain in domains[:2]:
            queries.extend([f'"{domain}"', f'site:{domain}', f'"{domain}" "contact"'])
    if _ARABIC_RE.search(term):
        queries.extend([f'"{term}" "خرائط"', f'"{term}" "مصر"', f'"{term}" "العنوان"'])
    else:
        queries.extend([f'"{term}" "{region_hint}"', f'"{term}" "Google Maps"', f'"{term}" "address"'])
    return queries


def generate_search_queries(
    *,
    ocr_phrases: Iterable[str] = (),
    map_labels: Iterable[str] = (),
    candidates: Iterable[str] = (),
    region_profile: str = "Unknown",
    limit: int = 12,
) -> list[str]:
    terms = _unique([*ocr_phrases, *map_labels, *candidates], limit=20)
    hint = _region_hint(region_profile)
    queries: list[str] = []

    for term in terms:
        queries.extend(_query_variants(term, hint))
        if len(queries) >= limit:
            break

    if terms:
        combined = " ".join(f'"{term}"' for term in terms[:3])
        queries.append(f"{combined} {hint}")

    return _unique(queries, limit=limit)
