from __future__ import annotations

"""Conservative offline place ranking for OSINT/location leads.

The ranker does not resolve places online. It scores only signals already present in
an acquired evidence item: OCR text, filenames, parsed map URLs, known-place aliases,
native GPS presence, and visual map/route indicators.
"""

from dataclasses import asdict, dataclass, field
from typing import Iterable, Mapping, Any

from .gazetteer import AREA_ALIASES, CITY_ALIASES, LANDMARK_ALIASES, all_matches, first_match, normalize_text, unique


@dataclass(slots=True)
class PlaceRank:
    place: str
    score: int
    category: str = "unknown"
    evidence_basis: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_label(self) -> str:
        basis = "+".join(self.evidence_basis[:4]) or "context"
        return f"{self.place} — {self.score}% — {self.category}:{basis}"


def _add_candidate(store: dict[str, PlaceRank], place: str, *, score: int, category: str, basis: str, limitation: str | None = None) -> None:
    clean = str(place or "").strip(" -:|•·")
    if not clean or clean.lower() in {"unknown", "unavailable", "n/a", "none"}:
        return
    key = normalize_text(clean).lower()
    current = store.get(key)
    if current is None:
        current = PlaceRank(place=clean, score=0, category=category)
        store[key] = current
    current.score = max(current.score, max(0, min(100, score)))
    if category != "unknown" and current.category == "unknown":
        current.category = category
    if basis and basis not in current.evidence_basis:
        current.evidence_basis.append(basis)
    if limitation and limitation not in current.limitations:
        current.limitations.append(limitation)


def rank_places(
    *,
    texts: Iterable[str] = (),
    explicit_candidates: Iterable[str] = (),
    candidate_city: str = "Unavailable",
    candidate_area: str = "Unavailable",
    landmarks: Iterable[str] = (),
    basis: Iterable[str] = (),
    map_url_signals: Iterable[Any] = (),
    has_native_gps: bool = False,
    derived_geo_confidence: int = 0,
    ocr_confidence: int = 0,
    limit: int = 8,
) -> list[PlaceRank]:
    basis_set = {str(item) for item in basis if str(item or "").strip()}
    text_blob = "\n".join(str(item or "") for item in texts)
    store: dict[str, PlaceRank] = {}

    city_hits = all_matches(text_blob, CITY_ALIASES, limit=8)
    area_hits = all_matches(text_blob, AREA_ALIASES, limit=8)
    landmark_hits = all_matches(text_blob, LANDMARK_ALIASES, limit=10)

    if candidate_city != "Unavailable":
        city_hits = unique([candidate_city, *city_hits], limit=10)
    if candidate_area != "Unavailable":
        area_hits = unique([candidate_area, *area_hits], limit=10)
    landmark_hits = unique([*landmarks, *landmark_hits], limit=12)

    text_bonus = 10 if "ocr/text" in basis_set else 0
    url_bonus = 16 if {"url", "map-url"}.intersection(basis_set) else 0
    visual_bonus = 7 if {"visual-map-colors", "route-visual"}.intersection(basis_set) else 0
    gps_bonus = 10 if has_native_gps else 0
    ocr_bonus = min(10, max(0, int(ocr_confidence or 0) // 10))

    for city in city_hits:
        _add_candidate(store, city, score=52 + text_bonus + url_bonus + visual_bonus + gps_bonus + ocr_bonus, category="city", basis="known-city")
    for area in area_hits:
        _add_candidate(store, area, score=58 + text_bonus + url_bonus + visual_bonus + gps_bonus + ocr_bonus, category="area", basis="known-area")
    for landmark in landmark_hits:
        _add_candidate(store, landmark, score=66 + text_bonus + url_bonus + visual_bonus + gps_bonus + ocr_bonus, category="landmark", basis="known-landmark")

    for raw in explicit_candidates:
        place = str(raw or "").strip()
        if not place or place == "Unavailable":
            continue
        category = "candidate"
        if first_match(place, LANDMARK_ALIASES) != "Unavailable":
            category = "landmark"
        elif first_match(place, AREA_ALIASES) != "Unavailable":
            category = "area"
        elif first_match(place, CITY_ALIASES) != "Unavailable":
            category = "city"
        score = 44 + text_bonus + visual_bonus + ocr_bonus
        if category == "landmark":
            score += 18
        elif category == "area":
            score += 12
        elif category == "city":
            score += 8
        limitation = None
        if basis_set == {"filename"}:
            score = min(score, 52)
            limitation = "filename-only"
        _add_candidate(store, place, score=score, category=category, basis="explicit-candidate", limitation=limitation)

    for signal in map_url_signals:
        place_name = getattr(signal, "place_name", "Unavailable")
        coords = getattr(signal, "coordinates", None)
        provider = getattr(signal, "provider", "Map signal")
        if place_name and place_name != "Unavailable":
            _add_candidate(store, str(place_name), score=82, category="map-url-place", basis=str(provider), limitation="displayed-location-not-device-proof")
        if coords:
            lat, lon = coords
            label = f"{float(lat):.6f}, {float(lon):.6f}"
            coord_score = max(82, min(94, 72 + int(derived_geo_confidence or 0) // 4 + url_bonus))
            _add_candidate(store, label, score=coord_score, category="coordinate", basis=str(provider), limitation="coordinate-is-visible-context-unless-native-gps")

    ranked = sorted(store.values(), key=lambda item: (-item.score, item.category, item.place.lower()))
    for item in ranked:
        if has_native_gps and item.category == "coordinate":
            item.evidence_basis.append("native-gps-present")
        # Keep courtroom language conservative.
        if item.category != "coordinate" and "native-gps-present" not in item.evidence_basis:
            if "displayed-place-not-device-location" not in item.limitations:
                item.limitations.append("displayed-place-not-device-location")
    return ranked[:limit]


def rank_places_as_labels(**kwargs: Any) -> list[str]:
    return [item.to_label() for item in rank_places(**kwargs)]
