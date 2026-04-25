from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Mapping
import re

from .osint.map_url_parser import parse_map_url_signals
from .osint.gazetteer import (
    AREA_ALIASES as GAZETTEER_AREA_ALIASES,
    CITY_ALIASES as GAZETTEER_CITY_ALIASES,
    LANDMARK_ALIASES as GAZETTEER_LANDMARK_ALIASES,
)
from .osint.place_ranking import rank_places_as_labels
from .vision import score_visual_map_and_route, summarize_visual_map_signals
from .map import location_strength_label

ARABIC_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]")

CITY_ALIASES: dict[str, tuple[str, ...]] = {
    "Cairo": ("cairo", "القاهرة", "القاهره", "new cairo", "مصر الجديدة", "مدينة نصر", "nasr city", "heliopolis"),
    "Giza": ("giza", "الجيزة", "جيزة", "dokki", "الدقي", "mohandessin", "المهندسين", "haram", "الهرم"),
    "Alexandria": ("alexandria", "الإسكندرية", "الاسكندرية"),
}

AREA_ALIASES: dict[str, tuple[str, ...]] = {
    "Zamalek": ("zamalek", "الزمالك"),
    "Garden City": ("garden city", "جاردن سيتي", "جاردن سيتى"),
    "Heliopolis": ("heliopolis", "مصر الجديدة"),
    "Nasr City": ("nasr city", "مدينة نصر"),
    "Dokki": ("dokki", "الدقي"),
    "Mohandessin": ("mohandessin", "المهندسين"),
    "Maadi": ("maadi", "المعادي"),
    "Tahrir": ("tahrir", "التحرير"),
    "Nile Corniche": ("nile", "corniche", "النيل", "كورنيش"),
}

LANDMARK_ALIASES: dict[str, tuple[str, ...]] = {
    "Fairmont Nile City": ("fairmont nile city", "فيرمونت نايل", "فيرمونت النيل"),
    "Cairo by Royal Tulip": ("cairo by royal tulip", "royal tulip"),
    "Cairo Tower": ("cairo tower", "برج القاهرة", "برج القاهره"),
    "Egyptian Museum": ("egyptian museum", "المتحف المصري", "المتحف المصرى"),
    "Cairo Stadium": ("cairo stadium", "استاد القاهرة", "ستاد القاهرة"),
    "Nile River": ("nile", "النيل"),
    "Google Maps": ("google maps", "خرائط google", "خرائط جوجل", "google خرائط"),
}

GOOGLE_MAPS_TOKENS = (
    "google maps", "google.com/maps", "maps.google", "خرائط", "خريطة", "خريطه",
    "directions", "اتجاهات", "route", "المسار", "nearby", "satellite",
)

ROUTE_TOKENS = ("route", "directions", "اتجاهات", "المسار", "كم", "دقيقة", "min", "minutes")

# Keep backwards compatibility with the legacy constants while extending them from the
# dedicated offline gazetteer module.
CITY_ALIASES.update(GAZETTEER_CITY_ALIASES)
AREA_ALIASES.update(GAZETTEER_AREA_ALIASES)
LANDMARK_ALIASES.update(GAZETTEER_LANDMARK_ALIASES)


@dataclass(slots=True)
class MapIntelligence:
    detected: bool = False
    app_detected: str = "Unknown"
    map_type: str = "Unknown"
    route_overlay_detected: bool = False
    route_confidence: int = 0
    candidate_city: str = "Unavailable"
    candidate_area: str = "Unavailable"
    landmarks_detected: list[str] = field(default_factory=list)
    place_candidates: list[str] = field(default_factory=list)
    confidence: int = 0
    ocr_language_hint: str = "Unknown"
    summary: str = "No map intelligence generated yet."
    reasons: list[str] = field(default_factory=list)
    evidence_basis: list[str] = field(default_factory=list)
    evidence_strength: str = "weak_signal"
    limitations: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    place_candidate_rankings: list[str] = field(default_factory=list)
    filename_location_hints: list[str] = field(default_factory=list)
    evidence_ladder: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _contains_arabic(text: str) -> bool:
    return bool(ARABIC_RE.search(text or ""))


