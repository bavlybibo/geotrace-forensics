from __future__ import annotations

"""Region-aware OCR scoring helpers.

visual_clues.py performs the actual OCR. This module turns per-zone text into a
forensic-safe signal profile so map/search-bar/bottom-sheet text can be weighted
more strongly than generic OCR noise.
"""

from dataclasses import asdict, dataclass, field
from typing import Mapping, Any

from .gazetteer import classify_known_places

REGION_WEIGHTS = {
    "map_search_bar": 92,
    "map_bottom_sheet": 88,
    "top": 74,
    "bottom": 72,
    "left": 66,
    "right": 58,
    "center": 54,
    "full": 42,
}


@dataclass(slots=True)
class OCRRegionSignal:
    region: str
    weight: int
    text_excerpt: str
    place_hits: list[str] = field(default_factory=list)
    basis: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_ocr_regions(region_text: Mapping[str, str]) -> list[OCRRegionSignal]:
    signals: list[OCRRegionSignal] = []
    for region, text in region_text.items():
        clean = " ".join(str(text or "").split())[:280]
        if not clean:
            continue
        places = classify_known_places(clean)
        place_hits = []
        city = str(places.get("city", "Unavailable"))
        area = str(places.get("area", "Unavailable"))
        landmarks = [str(item) for item in places.get("landmarks", []) or []]
        if city != "Unavailable":
            place_hits.append(city)
        if area != "Unavailable":
            place_hits.append(area)
        place_hits.extend(landmarks[:4])
        lower = clean.lower()
        basis = []
        if any(token in lower for token in ("google maps", "directions", "route", "خرائط", "اتجاهات", "المسار")):
            basis.append("map-ui-text")
        if place_hits:
            basis.append("known-place")
        if any(token in lower for token in ("km", "min", "minutes", "دقيقة", "كم")):
            basis.append("route-distance-time")
        if not basis:
            basis.append("ocr-region-text")
        signals.append(
            OCRRegionSignal(
                region=region,
                weight=REGION_WEIGHTS.get(region, 40),
                text_excerpt=clean,
                place_hits=place_hits,
                basis=basis,
            )
        )
    signals.sort(key=lambda item: (-item.weight, -len(item.place_hits), item.region))
    return signals[:10]
