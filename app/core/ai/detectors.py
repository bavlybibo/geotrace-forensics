from __future__ import annotations

"""Deterministic cross-evidence detectors used by the AI engine."""

from statistics import median
from typing import Dict, List

from ..models import EvidenceRecord
from .features import editing_tool_detected, geo_points, haversine_km, has_hidden_content_signal, record_coordinates, timeline_points
from .findings import BatchAIFinding

import os

IsolationForest = None  # type: ignore
if os.environ.get("GEOTRACE_ENABLE_SKLEARN_AI") == "1":  # optional heavy backend
    try:
        from sklearn.ensemble import IsolationForest  # type: ignore
    except Exception:  # pragma: no cover - exercised when sklearn is absent
        IsolationForest = None  # type: ignore


def _get_finding(findings: Dict[str, BatchAIFinding], record: EvidenceRecord) -> BatchAIFinding:
    return findings.setdefault(record.evidence_id, BatchAIFinding())


def detect_location_outliers(records: List[EvidenceRecord], findings: Dict[str, BatchAIFinding]) -> None:
    points = geo_points(records)
    if len(points) < 3:
        return

    ml_outliers: set[str] = set()
    if IsolationForest is not None and len(points) >= 4:
        try:
            contamination = min(0.35, max(0.10, 1 / len(points)))
            model = IsolationForest(n_estimators=100, contamination=contamination, random_state=42)
            predictions = model.fit_predict([[point.latitude, point.longitude] for point in points])
            for point, prediction in zip(points, predictions):
                if prediction == -1:
                    ml_outliers.add(point.record.evidence_id)
        except Exception:
            ml_outliers = set()

    center_lat = median([point.latitude for point in points])
    center_lon = median([point.longitude for point in points])
    distances = [haversine_km(point.latitude, point.longitude, center_lat, center_lon) for point in points]
    median_distance = median(distances) if distances else 0.0
    threshold = max(35.0, median_distance * 3.5 + 15.0)

    for point, distance_km in zip(points, distances):
        is_heuristic_outlier = distance_km >= threshold and distance_km >= 45.0
        is_ml_outlier = point.record.evidence_id in ml_outliers and distance_km >= max(20.0, median_distance * 2.2)
        if not (is_heuristic_outlier or is_ml_outlier):
            continue
        delta = 18 if point.source == "native GPS" else 12
        finding = _get_finding(findings, point.record)
        finding.add(
            flag="geo_outlier",
            reason=(
                f"This item is a geographic outlier against the case cluster: about {distance_km:.1f} km "
                f"from the median case location using {point.source}."
            ),
            contributor="AI location outlier",
            delta=delta,
            confidence_delta=4 if point.confidence >= 60 else 2,
            breakdown_detail=f"geographic outlier ({distance_km:.1f} km from case median)",
        )
        finding.add_action("Confirm whether this location is expected for the case before including it in the main narrative.")


