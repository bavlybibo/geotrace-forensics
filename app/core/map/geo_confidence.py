from __future__ import annotations

"""Explainable geo confidence ladder.

This module keeps the forensic wording strict:
- Native GPS means EXIF/device metadata only.
- Derived Geo Anchor means map URL/OCR/visible coordinate/offline geocoder.
- Map Search Lead means place text without a coordinate.
"""

from dataclasses import dataclass, asdict, field
from typing import Any, Iterable

from .evidence import anchor_kind_from_source, claim_policy_for_anchor


@dataclass(slots=True)
class GeoConfidenceLadder:
    evidence_id: str
    primary_classification: str
    final_score: int
    final_posture: str
    lines: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _valid_float_pair(lat: Any, lon: Any) -> bool:
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except Exception:
        return False
    return -90 <= lat_f <= 90 and -180 <= lon_f <= 180


def _yes(value: bool) -> str:
    return "PASS" if value else "FAIL"


def _clean(value: Any, default: str = "Unavailable") -> str:
    text = " ".join(str(value or "").split()).strip()
    return text if text and text.lower() not in {"none", "unknown", "unavailable", "n/a"} else default


def build_geo_confidence_ladder(record: Any) -> GeoConfidenceLadder:
    evidence_id = _clean(getattr(record, "evidence_id", "EV"), "EV")
    has_native_gps = bool(getattr(record, "has_gps", False)) and _valid_float_pair(
        getattr(record, "gps_latitude", None), getattr(record, "gps_longitude", None)
    )
    has_derived_coord = _valid_float_pair(getattr(record, "derived_latitude", None), getattr(record, "derived_longitude", None))
    bridge = getattr(record, "map_provider_bridge", {}) or {}
    has_bridge_coord = False
    if isinstance(bridge, dict):
        has_bridge_coord = _valid_float_pair(bridge.get("latitude"), bridge.get("longitude"))
    payload = getattr(record, "map_interactive_payload", {}) or {}
    has_payload_coord = isinstance(payload, dict) and payload.get("available") and _valid_float_pair(payload.get("latitude"), payload.get("longitude"))
    has_visible_coordinate = has_derived_coord or has_bridge_coord or has_payload_coord
    has_map_url_or_provider = bool(getattr(record, "map_provider_links", []) or getattr(record, "map_provider_queries", []))
    has_ocr_place = bool(
        getattr(record, "place_candidates", [])
        or getattr(record, "landmarks_detected", [])
        or _clean(getattr(record, "candidate_city", ""), "")
        or _clean(getattr(record, "candidate_area", ""), "")
    )
    visual_map = bool(getattr(record, "map_intelligence_confidence", 0) or getattr(record, "route_overlay_detected", False))
    local_vision = None
    try:
        metrics = getattr(record, "image_detail_metrics", {}) or {}
        if isinstance(metrics, dict):
            local_vision = metrics.get("local_vision") if isinstance(metrics.get("local_vision"), dict) else None
    except Exception:
        local_vision = None
    local_vision_executed = bool(local_vision and local_vision.get("executed"))

    score = 0
    if has_native_gps:
        score = max(score, int(getattr(record, "gps_confidence", 0) or 94))
    if has_visible_coordinate:
        score = max(score, int(getattr(record, "derived_geo_confidence", 0) or getattr(record, "map_answer_readiness_score", 0) or 82))
    if has_map_url_or_provider:
        score = max(score, 74)
    if has_ocr_place:
        score = max(score, min(78, max(52, int(getattr(record, "map_intelligence_confidence", 0) or 0))))
    if visual_map:
        score = max(score, min(48, max(28, int(getattr(record, "map_intelligence_confidence", 0) or 0))))
    if local_vision_executed and visual_map:
        score = min(92, score + 5)

    if has_native_gps:
        classification = "Native GPS"
        posture = "Metadata location anchor. Still verify timeline/custody before final reporting."
    elif has_visible_coordinate:
        classification = "Derived Geo Anchor"
        posture = "Coordinate lead from OCR/map URL/visible content. Not native device GPS."
    elif has_ocr_place:
        classification = "Map Search Lead"
        posture = "Place/landmark text lead only. Needs provider/source-app confirmation."
    elif visual_map:
        classification = "Map Screenshot Mode"
        posture = "Visual map context only. Extract labels/coordinates before claiming a place."
    else:
        classification = "No Geo Anchor"
        posture = "No reliable location anchor recovered yet."

    anchor_source_for_policy = getattr(record, "gps_source", "") if has_native_gps else getattr(record, "derived_geo_source", "") or (bridge.get("anchor_source") if isinstance(bridge, dict) else "") or getattr(record, "map_anchor_status", "")
    anchor_kind = anchor_kind_from_source(anchor_source_for_policy, has_native_gps=has_native_gps, has_coordinates=has_visible_coordinate)
    policy = claim_policy_for_anchor(anchor_kind, confidence=score, source=anchor_source_for_policy)

    lines = [
        f"1. Native EXIF GPS — {_yes(has_native_gps)}" + (f" ({getattr(record, 'gps_display', 'Unavailable')}, {getattr(record, 'gps_confidence', 0)}%)." if has_native_gps else " (do not label derived coordinates as GPS)."),
        f"2. Derived coordinate — {_yes(has_visible_coordinate)}" + (f" ({_clean(getattr(record, 'derived_geo_display', ''), _clean(bridge.get('anchor_label') if isinstance(bridge, dict) else '', 'coordinate anchor'))})." if has_visible_coordinate else " (no OCR/map URL/visible coordinate confirmed)."),
        f"3. Map provider bridge — {_yes(has_map_url_or_provider)}" + (f" ({len(getattr(record, 'map_provider_links', []) or [])} privacy-gated link(s))." if has_map_url_or_provider else " (no external verification link generated)."),
        f"4. OCR place/landmark text — {_yes(has_ocr_place)}" + (f" ({', '.join(list(getattr(record, 'place_candidates', []) or getattr(record, 'landmarks_detected', []) or [])[:3]) or _clean(getattr(record, 'candidate_city', ''), 'place text')})." if has_ocr_place else " (run map OCR zones)."),
        f"5. Visual map screenshot mode — {_yes(visual_map)}" + (f" ({getattr(record, 'map_type', 'Map context')}, {getattr(record, 'map_intelligence_confidence', 0)}%)." if visual_map else " (no clear map UI pattern)."),
        f"6. Local vision corroboration — {_yes(local_vision_executed)}" + (f" ({_clean(local_vision.get('provider'), 'local model')})." if local_vision_executed else " (optional offline model not executed)."),
        f"7. Reporting policy — {policy.claim_label} / {policy.proof_level}; radius ~{policy.radius_m}m.",
        f"8. Verification rule — {policy.verification_rule}",
    ]

    blockers: list[str] = []
    actions: list[str] = []
    if not has_native_gps:
        blockers.append("No native EXIF GPS. Any coordinate found here is a derived lead, not device GPS proof.")
    if visual_map and not has_visible_coordinate:
        blockers.append("Map screenshot detected, but no stable coordinate pair was recovered.")
    if has_ocr_place and not (has_visible_coordinate or has_map_url_or_provider):
        blockers.append("Place text exists without a coordinate/source URL; manual provider verification is required.")
    if not has_visible_coordinate and not has_ocr_place:
        actions.append("Run Map Screenshot Mode OCR zones: search bar, route card, pin/context menu, visible street labels, and scale/coordinate corner.")
    if policy.proof_level.startswith("approximate") or policy.anchor_kind in {"place_search", "visual_context"}:
        actions.append("Keep this as a search lead; do not plot/report it as an exact coordinate until independently confirmed.")
    if has_visible_coordinate:
        actions.append("Open provider links only after privacy approval and compare the point against the original screenshot/source URL.")
    actions.append("Keep Native GPS, Derived Geo Anchor, and Map Search Lead separated in the report.")

    return GeoConfidenceLadder(
        evidence_id=evidence_id,
        primary_classification=classification,
        final_score=max(0, min(100, int(score))),
        final_posture=posture,
        lines=lines,
        blockers=blockers,
        next_actions=actions,
    )


def build_case_geo_ladders(records: Iterable[Any]) -> list[dict[str, Any]]:
    return [build_geo_confidence_ladder(record).to_dict() for record in records]
