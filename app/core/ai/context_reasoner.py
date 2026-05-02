from __future__ import annotations

"""Conservative deep-context reasoning for per-evidence AI findings.

This module does not assert real-world location facts. It only adds review flags
when displayed map/place context could be mistaken for native device evidence, or
when privacy/timeline corroboration is missing.
"""

from typing import Dict, Iterable, Any

from ..models import EvidenceRecord
from .findings import BatchAIFinding


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _valid_text(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in {"", "unknown", "unavailable", "none", "n/a"} else text


def attach_deep_context_reasoning(records: Iterable[EvidenceRecord], findings: Dict[str, BatchAIFinding]) -> None:
    """Attach explainable context flags to existing batch AI findings.

    The rule set is intentionally conservative and mostly adds actions/matrix
    lines. Score deltas are small so this cannot turn weak visual leads into
    strong forensic claims by itself.
    """
    for record in records:
        finding = findings.get(record.evidence_id)
        if finding is None:
            continue

        has_native_gps = bool(getattr(record, "has_gps", False)) or _valid_text(getattr(record, "gps_display", "")) != ""
        gps_conf = int(getattr(record, "gps_confidence", 0) or 0)
        map_conf = int(getattr(record, "map_intelligence_confidence", 0) or getattr(record, "map_confidence", 0) or 0)
        derived_conf = int(getattr(record, "derived_geo_confidence", 0) or 0)
        city = _valid_text(getattr(record, "candidate_city", ""))
        area = _valid_text(getattr(record, "candidate_area", ""))
        place = _valid_text(getattr(record, "possible_place", ""))
        basis = [str(x) for x in _as_list(getattr(record, "map_evidence_basis", [])) if str(x).strip()]
        urls = [str(x) for x in _as_list(getattr(record, "visible_urls", [])) if str(x).strip()]
        route = bool(getattr(record, "route_overlay_detected", False))
        has_displayed_location = bool(map_conf >= 45 or derived_conf >= 35 or city or area or place or urls or route)

        if has_displayed_location and not (has_native_gps and gps_conf >= 70):
            finding.add(
                flag="displayed_location_not_device_proof",
                reason="Displayed map/place context is present, but no high-confidence native GPS proves device location.",
                contributor="Deep Context Reasoner",
                delta=5,
                confidence_delta=1,
                breakdown_detail="separates screenshot/map lead from native device-location evidence",
            )
            finding.add_action("Label displayed map/place context as an investigative lead unless native GPS, source-app history, or independent logs corroborate it.")
            finding.add_matrix_line("Context posture: displayed location lead, not native device proof.")

        time_conf = int(getattr(record, "timestamp_confidence", 0) or getattr(record, "timeline_confidence", 0) or 0)
        imported_at = _valid_text(getattr(record, "imported_at", ""))
        if has_displayed_location and time_conf <= 0 and not imported_at:
            finding.add(
                flag="location_without_time_anchor",
                reason="Location-like context exists without a reliable timestamp anchor.",
                contributor="Deep Context Reasoner",
                delta=4,
                confidence_delta=1,
                breakdown_detail="location context lacks time corroboration",
            )
            finding.add_action("Corroborate the time source before using the location context in a timeline.")
        elif has_displayed_location and time_conf <= 0:
            finding.add_matrix_line("Timeline posture: only import/system timing is available; preserve original source timestamp if possible.")

        if urls or map_conf >= 70:
            finding.add_matrix_line("Privacy posture: map URLs/location text should be redacted or reviewed before public export.")
            finding.add_action("Review privacy redaction for visible URLs, place labels, coordinates, usernames, and route endpoints before sharing reports.")

        if basis:
            finding.add_matrix_line("Location evidence basis: " + " | ".join(basis[:5]))
