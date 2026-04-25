from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:  # pragma: no cover
    from ..models import EvidenceRecord


@dataclass(slots=True)
class ScenePrediction:
    label: str
    confidence: int
    summary: str
    reasons: list[str]
    detected_map_context: str
    possible_place: str
    map_confidence: int


def _first_value(values: Iterable[str], fallback: str = "Unavailable") -> str:
    for value in values:
        text = str(value or "").strip()
        if text and text not in {"Unavailable", "Unknown", "N/A", "None"}:
            return text
    return fallback


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _is_good_place(text: str) -> bool:
    value = str(text or "").strip()
    if value in {"", "Unavailable", "Unknown", "N/A", "None"}:
        return False
    letters = sum(ch.isalpha() for ch in value)
    digits = sum(ch.isdigit() for ch in value)
    if letters == 0:
        return False
    if digits > letters * 2:
        return False
    return True


def _map_visual_score(file_path: Path) -> tuple[bool, int, list[str]]:
    reasons: list[str] = []
    try:
        with Image.open(file_path) as img:
            rgb = img.convert("RGB").resize((96, 96))
            pixels = list(rgb.getdata())
    except Exception:
        return False, 0, reasons

    total = max(1, len(pixels))
    light_ratio = sum(1 for r, g, b in pixels if (r + g + b) / 3 >= 182) / total
    accent_ratio = sum(1 for r, g, b in pixels if max(r, g, b) - min(r, g, b) >= 28 and (r + g + b) / 3 >= 105) / total
    route_ratio = sum(1 for r, g, b in pixels if (b >= 145 and g <= 130 and r <= 150) or (b >= 125 and r >= 70 and g <= 115)) / total
    green_ratio = sum(1 for r, g, b in pixels if g >= r + 12 and g >= b - 10 and g >= 118) / total

    score = 0
    if light_ratio >= 0.42:
        score += 24
        reasons.append("light base palette resembles a map canvas")
    if 0.08 <= accent_ratio <= 0.42:
        score += 14
        reasons.append("colored road/POI accents were detected")
    if route_ratio >= 0.003:
        score += 20
        reasons.append("route-like blue/purple overlay was detected")
    if green_ratio >= 0.04:
        score += 8
        reasons.append("park/landmark-like green regions were detected")
    return score >= 36, min(85, score), reasons


