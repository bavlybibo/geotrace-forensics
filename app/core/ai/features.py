from __future__ import annotations

"""Feature extraction helpers for the deterministic AI layer."""

from dataclasses import dataclass
from datetime import datetime
from math import atan2, cos, radians, sin, sqrt
from typing import Iterable, Optional, Tuple

from ..models import EvidenceRecord

DATE_FORMATS = ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S")


@dataclass(frozen=True)
class GeoPoint:
    record: EvidenceRecord
    latitude: float
    longitude: float
    source: str
    confidence: int


@dataclass(frozen=True)
class TimelinePoint:
    timestamp: datetime
    record: EvidenceRecord
    latitude: float
    longitude: float
    source: str


def parse_ai_timestamp(value: str) -> Optional[datetime]:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            continue
    return None


def record_coordinates(record: EvidenceRecord) -> Optional[Tuple[float, float, str, int]]:
    if record.gps_latitude is not None and record.gps_longitude is not None:
        return float(record.gps_latitude), float(record.gps_longitude), "native GPS", max(record.gps_confidence, 70)
    if record.derived_latitude is not None and record.derived_longitude is not None:
        confidence = max(0, min(int(record.derived_geo_confidence or 0), 70))
        if confidence >= 45:
            return float(record.derived_latitude), float(record.derived_longitude), "derived geo", confidence
    return None


def geo_points(records: Iterable[EvidenceRecord]) -> list[GeoPoint]:
    points: list[GeoPoint] = []
    for record in records:
        point = record_coordinates(record)
        if point is None:
            continue
        lat, lon, source, confidence = point
        points.append(GeoPoint(record, lat, lon, source, confidence))
    return points


def timeline_points(records: Iterable[EvidenceRecord]) -> list[TimelinePoint]:
    points: list[TimelinePoint] = []
    for record in records:
        timestamp = parse_ai_timestamp(record.timestamp)
        point = record_coordinates(record)
        if timestamp is None or point is None:
            continue
        lat, lon, source, _ = point
        points.append(TimelinePoint(timestamp, record, lat, lon, source))
    points.sort(key=lambda item: (item.timestamp, item.record.evidence_id))
    return points


def haversine_km(left_lat: float, left_lon: float, right_lat: float, right_lon: float) -> float:
    radius_km = 6371.0088
    lat1 = radians(left_lat)
    lat2 = radians(right_lat)
    delta_lat = radians(right_lat - left_lat)
    delta_lon = radians(right_lon - left_lon)
    a = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return radius_km * 2 * atan2(sqrt(a), sqrt(1 - a))


def editing_tool_detected(record: EvidenceRecord) -> bool:
    software = (record.software or "").lower()
    return any(token in software for token in ["photoshop", "lightroom", "snapseed", "gimp", "canva", "pixlr"])


def has_textual_location_lead(record: EvidenceRecord) -> bool:
    return bool(record.ocr_map_labels or record.ocr_location_entities or record.visible_location_strings or record.possible_geo_clues)


def has_hidden_content_signal(record: EvidenceRecord) -> bool:
    return bool(record.hidden_code_indicators or record.hidden_suspicious_embeds or record.hidden_carved_files or record.hidden_payload_markers or getattr(record, "pixel_hidden_indicators", []) or getattr(record, "pixel_lsb_strings", []))
