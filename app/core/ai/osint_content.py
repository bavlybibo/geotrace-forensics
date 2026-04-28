from __future__ import annotations

"""Explainable OSINT image-content and location-hypothesis reader.

This module intentionally stays deterministic/offline. It does not claim to identify
people or exact objects. Instead it converts visible text, file/source metadata, map
signals, and lightweight visual statistics into analyst-safe OSINT cues.
"""

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Iterable, TYPE_CHECKING

from PIL import Image, ImageStat

if TYPE_CHECKING:  # pragma: no cover
    from ..models import EvidenceRecord


_ARABIC_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]")

_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Map / navigation context": (
        "google maps", "maps.google", "directions", "route", "street view", "satellite", "nearby",
        "خرائط", "خريطة", "خريطه", "اتجاهات", "المسار", "موقع",
    ),
    "Messaging / social context": (
        "whatsapp", "telegram", "signal", "discord", "messenger", "instagram", "facebook", "twitter", "x.com",
        "typing", "online", "last seen", "reels", "story", "followers",
    ),
    "Browser / web context": (
        "http://", "https://", "www.", ".com", ".org", ".net", "chrome", "edge", "firefox", "safari", "search",
    ),
    "Document / report context": (
        "pdf", "report", "invoice", "receipt", "statement", "document", "signature", "page", "date", "total",
        "تقرير", "فاتورة", "مستند", "تاريخ", "توقيع", "صفحة",
    ),
    "Security / dashboard context": (
        "dashboard", "analysis", "evidence", "risk", "alert", "scan", "vulnerability", "security", "forensic",
        "threat", "log", "incident", "case", "severity",
    ),
    "Location / venue context": (
        "airport", "hospital", "hotel", "school", "university", "bank", "mall", "station", "metro", "street", "road",
        "bridge", "park", "museum", "restaurant", "cafe", "mosque", "church", "tower", "square", "district",
        "مطار", "مستشفى", "فندق", "مدرسة", "جامعة", "بنك", "مول", "محطة", "مترو", "شارع", "طريق",
        "كوبري", "كوبرى", "حديقة", "متحف", "مطعم", "كافيه", "مسجد", "كنيسة", "برج", "ميدان",
    ),
    "Transport / movement context": (
        "route", "directions", "km", "min", "minutes", "eta", "uber", "careem", "taxi", "bus", "metro", "station",
        "airport", "train", "flight", "دقيقة", "كم", "مسار", "اتجاهات", "مطار", "محطة", "مترو", "أوبر", "اوبر",
    ),
}

_VISUAL_LIMITATIONS = [
    "Visual heuristics are not object recognition; they only describe broad image/layout signals.",
    "OCR and map-derived places are investigative leads unless native GPS/source-app data corroborates them.",
]


@dataclass(slots=True)
class OSINTContentProfile:
    label: str = "Unclassified image content"
    confidence: int = 0
    summary: str = "No OSINT content profile generated yet."
    content_tags: list[str] = field(default_factory=list)
    visual_cues: list[str] = field(default_factory=list)
    text_cues: list[str] = field(default_factory=list)
    location_hypotheses: list[str] = field(default_factory=list)
    source_context: str = "Unknown"
    limitations: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)


def _unique(items: Iterable[str], limit: int = 12) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        clean = re.sub(r"\s+", " ", str(item or "")).strip(" -:|•·")
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(clean)
        if len(out) >= limit:
            break
    return out


def _contains_arabic(text: str) -> bool:
    return bool(_ARABIC_RE.search(text or ""))


