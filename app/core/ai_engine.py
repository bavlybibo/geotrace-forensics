from __future__ import annotations

"""AI-assisted batch risk analysis for GeoTrace.

The module is intentionally conservative: it enriches the existing forensic
scoring pipeline with explainable batch-level signals while keeping the tool
usable without heavy ML dependencies. When scikit-learn is installed, the
geographic outlier detector uses IsolationForest. Otherwise, it falls back to a
transparent median-distance heuristic.
"""

from dataclasses import dataclass, field
from datetime import datetime
from math import atan2, cos, radians, sin, sqrt
from statistics import median
from typing import Dict, Iterable, List, Optional, Tuple

from .models import EvidenceRecord

try:  # Optional dependency; the fallback keeps classroom/demo installs simple.
    from sklearn.ensemble import IsolationForest  # type: ignore
except Exception:  # pragma: no cover - exercised when sklearn is absent
    IsolationForest = None  # type: ignore


DATE_FORMATS = ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S")
AI_PROVIDER_NAME = "GeoTrace AI Risk Engine v1"


@dataclass
class BatchAIFinding:
    provider: str = AI_PROVIDER_NAME
    score_delta: int = 0
    confidence_delta: int = 0
    label: str = "No batch-level AI flags"
    summary: str = "AI batch assessment completed; no cross-evidence anomaly was identified for this item."
    flags: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    contributors: List[str] = field(default_factory=list)
    breakdown: List[str] = field(default_factory=list)

    def add(
        self,
        *,
        flag: str,
        reason: str,
        contributor: str,
        delta: int,
        confidence_delta: int = 2,
        breakdown_detail: Optional[str] = None,
    ) -> None:
        if flag not in self.flags:
            self.flags.append(flag)
        if contributor not in self.contributors:
            self.contributors.append(contributor)
        self.reasons.append(reason)
        self.score_delta += max(0, delta)
        self.confidence_delta += max(0, confidence_delta)
        self.breakdown.append(f"AI +{max(0, delta)} — {breakdown_detail or reason}")
        self._refresh_label()

    def _refresh_label(self) -> None:
        if self.score_delta >= 24 or len(self.flags) >= 3:
            self.label = "High AI review priority"
        elif self.score_delta >= 10 or self.flags:
            self.label = "AI review recommended"
        else:
            self.label = "No batch-level AI flags"
        if self.flags:
            self.summary = f"{self.label}: " + "; ".join(self.reasons[:3])


def _record_coordinates(record: EvidenceRecord) -> Optional[Tuple[float, float, str, int]]:
    if record.gps_latitude is not None and record.gps_longitude is not None:
        return float(record.gps_latitude), float(record.gps_longitude), "native GPS", max(record.gps_confidence, 70)
    if record.derived_latitude is not None and record.derived_longitude is not None:
        confidence = max(0, min(int(record.derived_geo_confidence or 0), 70))
        if confidence >= 45:
            return float(record.derived_latitude), float(record.derived_longitude), "derived geo", confidence
    return None


def _parse_timestamp(value: str) -> Optional[datetime]:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            continue
    return None


def _haversine_km(left_lat: float, left_lon: float, right_lat: float, right_lon: float) -> float:
    radius_km = 6371.0088
    lat1 = radians(left_lat)
    lat2 = radians(right_lat)
    delta_lat = radians(right_lat - left_lat)
    delta_lon = radians(right_lon - left_lon)
    a = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return radius_km * 2 * atan2(sqrt(a), sqrt(1 - a))


def _get_finding(findings: Dict[str, BatchAIFinding], record: EvidenceRecord) -> BatchAIFinding:
    return findings.setdefault(record.evidence_id, BatchAIFinding())


def _detect_location_outliers(records: List[EvidenceRecord], findings: Dict[str, BatchAIFinding]) -> None:
    geo_points: List[Tuple[EvidenceRecord, float, float, str, int]] = []
    for record in records:
        point = _record_coordinates(record)
        if point is None:
            continue
        lat, lon, source, confidence = point
        geo_points.append((record, lat, lon, source, confidence))

    if len(geo_points) < 3:
        return

    # Optional ML path: IsolationForest catches multi-dimensional geo outliers.
    ml_outliers: set[str] = set()
    if IsolationForest is not None and len(geo_points) >= 4:
        try:
            contamination = min(0.35, max(0.10, 1 / len(geo_points)))
            model = IsolationForest(n_estimators=100, contamination=contamination, random_state=42)
            predictions = model.fit_predict([[lat, lon] for _, lat, lon, _, _ in geo_points])
            for (record, *_), prediction in zip(geo_points, predictions):
                if prediction == -1:
                    ml_outliers.add(record.evidence_id)
        except Exception:
            ml_outliers = set()

    center_lat = median([lat for _, lat, _, _, _ in geo_points])
    center_lon = median([lon for _, _, lon, _, _ in geo_points])
    distances = [
        _haversine_km(lat, lon, center_lat, center_lon)
        for _, lat, lon, _, _ in geo_points
    ]
    median_distance = median(distances) if distances else 0.0
    threshold = max(35.0, median_distance * 3.5 + 15.0)

    for (record, lat, lon, source, confidence), distance_km in zip(geo_points, distances):
        is_heuristic_outlier = distance_km >= threshold and distance_km >= 45.0
        is_ml_outlier = record.evidence_id in ml_outliers and distance_km >= max(20.0, median_distance * 2.2)
        if not (is_heuristic_outlier or is_ml_outlier):
            continue
        delta = 18 if source == "native GPS" else 12
        finding = _get_finding(findings, record)
        finding.add(
            flag="geo_outlier",
            reason=(
                f"This item is a geographic outlier against the case cluster: about {distance_km:.1f} km "
                f"from the median case location using {source}."
            ),
            contributor="AI location outlier",
            delta=delta,
            confidence_delta=4 if confidence >= 60 else 2,
            breakdown_detail=f"geographic outlier ({distance_km:.1f} km from case median)",
        )