def detect_impossible_travel(records: List[EvidenceRecord], findings: Dict[str, BatchAIFinding]) -> None:
    points = timeline_points(records)
    if len(points) < 2:
        return

    for previous, current in zip(points, points[1:]):
        hours = (current.timestamp - previous.timestamp).total_seconds() / 3600
        distance_km = haversine_km(previous.latitude, previous.longitude, current.latitude, current.longitude)
        if distance_km < 25:
            continue
        speed = float("inf") if hours <= 0 else distance_km / hours

        delta = 0
        flag = ""
        label = ""
        if hours <= 0 and distance_km >= 25:
            delta = 20
            flag = "time_geo_conflict"
            label = "non-increasing timestamp with different locations"
        elif speed >= 900 and distance_km >= 50:
            delta = 22
            flag = "impossible_travel"
            label = f"impossible travel speed ({speed:.0f} km/h)"
        elif speed >= 220 and distance_km >= 40 and hours <= 6:
            delta = 12
            flag = "rapid_travel"
            label = f"rapid movement requiring {speed:.0f} km/h"
        if not delta:
            continue

        source_note = f"{previous.source} → {current.source}"
        reason = (
            f"Timeline/geography conflict between {previous.record.evidence_id} and {current.record.evidence_id}: "
            f"{distance_km:.1f} km apart over {max(hours, 0):.2f} hour(s), {label}."
        )
        current_finding = _get_finding(findings, current.record)
        current_finding.add(
            flag=flag,
            reason=reason,
            contributor="AI impossible travel" if flag == "impossible_travel" else "AI timeline/geo conflict",
            delta=delta,
            confidence_delta=5,
            breakdown_detail=f"timeline/geography conflict ({source_note})",
            case_link=f"Linked with {previous.record.evidence_id} by travel/timeline analysis.",
        )
        current_finding.add_action("Build a two-item timeline card and verify both time anchors before claiming movement inconsistency.")
        previous_finding = _get_finding(findings, previous.record)
        previous_finding.add(
            flag=f"peer_{flag}",
            reason=(
                f"Peer timeline warning: {current.record.evidence_id} forms a suspicious travel pair with this item "
                f"({distance_km:.1f} km over {max(hours, 0):.2f} hour(s))."
            ),
            contributor="AI timeline peer link",
            delta=max(4, delta // 3),
            confidence_delta=2,
            breakdown_detail=f"linked to {current.record.evidence_id} timeline/geography warning",
            case_link=f"Linked with {current.record.evidence_id} by travel/timeline analysis.",
        )


def detect_duplicate_context_conflicts(records: List[EvidenceRecord], findings: Dict[str, BatchAIFinding]) -> None:
    groups: Dict[str, List[EvidenceRecord]] = {}
    for record in records:
        if record.duplicate_group:
            groups.setdefault(record.duplicate_group, []).append(record)
    for group_id, group_records in groups.items():
        if len(group_records) < 2:
            continue
        timestamps = {record.timestamp for record in group_records if record.timestamp and record.timestamp != "Unknown"}
        locations = {record.gps_display for record in group_records if record.gps_display and record.gps_display != "Unavailable"}
        derived_locations = {record.derived_geo_display for record in group_records if record.derived_geo_display and record.derived_geo_display != "Unavailable"}
        sources = {record.source_type for record in group_records if record.source_type and record.source_type != "Unknown"}
        conflict_reasons: List[str] = []
        if len(timestamps) > 1:
            conflict_reasons.append("duplicate peers carry different timestamp anchors")
        if len(locations) > 1 or len(derived_locations) > 1:
            conflict_reasons.append("duplicate peers carry different location displays")
        if len(sources) > 1:
            conflict_reasons.append("duplicate peers were classified as different source profiles")
        if not conflict_reasons:
            continue
        peer_ids = ", ".join(record.evidence_id for record in group_records[:6])
        for record in group_records:
            finding = _get_finding(findings, record)
            finding.add(
                flag="duplicate_context_conflict",
                reason="Duplicate-context warning: " + ", ".join(conflict_reasons[:3]) + ".",
                contributor="AI duplicate context comparison",
                delta=8 if len(conflict_reasons) == 1 else 12,
                confidence_delta=3,
                breakdown_detail=f"duplicate group {group_id} peers disagree on timeline/location/source context",
                case_link=f"Duplicate context group {group_id}: {peer_ids}",
            )
            finding.add_action("Open the duplicate comparison workspace and decide which peer carries the strongest source/originality evidence.")


def metadata_authenticity_review(record: EvidenceRecord, findings: Dict[str, BatchAIFinding]) -> None:
    cues: List[str] = []
    if record.signature_status == "Mismatch" or record.parser_status != "Valid":
        cues.append("container/parser trust issue")
    if editing_tool_detected(record):
        cues.append("editing software tag")
    if record.time_conflicts:
        cues.append("conflicting time candidates")
    if not record.exif and record.source_type in {"Camera Photo", "Edited / Exported", "Unknown"}:
        cues.append("photo-like source with missing EXIF")
    if has_hidden_content_signal(record):
        cues.append("hidden/appended-content indicators")
    if record.derived_geo_display != "Unavailable" and not record.has_gps and record.source_type == "Camera Photo":
        cues.append("camera profile relies only on derived geo")

    if len(cues) >= 3:
        finding = _get_finding(findings, record)
        finding.add(
            flag="metadata_authenticity_cluster",
            reason="AI feature review found a cluster of authenticity risk cues: " + ", ".join(cues[:5]) + ".",
            contributor="AI metadata authenticity cluster",
            delta=10 if len(cues) == 3 else 14,
            confidence_delta=3,
            breakdown_detail="combined metadata/authenticity cues",
        )
        finding.add_action("Prepare a focused authenticity review: parser validation, software history, time anchors, and hidden-content explanation.")


def detect_source_timeline_anomalies(records: List[EvidenceRecord], findings: Dict[str, BatchAIFinding]) -> None:
    """Flag source-profile contradictions that are useful in forensic triage."""
    for record in records:
        point = record_coordinates(record)
        finding = _get_finding(findings, record)
        if record.source_type == "Screenshot" and record.has_gps:
            finding.add(
                flag="source_geo_contradiction",
                reason="Screenshot-like item contains native GPS; this combination needs manual explanation.",
                contributor="AI source/GPS contradiction",
                delta=8,
                confidence_delta=2,
                breakdown_detail="screenshot profile with native GPS metadata",
            )
        if record.source_type == "Camera Photo" and not record.has_gps and record.derived_geo_confidence >= 60:
            finding.add(
                flag="camera_without_native_gps_but_map_lead",
                reason="Camera-like item lacks native GPS but carries a strong derived map/location lead.",
                contributor="AI source/location mismatch",
                delta=6,
                confidence_delta=2,
                breakdown_detail="camera profile relies on derived location lead",
            )
        if point and record.timestamp == "Unknown" and (record.gps_confidence >= 70 or record.derived_geo_confidence >= 60):
            finding.add(
                flag="location_without_time_anchor",
                reason="Location evidence exists, but no trustworthy time anchor was recovered.",
                contributor="AI time/location completeness check",
                delta=5,
                confidence_delta=1,
                breakdown_detail="location lead without a reliable timestamp",
            )