def predict_osint_scene(record: "EvidenceRecord") -> ScenePrediction:
    filename = (record.file_name or "").lower()
    source_type = (record.source_type or "Unknown").strip()
    subtype = (record.source_subtype or "Unknown").strip()
    app = (record.app_detected or "Unknown").strip()
    map_app = getattr(record, "map_app_detected", "Unknown")
    text_blob = " ".join([
        record.visible_text_excerpt,
        record.ocr_raw_text,
        " ".join(record.visible_urls),
        " ".join(record.ocr_map_labels),
        " ".join(record.visible_location_strings),
        " ".join(record.possible_geo_clues),
        " ".join(getattr(record, "landmarks_detected", [])),
        getattr(record, "candidate_city", ""),
        getattr(record, "candidate_area", ""),
    ]).lower()

    map_like, visual_score, visual_reasons = _map_visual_score(record.file_path)
    route_detected = bool(getattr(record, "route_overlay_detected", False))
    map_intel_conf = int(getattr(record, "map_intelligence_confidence", 0) or 0)
    is_screenshot = (
        "screenshot" in source_type.lower()
        or "export" in source_type.lower()
        or "desktop" in subtype.lower()
        or "screen" in filename
    )
    is_map_app = (
        app in {"Google Maps", "Google Earth", "Map Application"}
        or map_app in {"Google Maps", "Google Earth", "Map Application"}
        or any("maps" in url.lower() for url in record.visible_urls)
    )
    clean_place_labels = [
        item for item in [
            *record.ocr_map_labels,
            *record.possible_geo_clues,
            *record.visible_location_strings,
            *getattr(record, "place_candidates", []),
            *getattr(record, "landmarks_detected", []),
            getattr(record, "candidate_city", "Unavailable"),
            getattr(record, "candidate_area", "Unavailable"),
        ]
        if _is_good_place(item)
    ]
    has_map_labels = bool(clean_place_labels)
    has_geo_anchor = record.derived_geo_display != "Unavailable" or record.has_gps

    label = "Screenshot / UI Capture"
    confidence = 54
    reasons: list[str] = []

    if is_map_app or has_map_labels or has_geo_anchor or map_intel_conf >= 50 or (is_screenshot and map_like):
        label = "Map / Navigation Screenshot" if route_detected else "Map / Location Screenshot"
        confidence = max(record.derived_geo_confidence, record.gps_confidence, visual_score, map_intel_conf, 58)
        reasons.append("location-oriented cues were recovered from the screenshot workflow")
        if is_map_app:
            confidence = max(confidence, 84)
            reasons.append(f"application context points to {map_app if map_app != 'Unknown' else app}")
        if route_detected:
            confidence = max(confidence, min(92, int(getattr(record, "route_confidence", 0) or 0) + 8))
            reasons.append("route/navigation overlay is visible")
        if record.derived_geo_display != "Unavailable":
            confidence = max(confidence, 78)
            reasons.append(f"derived geo clue recovered at {record.derived_geo_display}")
        if has_map_labels:
            reasons.append("OCR/map intelligence recovered place labels")
        reasons.extend(visual_reasons[:2])
    elif app in {"WhatsApp", "Telegram", "Signal", "Discord", "Facebook", "Instagram", "X / Twitter"}:
        label = "Messaging / Social Screenshot"
        confidence = 82
        reasons.append(f"application context suggests {app}")
        if record.visible_text_excerpt:
            reasons.append("on-screen text supports a social or chat artifact")
    elif app in {"Chrome", "Safari", "Firefox", "Edge"} or record.visible_urls:
        label = "Browser / Web Screenshot"
        confidence = 74
        reasons.append("visible browser/web indicators were recovered")
    elif source_type == "Camera Photo":
        label = "Real-world Camera Photo"
        confidence = 80 if record.device_model not in {"Unknown", "N/A", ""} else 68
        reasons.append("capture profile is consistent with a camera-origin image")
    elif any(word in text_blob for word in {"document", "report", "invoice", "statement"}):
        label = "Document / Report Screenshot"
        confidence = 70
        reasons.append("recovered text resembles a document-style artifact")
    elif any(word in text_blob for word in {"dashboard", "analysis", "evidence"}):
        label = "Dashboard / Analytical Screenshot"
        confidence = 66
        reasons.append("recovered text resembles an application dashboard")

    possible_place = _first_value([
        record.gps_display,
        record.derived_geo_display,
        *clean_place_labels,
    ])
    if possible_place == record.gps_display and record.gps_display == "Unavailable":
        possible_place = _first_value([record.derived_geo_display, *clean_place_labels])

    if record.has_gps:
        map_context = "Native GPS recovered from embedded metadata."
        map_confidence = max(record.gps_confidence, 90)
    elif record.derived_geo_display != "Unavailable":
        map_context = "Visible map/location clue recovered from screenshot content."
        map_confidence = max(record.derived_geo_confidence, 68)
    elif map_intel_conf > 0:
        map_context = getattr(record, "map_intelligence_summary", "Map intelligence detected context, but no native coordinates were available.")
        map_confidence = map_intel_conf
    elif has_map_labels:
        labels = _unique(clean_place_labels)
        map_context = (
            "Map/place context detected from OCR-visible labels."
            if not labels
            else f"Map/place context detected from visible labels such as {', '.join(labels[:3])}."
        )
        map_confidence = max(55, min(78, 52 + len(labels) * 7))
    elif is_screenshot and map_like:
        map_context = "Visual map-like layout detected, but no stable place text or coordinates were recovered yet."
        map_confidence = max(visual_score, 52)
    else:
        map_context = "No clear map/location context was recovered from the current evidence item."
        map_confidence = 0

    if label.startswith("Map") and possible_place == "Unavailable" and map_confidence >= 50:
        reasons.append("map context exists, but the place anchor still needs corroboration")

    reasons = _unique(reasons)[:4]
    summary = (
        f"OSINT AI read: {label} ({confidence}% confidence). "
        f"Map context: {map_context} "
        f"Possible place: {possible_place}."
    )
    return ScenePrediction(
        label=label,
        confidence=max(0, min(100, confidence)),
        summary=summary,
        reasons=reasons,
        detected_map_context=map_context,
        possible_place=possible_place,
        map_confidence=max(0, min(100, map_confidence)),
    )