def _visual_layout_cues(file_path: Path) -> tuple[list[str], int]:
    cues: list[str] = []
    score = 0
    try:
        with Image.open(file_path) as img:
            width, height = img.size
            rgb = img.convert("RGB")
            sample = rgb.resize((96, 96))
            pixels = list(sample.getdata())
            stat = ImageStat.Stat(sample)
    except Exception:
        return ["visual analysis unavailable"], 0

    total = max(1, len(pixels))
    aspect = width / max(1, height)
    brightness = sum((r + g + b) / 3 for r, g, b in pixels) / total
    saturation_like = sum(max(r, g, b) - min(r, g, b) for r, g, b in pixels) / total
    light_ratio = sum(1 for r, g, b in pixels if (r + g + b) / 3 >= 185) / total
    dark_ratio = sum(1 for r, g, b in pixels if (r + g + b) / 3 <= 55) / total
    edge_like = sum(1 for r, g, b in pixels if max(r, g, b) - min(r, g, b) >= 45) / total
    green_ratio = sum(1 for r, g, b in pixels if g >= 118 and g >= r + 10 and g >= b - 8) / total
    blue_route_ratio = sum(1 for r, g, b in pixels if b >= 145 and r <= 150 and g <= 135 and b >= r + 35) / total

    if width >= 900 and height >= 500 and (aspect >= 1.55 or aspect <= 0.65):
        cues.append("screenshot-like wide/tall canvas")
        score += 8
    if light_ratio >= 0.45 and edge_like >= 0.10:
        cues.append("bright UI/map-like layout")
        score += 12
    if dark_ratio >= 0.40 and edge_like >= 0.06:
        cues.append("dark application/UI screenshot")
        score += 10
    if green_ratio >= 0.045:
        cues.append("green outdoor/map-region visual signal")
        score += 6
    if blue_route_ratio >= 0.003:
        cues.append("blue route/line visual signal")
        score += 12
    if saturation_like >= 48 and 70 <= brightness <= 185 and edge_like <= 0.38:
        cues.append("natural-photo color distribution")
        score += 8
    if width and height:
        cues.append(f"dimensions {width}x{height}")
    try:
        # high standard deviation often indicates real-world texture or dense UI; low std often blank/exported.
        mean_std = sum(stat.stddev) / max(1, len(stat.stddev))
        if mean_std < 22:
            cues.append("low-detail/flat exported image")
        elif mean_std > 58:
            cues.append("high-detail visual texture")
    except Exception:
        pass
    return _unique(cues, limit=8), max(0, min(100, score))


def _keyword_tags(text: str) -> tuple[list[str], list[str]]:
    lower = (text or "").lower()
    tags: list[str] = []
    cues: list[str] = []
    for label, tokens in _DOMAIN_KEYWORDS.items():
        matched = [token for token in tokens if token.lower() in lower]
        if matched:
            tags.append(label)
            cues.append(f"{label}: {', '.join(matched[:4])}")
    if _contains_arabic(text):
        tags.append("Arabic visible text")
        cues.append("Arabic OCR/text signals present")
    if re.search(r"[A-Za-z]", text or ""):
        tags.append("English/Latin visible text")
    return _unique(tags, limit=10), _unique(cues, limit=8)


def _source_context(record: "EvidenceRecord") -> str:
    parts = []
    for value in [record.source_type, record.source_subtype, record.app_detected, getattr(record, "map_app_detected", "")]:
        text = str(value or "").strip()
        if text and text not in {"Unknown", "N/A", "Unavailable"}:
            parts.append(text)
    return " / ".join(_unique(parts, limit=4)) or "Unknown"


def _location_hypotheses(record: "EvidenceRecord") -> list[str]:
    hypotheses: list[str] = []
    if record.has_gps:
        hypotheses.append(f"Native GPS: {record.gps_display} ({record.gps_confidence}% confidence) — strongest location anchor.")
    if record.derived_geo_display != "Unavailable":
        hypotheses.append(f"Derived geo: {record.derived_geo_display} ({record.derived_geo_confidence}% confidence) — corroborate with source app/history.")
    if getattr(record, "candidate_city", "Unavailable") != "Unavailable":
        hypotheses.append(f"Candidate city: {record.candidate_city} — lead from map/OCR/filename context.")
    if getattr(record, "candidate_area", "Unavailable") != "Unavailable":
        hypotheses.append(f"Candidate area: {record.candidate_area} — lead from map/OCR/filename context.")
    for landmark in getattr(record, "landmarks_detected", [])[:3]:
        hypotheses.append(f"Landmark/place cue: {landmark} — verify manually before reporting as location.")
    for place in getattr(record, "place_candidates", [])[:3]:
        if place not in " ".join(hypotheses):
            hypotheses.append(f"Place candidate: {place} — OCR/map lead, not proof.")
    for clue in getattr(record, "possible_geo_clues", [])[:2]:
        if clue not in " ".join(hypotheses):
            hypotheses.append(f"Visible geo clue: {clue} — needs corroboration.")
    return _unique(hypotheses, limit=8)


