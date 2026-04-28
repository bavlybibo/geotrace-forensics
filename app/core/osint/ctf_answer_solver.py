from __future__ import annotations

"""CTF Answer Solver Mode.

This turns already-recovered offline evidence into question-aware answer candidates.
It does not browse or reverse-search images. It is designed for CTF/authorized labs
where the analyst must show why an answer is strong and why alternatives are weaker.
"""

from dataclasses import dataclass, asdict
import re
from typing import Any


@dataclass(slots=True)
class ParsedCTFQuestion:
    raw: str
    answer_kind: str
    flag_format: str
    normalized_prompt: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


KIND_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("coordinates", ("coordinate", "gps", "lat", "long", "latitude", "longitude", "exact location")),
    ("landmark", ("landmark", "temple", "bridge", "tower", "museum", "building", "monument", "poi")),
    ("city_state", ("city-state", "city state", "{city-state}", "city and state")),
    ("city", ("city", "town")),
    ("country", ("country", "nation", "region")),
    ("date", ("date", "timestamp", "published", "when")),
    ("map_app", ("map app", "platform", "which app", "google maps")),
    ("route", ("route", "start", "end", "from", "to", "bypass")),
]


def parse_ctf_question(question: str) -> ParsedCTFQuestion:
    raw = str(question or "").strip()
    lower = raw.lower()
    answer_kind = "generic"
    # Flag-format hints should override generic landmark words. Example:
    # "Identify this temple. Flag format: byuctf{City-State}" expects a city/state,
    # not the temple name.
    if "city-state" in lower or "city state" in lower or "{city-state}" in lower or "city and state" in lower:
        answer_kind = "city_state"
    else:
        for kind, tokens in KIND_PATTERNS:
            if any(token in lower for token in tokens):
                answer_kind = kind
                break
    flag_format = ""
    fmt = re.search(r"(?:flag\s*format|format)\s*[:\-]?\s*([A-Za-z0-9_{}:.,/\\|<>\-\s]+)", raw, re.I)
    if fmt:
        flag_format = re.sub(r"\s+", " ", fmt.group(1)).strip()
    brace = re.search(r"\b([A-Za-z0-9_]+)\{[^}]+\}", raw)
    if brace and not flag_format:
        flag_format = brace.group(0)
    return ParsedCTFQuestion(raw=raw, answer_kind=answer_kind, flag_format=flag_format, normalized_prompt=lower)