def _detect_impossible_travel(records: List[EvidenceRecord], findings: Dict[str, BatchAIFinding]) -> None:
    timeline_points: List[Tuple[datetime, EvidenceRecord, float, float, str]] = []
    for record in records:
        timestamp = _parse_timestamp(record.timestamp)
        point = _record_coordinates(record)
        if timestamp is None or point is None:
            continue
        lat, lon, source, _ = point
        timeline_points.append((timestamp, record, lat, lon, source))

    if len(timeline_points) < 2:
        return

    timeline_points.sort(key=lambda item: (item[0], item[1].evidence_id))
    for previous, current in zip(timeline_points, timeline_points[1:]):
        previous_time, previous_record, previous_lat, previous_lon, previous_source = previous
        current_time, current_record, current_lat, current_lon, current_source = current
        hours = (current_time - previous_time).total_seconds() / 3600
        distance_km = _haversine_km(previous_lat, previous_lon, current_lat, current_lon)
        if distance_km < 25:
            continue
        if hours <= 0:
            speed = float("inf")
        else:
            speed = distance_km / hours

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

        source_note = f"{previous_source} → {current_source}"
        reason = (
            f"Timeline/geography conflict between {previous_record.evidence_id} and {current_record.evidence_id}: "
            f"{distance_km:.1f} km apart over {max(hours, 0):.2f} hour(s), {label}."
        )
        current_finding = _get_finding(findings, current_record)
        current_finding.add(
            flag=flag,
            reason=reason,
            contributor="AI impossible travel" if flag == "impossible_travel" else "AI timeline/geo conflict",
            delta=delta,
            confidence_delta=5,
            breakdown_detail=f"timeline/geography conflict ({source_note})",
        )
        # Mark the previous item lightly so the pair is discoverable from both sides.
        previous_finding = _get_finding(findings, previous_record)
        previous_finding.add(
            flag=f"peer_{flag}",
            reason=(
                f"Peer timeline warning: {current_record.evidence_id} forms a suspicious travel pair with this item "
                f"({distance_km:.1f} km over {max(hours, 0):.2f} hour(s))."
            ),
            contributor="AI timeline peer link",
            delta=max(4, delta // 3),
            confidence_delta=2,
            breakdown_detail=f"linked to {current_record.evidence_id} timeline/geography warning",
        )


def _metadata_authenticity_review(record: EvidenceRecord, findings: Dict[str, BatchAIFinding]) -> None:
    cues: List[str] = []
    if record.signature_status == "Mismatch" or record.parser_status != "Valid":
        cues.append("container/parser trust issue")
    if record.software not in {"", "N/A", "Unknown"} and any(
        token in record.software.lower() for token in ["photoshop", "lightroom", "snapseed", "gimp", "canva"]
    ):
        cues.append("editing software tag")
    if record.time_conflicts:
        cues.append("conflicting time candidates")
    if not record.exif and record.source_type in {"Camera Photo", "Edited / Exported", "Unknown"}:
        cues.append("photo-like source with missing EXIF")
    if record.hidden_code_indicators or record.hidden_suspicious_embeds or record.hidden_carved_files:
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


def run_ai_batch_assessment(records: Iterable[EvidenceRecord]) -> Dict[str, BatchAIFinding]:
    """Return explainable AI-assisted findings keyed by evidence id.

    The caller merges these findings into the existing scoring fields, which keeps
    reports/UI backward-compatible while giving the project a concrete AI layer.
    """
    records_list = list(records)
    findings: Dict[str, BatchAIFinding] = {record.evidence_id: BatchAIFinding() for record in records_list}

    _detect_location_outliers(records_list, findings)
    _detect_impossible_travel(records_list, findings)
    for record in records_list:
        _metadata_authenticity_review(record, findings)

    for finding in findings.values():
        finding.score_delta = max(0, min(35, int(finding.score_delta)))
        finding.confidence_delta = max(0, min(12, int(finding.confidence_delta)))
        finding._refresh_label()
    return findings