def _normalize(text: str) -> str:
    text = str(text or "").replace("\u200f", " ").replace("\u200e", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _unique(items: Iterable[str], limit: int = 10) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        clean = _normalize(item).strip(" -:|•·")
        if not clean or clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
        if len(out) >= limit:
            break
    return out


def _good_place_candidate(value: str) -> bool:
    text = _normalize(value).strip(" -:|•·")
    if len(text) < 4 or text.lower() in {"unknown", "unavailable", "none", "n/a"}:
        return False
    letters = sum(ch.isalpha() for ch in text)
    digits = sum(ch.isdigit() for ch in text)
    arabic = _contains_arabic(text)
    if letters == 0 and not arabic:
        return False
    if digits and digits > max(2, letters * 2) and not arabic:
        return False
    # Reject date/id-like OCR noise.
    if re.fullmatch(r"(?:img|image|screenshot|screen|capture)?\s*\d+[\s:/.-]*\d*", text, re.I):
        return False
    if re.search(r"\b20\d{2}\b", text) and letters <= 4 and not arabic:
        return False
    return True


def _first_match(text: str, aliases: Mapping[str, tuple[str, ...]]) -> str:
    lower = text.lower()
    for canonical, tokens in aliases.items():
        for token in tokens:
            if token.lower() in lower:
                return canonical
    return "Unavailable"


def _all_matches(text: str, aliases: Mapping[str, tuple[str, ...]], limit: int = 8) -> list[str]:
    lower = text.lower()
    out: list[str] = []
    for canonical, tokens in aliases.items():
        if any(token.lower() in lower for token in tokens):
            out.append(canonical)
    return _unique(out, limit=limit)

def _rank_place_candidates(
    candidates: Iterable[str],
    *,
    candidate_city: str,
    candidate_area: str,
    landmarks: list[str],
    basis: list[str],
) -> list[str]:
    ranked: list[tuple[int, str, str]] = []
    basis_bonus = 12 if any(item in basis for item in ("ocr/text", "url", "known-place-dictionary")) else 0
    for place in _unique(candidates, limit=12):
        score = 42 + basis_bonus
        reasons: list[str] = []
        if place == candidate_city and candidate_city != "Unavailable":
            score += 18
            reasons.append("city")
        if place == candidate_area and candidate_area != "Unavailable":
            score += 22
            reasons.append("area")
        if place in landmarks:
            score += 26
            reasons.append("landmark")
        if any(item in basis for item in ("visual-map-colors", "route-visual")):
            score += 8
            reasons.append("visual")
        if "filename" in basis and len(basis) == 1:
            score = min(score, 52)
            reasons.append("filename-only")
        ranked.append((min(96, score), place, "+".join(reasons) or "context"))
    ranked.sort(key=lambda item: (-item[0], item[1].lower()))
    return [f"{place} — {score}% — {reason}" for score, place, reason in ranked[:8]]


def _visual_map_and_route_score(file_path: Path) -> tuple[int, int, list[str]]:
    # Backwards-compatible wrapper; implementation moved to app.core.vision.map_visuals.
    return score_visual_map_and_route(file_path)


def _build_map_evidence_ladder(
    *,
    map_url_signals: list[object],
    candidate_city: str,
    candidate_area: str,
    place_candidates: list[str],
    landmarks: list[str],
    labels: list[str],
    locations: list[str],
    visual_detected: bool,
    route_overlay: bool,
    filename_location_hints: list[str],
) -> list[str]:
    has_coords = any(getattr(signal, "coordinates", None) for signal in map_url_signals)
    has_map_url = bool(map_url_signals)
    has_ocr_labels = bool(labels or locations or place_candidates or candidate_city != "Unavailable" or candidate_area != "Unavailable" or landmarks)
    return [
        "Native GPS: not evaluated in map module; handled by forensic metadata layer",
        f"Visible coordinates/map URL: {'present' if has_coords else 'missing'}" + (" (map URL/provider seen)" if has_map_url and not has_coords else ""),
        f"OCR labels/place text: {'present' if has_ocr_labels else 'missing'}",
        f"Known city/area/landmark: {'present' if candidate_city != 'Unavailable' or candidate_area != 'Unavailable' or landmarks else 'missing'}",
        f"Visual map context: {'present' if visual_detected else 'missing'}" + ("; route overlay present" if route_overlay else ""),
        f"Filename-only hints: {', '.join(filename_location_hints) if filename_location_hints else 'none'}",
        "Final posture: weak visual context only unless coordinates, map URL, OCR labels, or source-app history corroborate it."
        if visual_detected and not has_coords and not has_ocr_labels
        else "Final posture: keep displayed map context separate from real device location until corroborated.",
    ]


def analyze_map_intelligence(file_path: Path, visible: Mapping[str, object]) -> MapIntelligence:
    lines = [str(x) for x in visible.get("lines", []) or []]
    labels = [str(x) for x in visible.get("ocr_map_labels", []) or []]
    locations = [str(x) for x in visible.get("visible_location_strings", []) or []]
    urls = [str(x) for x in visible.get("visible_urls", []) or []]
    app_names = [str(x) for x in visible.get("app_names", []) or []]
    raw_text = str(visible.get("raw_text", "") or "")
    excerpt = str(visible.get("excerpt", "") or "")

    map_url_signals = parse_map_url_signals([raw_text, excerpt, *lines, *labels, *locations, *urls, file_path.name], source="map-intelligence")

    content_text = _normalize("\n".join([raw_text, excerpt, *lines, *labels, *locations, *urls]))
    filename_text = _normalize(file_path.name)
    text = _normalize("\n".join([content_text, filename_text]))
    lower_content = content_text.lower()
    lower_filename = filename_text.lower()

    visual_map_score, visual_route_score, visual_reasons = _visual_map_and_route_score(file_path)
    textual_google = any(token in lower_content for token in GOOGLE_MAPS_TOKENS) or any(app == "Google Maps" for app in app_names)
    filename_map_signal = any(token in lower_filename for token in ("map", "maps", "route", "directions", "geo", "location"))
    route_text = any(token in lower_content for token in ROUTE_TOKENS)
    filename_route_text = any(token in lower_filename for token in ("route", "directions"))
    has_map_label = any(_good_place_candidate(x) for x in [*labels, *locations])

    route_overlay = visual_route_score >= 52 or route_text
    route_confidence = max(visual_route_score, 72 if route_text else 0, 40 if filename_route_text else 0)
    map_url_detected = bool(map_url_signals)
    detected = textual_google or visual_map_score >= 42 or has_map_label or route_overlay or filename_map_signal or map_url_detected
    first_map_provider = map_url_signals[0].provider if map_url_signals else ""
    app_detected = "Google Maps" if textual_google else (first_map_provider if map_url_detected else ("Google Maps-like UI" if route_overlay or visual_map_score >= 42 else "Map Application" if detected else "Unknown"))
    map_type = "Road / navigation map" if route_overlay else "Road map" if detected else "Unknown"

    candidate_city_content = _first_match(content_text, CITY_ALIASES)
    candidate_city_filename = _first_match(filename_text, CITY_ALIASES)
    # Keep filename-only location hints separate from real visible/OCR/map evidence.
    # This prevents a file called cairo_scene.jpg from becoming a strong city claim.
    candidate_city = candidate_city_content

    candidate_area_content = _first_match(content_text, AREA_ALIASES)
    candidate_area_filename = _first_match(filename_text, AREA_ALIASES)
    candidate_area = candidate_area_content

    content_landmarks = _all_matches(content_text, LANDMARK_ALIASES, limit=8)
    filename_landmarks = _all_matches(filename_text, LANDMARK_ALIASES, limit=4)
    landmarks = _unique(content_landmarks, limit=8)
    filename_location_hints = _unique(
        [
            candidate_city_filename if candidate_city_filename != "Unavailable" else "",
            candidate_area_filename if candidate_area_filename != "Unavailable" else "",
            *filename_landmarks,
        ],
        limit=6,
    )
    url_places = [signal.place_name for signal in map_url_signals if signal.place_name != "Unavailable"]
    raw_places = _unique([*labels, *locations, *url_places, *landmarks, candidate_area, candidate_city], limit=12)
    place_candidates = [item for item in raw_places if _good_place_candidate(item) and item != "Unavailable"]

    basis: list[str] = []
    if visual_map_score >= 30:
        basis.append("visual-map-colors")
    if visual_route_score >= 30:
        basis.append("route-visual")
    if textual_google or raw_text or lines or labels or locations:
        basis.append("ocr/text")
    if urls:
        basis.append("url")
    if map_url_signals:
        basis.append("map-url")
    if route_text:
        basis.append("route-text")
    if candidate_city_content != "Unavailable" or candidate_area_content != "Unavailable" or landmarks:
        basis.append("known-place-dictionary")
    if filename_map_signal or filename_location_hints:
        basis.append("filename")
    if any(isinstance(item, dict) and item.get("place_hits") for item in visible.get("ocr_region_signals", []) or []):
        basis.append("region-aware-ocr")
    basis = _unique(basis, limit=8)

    confidence = 0
    reasons: list[str] = []
    if detected:
        # Keep a conservative floor only when the signal is not filename-only.
        if basis and basis != ["filename"]:
            confidence = max(confidence, visual_map_score, 55)
        else:
            confidence = max(confidence, 38)
        reasons.extend(visual_reasons)
    if textual_google:
        confidence = max(confidence, 86)
        reasons.append("Google Maps UI/text signal detected")
    if map_url_signals:
        confidence = max(confidence, max(signal.confidence for signal in map_url_signals[:3]))
        reasons.append("map URL/coordinate signal parsed from visible text")
    if route_overlay:
        confidence = max(confidence, min(92, route_confidence + 8))
        reasons.append("route/navigation overlay detected")
    if candidate_city != "Unavailable":
        confidence = max(confidence, 78)
        reasons.append(f"candidate city recovered from visible/OCR context: {candidate_city}")
    elif candidate_city_filename != "Unavailable":
        confidence = max(confidence, 44)
        reasons.append(f"filename-only city hint retained separately: {candidate_city_filename}")
    if candidate_area != "Unavailable":
        confidence = max(confidence, 80)
        reasons.append(f"candidate area recovered from visible/OCR context: {candidate_area}")
    elif candidate_area_filename != "Unavailable":
        confidence = max(confidence, 46)
        reasons.append(f"filename-only area hint retained separately: {candidate_area_filename}")
    if landmarks:
        confidence = max(confidence, 82)
        reasons.append("recognizable landmark/place labels recovered from visible/OCR context")
    elif filename_landmarks:
        confidence = max(confidence, 48)
        reasons.append("filename-only landmark hint retained separately")
    strong_regions = [item for item in visible.get("ocr_region_signals", []) or [] if isinstance(item, dict) and item.get("place_hits") and int(item.get("weight", 0) or 0) >= 70]
    if strong_regions:
        confidence = max(confidence, 84)
        reasons.append("region-aware OCR found place text in a high-value map/screenshot zone")

    if basis == ["filename"]:
        confidence = min(confidence, 52)
        reasons.append("confidence capped because the map clue is filename-only")
    if any(item in basis for item in ("visual-map-colors", "route-visual", "filename")):
        reasons.append(summarize_visual_map_signals(basis, confidence=confidence))

    ocr_language = "Arabic + English" if _contains_arabic(text) and re.search(r"[A-Za-z]", text) else "Arabic" if _contains_arabic(text) else "English/Latin" if re.search(r"[A-Za-z]", text) else "Unknown"
    route_text_value = "Route overlay detected" if route_overlay else "No clear route overlay"
    city_text = candidate_city if candidate_city != "Unavailable" else "no stable city"
    place_text = ", ".join(place_candidates[:3]) if place_candidates else "no stable place label"
    region_signals = list(visible.get("ocr_region_signals", []) or [])
    region_texts = [str(item.get("text_excerpt", "")) for item in region_signals if isinstance(item, dict)]
    region_place_hits = [str(hit) for item in region_signals if isinstance(item, dict) for hit in (item.get("place_hits", []) or [])]
    rankings = rank_places_as_labels(
        texts=[content_text, *region_texts],
        explicit_candidates=[*place_candidates, *region_place_hits],
        candidate_city=candidate_city,
        candidate_area=candidate_area,
        landmarks=landmarks,
        basis=basis,
        map_url_signals=map_url_signals,
        has_native_gps=False,
        derived_geo_confidence=max(signal.confidence for signal in map_url_signals) if map_url_signals else 0,
        ocr_confidence=int(visible.get("ocr_confidence", 0) or 0),
    )

    limitations: list[str] = []
    recommended_actions: list[str] = []
    if basis == ["filename"] or filename_location_hints and not any(b in basis for b in ("ocr/text", "url", "map-url", "known-place-dictionary", "region-aware-ocr")):
        limitations.append("Location/map inference is filename-only; treat as weak signal.")
    elif filename_location_hints:
        limitations.append("Filename location hints are retained separately and do not outrank OCR/GPS/map evidence.")
    if detected and not (textual_google or labels or locations or urls or map_url_signals):
        limitations.append("Visual map pattern was detected without stable OCR text or source URL.")
    if map_url_signals and not any(signal.coordinates for signal in map_url_signals):
        limitations.append("Map URL/provider context was detected, but no stable coordinate pair was recovered from it.")
    if place_candidates and not (candidate_city_content != "Unavailable" or candidate_area_content != "Unavailable" or landmarks):
        limitations.append("Place candidates require manual confirmation because they were not matched to a known-place dictionary.")
    if route_overlay:
        recommended_actions.append("Confirm route start/end assumptions using source-app history or a share URL before using this as movement evidence.")
    if map_url_signals:
        recommended_actions.append("Preserve the original visible map URL/text and verify it manually before treating it as a location fact.")
    if place_candidates or candidate_city != "Unavailable" or candidate_area != "Unavailable":
        recommended_actions.append("Corroborate visible place labels with manual map review, source URLs, or native device/app logs.")
    if detected and not recommended_actions:
        recommended_actions.append("Preserve the original screenshot and rerun Deep OCR if location context is important.")
    evidence_strength = location_strength_label(
        has_native_gps=False,
        derived_geo_confidence=max(signal.confidence for signal in map_url_signals) if map_url_signals else 0,
        map_confidence=confidence,
        has_map_url=bool(map_url_signals),
        has_place_dictionary_hit=bool(candidate_city_content != "Unavailable" or candidate_area_content != "Unavailable" or landmarks),
        basis=basis,
    )

    evidence_ladder = _build_map_evidence_ladder(
        map_url_signals=map_url_signals,
        candidate_city=candidate_city,
        candidate_area=candidate_area,
        place_candidates=place_candidates,
        landmarks=landmarks,
        labels=labels,
        locations=locations,
        visual_detected=bool(detected),
        route_overlay=bool(route_overlay),
        filename_location_hints=filename_location_hints,
    )

    if detected:
        summary = (
            f"Map intelligence v3: {app_detected}; {map_type}; {route_text_value}. "
            f"Candidate city: {city_text}. Candidate place/area: {place_text}. "
            f"Evidence strength: {evidence_strength}. Evidence basis: {', '.join(basis) if basis else 'none'}."
        )
    else:
        summary = "No strong map/navigation context was detected from the current evidence item."

    return MapIntelligence(
        detected=bool(detected),
        app_detected=app_detected,
        map_type=map_type,
        route_overlay_detected=bool(route_overlay),
        route_confidence=max(0, min(100, route_confidence)),
        candidate_city=candidate_city,
        candidate_area=candidate_area,
        landmarks_detected=landmarks,
        place_candidates=place_candidates,
        confidence=max(0, min(100, confidence)),
        ocr_language_hint=ocr_language,
        summary=summary,
        reasons=_unique(reasons, limit=8),
        evidence_basis=basis,
        evidence_strength=evidence_strength,
        limitations=_unique(limitations, limit=6),
        recommended_actions=_unique(recommended_actions, limit=6),
        place_candidate_rankings=rankings,
        filename_location_hints=filename_location_hints,
        evidence_ladder=evidence_ladder,
    )