def _clean(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower() in {"unknown", "unavailable", "none", "n/a", "no stable answer yet"}:
        return ""
    return text


def _candidate_rows(record: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in getattr(record, "geo_candidates", []) or []:
        if isinstance(candidate, dict) and candidate.get("status", "needs_review") != "rejected":
            rows.append(candidate)
    rows.sort(key=lambda row: (-int(row.get("confidence", 0) or 0), str(row.get("name", "")).lower()))
    return rows


def format_flag_answer(answer: str, flag_format: str) -> str:
    answer = _clean(answer)
    if not answer:
        return "No stable answer yet"
    fmt = _clean(flag_format)
    normalized = answer.strip()
    if re.search(r"\{[^}]+\}", fmt):
        prefix = fmt.split("{", 1)[0]
        # BYU-style examples usually expect spaces converted to hyphens inside braces.
        inner = normalized.replace(", ", "-").replace(",", "-").replace(" ", "-")
        return f"{prefix}" + "{" + inner + "}"
    return normalized


def solve_ctf_answer(record: Any, question: str = "") -> dict[str, Any]:
    parsed = parse_ctf_question(question)
    candidates = _candidate_rows(record)
    estimate = _clean(getattr(record, "location_estimate_label", ""))
    country = _clean(str(getattr(record, "ctf_country_region_profile", "")).split("(", 1)[0])
    city = _clean(getattr(record, "candidate_city", ""))
    area = _clean(getattr(record, "candidate_area", ""))
    map_app = _clean(getattr(record, "map_app_detected", ""))
    route_start = _clean(getattr(record, "map_route_start_label", ""))
    route_end = _clean(getattr(record, "map_route_end_label", ""))

    chosen = ""
    chosen_type = parsed.answer_kind
    why: list[str] = []
    alternatives: list[str] = []

    if parsed.answer_kind == "coordinates":
        chosen = _clean(getattr(record, "derived_geo_display", "")) or _clean(getattr(record, "gps_display", ""))
        why.append("Coordinate questions require GPS or parsed map URL coordinates; OCR labels alone are not enough.")
    elif parsed.answer_kind == "landmark":
        poi = next((c for c in candidates if str(c.get("level", "")) in {"poi", "place", "landmark", "map-url-place"}), None)
        chosen = str(poi.get("name", "")) if poi else estimate
        why.append("Landmark/POI questions prefer verified POI candidates over city/area hints.")
    elif parsed.answer_kind == "city_state":
        if city and area and city.lower() != area.lower():
            chosen = f"{city} {area}"
        else:
            chosen = city or area or estimate
        why.append("City/state format combines the best city/area or city/state fields when both are available.")
    elif parsed.answer_kind == "city":
        chosen = city or area or estimate
        why.append("City questions avoid POI answers unless no city-level signal exists.")
    elif parsed.answer_kind == "country":
        chosen = country
        why.append("Country answer comes from region classifier and known place/offline geocoder corroboration.")
    elif parsed.answer_kind == "map_app":
        chosen = map_app
        why.append("Map-platform question is answered from OCR/UI/provider signals.")
    elif parsed.answer_kind == "route":
        chosen = f"{route_start} -> {route_end}" if route_start and route_end else ""
        why.append("Route questions require separate start/end labels, not just map center.")
    else:
        chosen = estimate or (str(candidates[0].get("name", "")) if candidates else "") or country
        why.append("Generic mode chooses the strongest existing location estimate.")

    for candidate in candidates[:5]:
        name = _clean(candidate.get("name", ""))
        if name and name != chosen:
            alternatives.append(f"{name} ({candidate.get('level', 'level')}, {candidate.get('confidence', 0)}%)")
    if country and country != chosen:
        alternatives.append(f"{country} (country/region fallback)")
    if not chosen:
        chosen = "No stable answer yet"
        why.append("Current evidence has no hard anchor for this question type.")

    confidence = int(getattr(record, "location_estimate_confidence", 0) or 0)
    if candidates:
        confidence = max(confidence, int(candidates[0].get("confidence", 0) or 0))
    if chosen == "No stable answer yet":
        confidence = min(confidence, int(getattr(record, "map_answer_readiness_score", 0) or 0))

    timeline = []
    if getattr(record, "ocr_confidence", 0):
        timeline.append({"stage": "OCR", "confidence": int(getattr(record, "ocr_confidence", 0) or 0), "note": "Visible text/labels extracted."})
    if getattr(record, "map_intelligence_confidence", 0):
        timeline.append({"stage": "Map Intelligence", "confidence": int(getattr(record, "map_intelligence_confidence", 0) or 0), "note": getattr(record, "map_anchor_status", "")})
    if getattr(record, "location_solvability_score", 0):
        timeline.append({"stage": "CTF Solvability", "confidence": int(getattr(record, "location_solvability_score", 0) or 0), "note": getattr(record, "location_solvability_label", "")})
    if getattr(record, "manual_crop_assets", []):
        timeline.append({"stage": "Manual Crop OCR", "confidence": max(confidence, 55), "note": f"{len(getattr(record, 'manual_crop_assets', []))} crop asset(s) merged."})

    return {
        "parsed_question": parsed.to_dict(),
        "answer": chosen,
        "formatted_answer": format_flag_answer(chosen, parsed.flag_format),
        "answer_type": chosen_type,
        "confidence": max(0, min(100, confidence)),
        "why_this_answer": why[:6],
        "why_not_alternatives": alternatives[:6] or ["No stronger alternative candidate exists in the current evidence."],
        "confidence_timeline": timeline,
        "limitations": [
            "Offline solver only: it formats and ranks existing evidence; it does not browse or reverse-search.",
            "Final CTF submission should be based on verified evidence and exact required flag casing/format.",
        ],
    }
