from __future__ import annotations

"""Map screenshot OCR zone planner.

The planner does not crop automatically. It gives the UI/export a clear list of
high-value zones so analysts stop running one huge OCR pass over the whole map.
"""

from dataclasses import dataclass, asdict
from typing import Any, Iterable


@dataclass(slots=True)
class MapOCRZone:
    evidence_id: str
    zone: str
    priority: int
    reason: str
    expected_signal: str
    analyst_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _has_map_context(record: Any) -> bool:
    return bool(
        getattr(record, "map_intelligence_confidence", 0)
        or getattr(record, "route_overlay_detected", False)
        or getattr(record, "map_app_detected", "Unknown") not in {"Unknown", ""}
        or getattr(record, "ocr_map_labels", [])
    )


def build_map_ocr_zones(record: Any) -> list[MapOCRZone]:
    evidence_id = str(getattr(record, "evidence_id", "EV"))
    if not _has_map_context(record):
        return []
    zones: list[MapOCRZone] = [
        MapOCRZone(evidence_id, "Top search bar / title bar", 92, "Often contains the searched place, pinned address, or map app context.", "place name, address, plus code, provider UI", "Crop the top 15–25% and run OCR in English + Arabic."),
        MapOCRZone(evidence_id, "Pin/context-menu coordinate bubble", 90, "Right-click/context menus and dropped pins often expose exact lat/lon.", "latitude/longitude pair", "Zoom around pins and menus; look for decimal coordinates."),
        MapOCRZone(evidence_id, "Route card / bottom sheet", 86, "Navigation screenshots hide start/end, ETA, and distance in side/bottom panels.", "origin, destination, ETA, distance", "Crop side panel or bottom 30%; extract start/end separately."),
        MapOCRZone(evidence_id, "Visible street/POI labels", 78, "Street labels and POIs convert a visual map into searchable place leads.", "street names, shops, landmarks", "Run region OCR on dense label clusters; keep low-confidence labels separate."),
        MapOCRZone(evidence_id, "Scale/coordinate/status corners", 72, "Map providers place scale, zoom, compass, and sometimes coordinate hints in corners.", "scale bar, provider UI, compass", "Crop each corner; record provider and map mode."),
    ]
    if getattr(record, "route_overlay_detected", False):
        zones.insert(0, MapOCRZone(evidence_id, "Route polyline and waypoints", 95, "Route overlay is present; the start/end points must not be confused with current map center.", "route endpoints and waypoint labels", "Crop each waypoint and route card; tag as route-derived, not GPS."))
    if getattr(record, "map_type", "").lower().find("satellite") >= 0:
        zones.append(MapOCRZone(evidence_id, "Satellite landmark clusters", 70, "Satellite mode needs landmarks/roads/rivers more than text labels.", "landmark/road/river clues", "Use visual landmark comparison and offline gazetteer hits; keep as lead."))
    return sorted(zones, key=lambda z: (-z.priority, z.zone))[:8]


def build_case_map_ocr_zones(records: Iterable[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for record in records:
        out.extend(zone.to_dict() for zone in build_map_ocr_zones(record))
    return out[:40]