def analyze_image_content(record: "EvidenceRecord") -> OSINTContentProfile:
    """Return an analyst-safe OSINT content read for a single evidence item."""
    text_blob = "\n".join([
        record.file_name,
        record.visible_text_excerpt,
        record.ocr_raw_text,
        " ".join(record.visible_text_lines),
        " ".join(record.visible_urls),
        " ".join(record.ocr_app_names),
        " ".join(record.ocr_map_labels),
        " ".join(record.visible_location_strings),
        " ".join(getattr(record, "place_candidates", [])),
        " ".join(getattr(record, "landmarks_detected", [])),
        str(getattr(record, "candidate_city", "")),
        str(getattr(record, "candidate_area", "")),
    ])

    visual_cues, visual_score = _visual_layout_cues(record.file_path)
    detail_cues = list(getattr(record, "image_detail_cues", []) or [])
    detail_layout = list(getattr(record, "image_layout_hints", []) or [])
    detail_objects = list(getattr(record, "image_object_hints", []) or [])
    detail_quality = list(getattr(record, "image_quality_flags", []) or [])
    detail_regions = list(getattr(record, "image_attention_regions", []) or [])
    detail_scene = list(getattr(record, "image_scene_descriptors", []) or [])
    detail_methodology = list(getattr(record, "image_analysis_methodology", []) or [])
    detail_metrics = dict(getattr(record, "image_detail_metrics", {}) or {})
    detail_strategy = str(detail_metrics.get("analysis_strategy", "") or "")
    detail_quality_gate = str(detail_metrics.get("quality_gate", "") or "")
    detail_corroboration_target = str(detail_metrics.get("corroboration_target", "") or "")
    detail_label = str(getattr(record, "image_detail_label", "") or "")
    detail_confidence = int(getattr(record, "image_detail_confidence", 0) or 0)
    if detail_cues or detail_layout or detail_objects or detail_quality or detail_regions or detail_scene:
        region_cues = []
        for region in detail_regions[:2]:
            if isinstance(region, dict):
                region_cues.append(
                    f"attention region {region.get('region', '?')} score {region.get('attention_score', 0)}: "
                    + ", ".join(str(x) for x in (region.get('reasons', []) or [])[:3])
                )
        strategy_cues = []
        if detail_strategy:
            strategy_cues.append(
                f"image reasoning strategy {detail_strategy}; "
                f"OCR={detail_metrics.get('ocr_priority_score', 0)}, "
                f"map={detail_metrics.get('map_review_priority_score', 0)}, "
                f"geo={detail_metrics.get('geolocation_potential_score', 0)}"
            )
        if detail_quality_gate and detail_quality_gate != "ready_for_triage":
            strategy_cues.append(f"quality gate {detail_quality_gate}")
        visual_cues.extend([*strategy_cues, *detail_scene[:3], *detail_layout[:3], *detail_objects[:3], *detail_quality[:2], *region_cues, *detail_cues[:2]])
        visual_score = max(visual_score, min(88, detail_confidence + (4 if detail_strategy else 0)))
    keyword_tags, text_cues = _keyword_tags(text_blob)
    source_context = _source_context(record)
    location_hypotheses = _location_hypotheses(record)

    tags = list(keyword_tags)
    if detail_label and "unavailable" not in detail_label.lower():
        tags.append(detail_label)
    reasons: list[str] = []
    confidence = max(38, min(74, 36 + visual_score // 2 + min(24, len(text_cues) * 5)))
    label = "General image / low-context artifact"

    map_conf = int(getattr(record, "map_intelligence_confidence", 0) or 0)
    route = bool(getattr(record, "route_overlay_detected", False))
    if map_conf >= 50 or route or any("Map" in tag for tag in tags):
        label = "OSINT map/location artifact"
        confidence = max(confidence, map_conf, 76 if route else 68)
        reasons.append("map/navigation context is the dominant content signal")
    elif any("Messaging" in tag for tag in tags):
        label = "OSINT messaging/social artifact"
        confidence = max(confidence, 76)
        reasons.append("social or messaging UI indicators were recovered")
    elif any("Browser" in tag for tag in tags):
        label = "OSINT browser/web artifact"
        confidence = max(confidence, 70)
        reasons.append("web/browser indicators or visible URLs were recovered")
    elif any("Document" in tag for tag in tags):
        label = "OSINT document/report artifact"
        confidence = max(confidence, 68)
        reasons.append("document/report style terms were recovered from visible text")
    elif any("Security" in tag for tag in tags):
        label = "OSINT dashboard/security artifact"
        confidence = max(confidence, 66)
        reasons.append("dashboard/security workflow words were recovered")
    elif detail_label in {"Outdoor/photo-like image", "Screenshot/UI-rich image", "Map/document-style visual artifact", "Flat/low-information image"}:
        label = detail_label
        confidence = max(confidence, detail_confidence)
        reasons.append("deep image-detail profile provided the dominant visual reading")
    elif record.source_type == "Camera Photo":
        label = "Real-world camera photo"
        confidence = max(confidence, 68 if record.device_model in {"Unknown", "N/A", ""} else 80)
        reasons.append("source metadata resembles camera-origin media")
    elif "screenshot" in record.source_type.lower() or "screen" in record.file_name.lower():
        label = "Generic screenshot / UI capture"
        confidence = max(confidence, 58)
        reasons.append("source profile suggests a screenshot capture")

    if record.visible_urls:
        tags.append("URL pivot available")
        reasons.append("visible URL(s) can be used as OSINT pivots")
    if record.ocr_username_entities:
        tags.append("Username/entity pivot available")
        reasons.append("visible username/entity strings can support external corroboration")
    if location_hypotheses:
        tags.append("Location hypothesis available")
        reasons.append("one or more location hypotheses were generated")
    if getattr(record, "map_evidence_strength", "") in {"lead", "strong_indicator", "proof"}:
        tags.append(f"Map evidence strength: {record.map_evidence_strength}")
    if detail_quality:
        tags.append("Image quality/forensic review needed")
    if detail_objects:
        reasons.append("image-detail cues can guide OCR crops and manual object/location review")
    if detail_regions:
        reasons.append("tile-level attention regions identify where OCR/manual zoom should start")
    if detail_scene:
        reasons.append("scene descriptors convert raw visual metrics into analyst-safe review hypotheses")
    if detail_strategy:
        tags.append(f"Image reasoning strategy: {detail_strategy}")
        reasons.append("image reasoning strategy selected the safest analysis path for this evidence item")

    pixel_score = int(getattr(record, "pixel_hidden_score", 0) or 0)
    pixel_indicators = list(getattr(record, "pixel_hidden_indicators", []) or [])
    pixel_strings = list(getattr(record, "pixel_lsb_strings", []) or [])
    if pixel_score >= 40 or pixel_indicators or pixel_strings:
        tags.append("Pixel-level hidden-content lead")
        visual_cues.extend(pixel_indicators[:3] or [getattr(record, "pixel_hidden_verdict", "Pixel-level review required")])
        reasons.append("pixel-level LSB/alpha heuristics produced a hidden-content lead")
        if label == "General image / low-context artifact":
            label = "Image with pixel-level hidden-content lead"
        confidence = max(confidence, min(92, 62 + pixel_score // 2))

    next_actions: list[str] = []
    if location_hypotheses:
        next_actions.append("Corroborate location hypotheses with native GPS, source-app share links/history, device logs, or manual map review.")
    if record.visible_urls:
        next_actions.append("Preserve visible URLs as pivots, but redact them from external reports unless explicitly needed.")
    if record.ocr_username_entities:
        next_actions.append("Treat usernames/entities as sensitive; use them for scoped OSINT pivots only after confirming permission and relevance.")
    if map_conf >= 50 and not record.has_gps:
        next_actions.append("Do not claim device location from map screenshots alone; label it as searched/displayed place unless corroborated.")
    if int(getattr(record, "pixel_hidden_score", 0) or 0) >= 40 or getattr(record, "pixel_lsb_strings", []):
        next_actions.append("Run a dedicated steganography review on a forensic copy and keep decoded low-bit strings separate from visible OCR text.")
    if detail_strategy:
        next_actions.append(
            "Apply image reasoning strategy: "
            + detail_strategy
            + (f" — {detail_corroboration_target}" if detail_corroboration_target else "")
        )
    if detail_quality_gate and detail_quality_gate != "ready_for_triage":
        next_actions.append("Resolve image quality gate before final wording: " + detail_quality_gate)
    for action in list(getattr(record, "image_detail_next_actions", []) or [])[:2]:
        next_actions.append(action)
    for step in detail_methodology[:2]:
        next_actions.append("Methodology: " + str(step))
    if not next_actions:
        next_actions.append("Use metadata integrity, source profile, and custody trail as the primary analysis anchors.")

    limitations = list(_VISUAL_LIMITATIONS)
    if not record.ocr_raw_text and not record.visible_text_lines:
        limitations.append("No OCR text was recovered, so content interpretation relies mostly on metadata and visual layout heuristics.")
    if getattr(record, "map_evidence_basis", []) == ["filename"]:
        limitations.append("Location signal appears filename-only and should not be used as a factual place claim.")
    if getattr(record, "pixel_hidden_score", 0):
        limitations.extend(getattr(record, "pixel_hidden_limitations", [])[:2])
    limitations.extend(list(getattr(record, "image_detail_limitations", []) or [])[:2])

    cue_summary = "; ".join(_unique([*reasons, *text_cues[:2], *visual_cues[:3]], limit=6)) or "low-context image"
    place_text = location_hypotheses[0] if location_hypotheses else "no stable location hypothesis"
    summary = (
        f"OSINT Content v2: {label} ({max(0, min(100, confidence))}% confidence). "
        f"Key cues: {cue_summary}. Location: {place_text}"
    )
    return OSINTContentProfile(
        label=label,
        confidence=max(0, min(100, confidence)),
        summary=summary,
        content_tags=_unique(tags, limit=12),
        visual_cues=_unique(visual_cues, limit=8),
        text_cues=_unique(text_cues, limit=8),
        location_hypotheses=location_hypotheses,
        source_context=source_context,
        limitations=_unique(limitations, limit=6),
        next_actions=_unique(next_actions, limit=6),
    )
