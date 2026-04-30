from __future__ import annotations

"""Case-level map reconstruction helpers.

The reconstruction engine never treats screenshot-derived coordinates as proof.
It groups native GPS, map URL/OCR coordinates, and derived coordinate fields into
explainable anchors, then summarizes route/cluster limitations.
"""

from dataclasses import asdict, dataclass, field
from math import asin, cos, radians, sin, sqrt
import re
from typing import Any, Iterable

from .models import EvidenceRecord

_COORD_RE = re.compile(r'(-?\d{1,2}\.\d{3,})\s*,\s*(-?\d{1,3}\.\d{3,})')

@dataclass(slots=True)
class MapAnchor:
    evidence_id: str
    file_name: str
    latitude: float
    longitude: float
    source: str
    confidence: int
    radius_m: int
    label: str = ''

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(slots=True)
class MapReconstructionSummary:
    anchor_count: int
    native_gps_count: int
    derived_count: int
    centroid: dict[str, float] | None = None
    bounding_box: dict[str, float] | None = None
    route_story: str = 'No coordinate anchors available.'
    anomalies: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    anchors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def _coerce_coordinate_pair(lat: Any, lon: Any) -> tuple[float | None, float | None]:
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return None, None
    if not _valid_coordinate(lat_f, lon_f):
        return None, None
    return lat_f, lon_f


def _candidate_coordinate(record: EvidenceRecord) -> tuple[float | None, float | None, str]:
    # Native GPS is only valid when the EXIF/device coordinate fields themselves
    # are present and parseable. Do not let a stale has_gps flag turn derived
    # coordinates into a GPS claim or crash the map workspace.
    if getattr(record, 'has_gps', False):
        lat_f, lon_f = _coerce_coordinate_pair(getattr(record, 'gps_latitude', None), getattr(record, 'gps_longitude', None))
        if lat_f is not None and lon_f is not None:
            return lat_f, lon_f, 'native-gps'
    direct_lat = getattr(record, 'derived_latitude', None)
    direct_lon = getattr(record, 'derived_longitude', None)
    lat_f, lon_f = _coerce_coordinate_pair(direct_lat, direct_lon)
    if lat_f is not None and lon_f is not None:
        return lat_f, lon_f, 'derived-coordinate-field'
    fields = [
        getattr(record, 'derived_geo_display', ''),
        ' '.join(getattr(record, 'possible_geo_clues', []) or []),
        getattr(record, 'map_intelligence_summary', ''),
        getattr(record, 'ocr_raw_text', ''),
        getattr(record, 'visible_text_excerpt', ''),
    ]
    for text in fields:
        match = _COORD_RE.search(str(text or ''))
        if match:
            return float(match.group(1)), float(match.group(2)), 'derived-map-or-ocr-coordinate'
    return None, None, 'no-coordinate-anchor'

def _valid_coordinate(lat: float | None, lon: float | None) -> bool:
    if lat is None or lon is None:
        return False
    try:
        return -90.0 <= float(lat) <= 90.0 and -180.0 <= float(lon) <= 180.0
    except (TypeError, ValueError):
        return False


def _distance_km(a: MapAnchor, b: MapAnchor) -> float:
    radius_km = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [a.latitude, a.longitude, b.latitude, b.longitude])
    d_lat = lat2 - lat1
    d_lon = lon2 - lon1
    h = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
    return 2 * radius_km * asin(sqrt(h))

def build_map_reconstruction(records: Iterable[EvidenceRecord]) -> MapReconstructionSummary:
    anchors: list[MapAnchor] = []
    for record in records:
        lat, lon, source = _candidate_coordinate(record)
        if not _valid_coordinate(lat, lon):
            continue
        confidence = int(
            getattr(record, 'gps_confidence', 0)
            or getattr(record, 'derived_geo_confidence', 0)
            or getattr(record, 'map_answer_readiness_score', 0)
            or getattr(record, 'map_intelligence_confidence', 0)
            or (95 if source == 'native-gps' else 50)
        )
        radius = int(getattr(record, 'map_confidence_radius_m', 0) or (25 if source == 'native-gps' else 150))
        label = str(getattr(record, 'possible_place', '') or getattr(record, 'location_estimate_label', '') or '')
        anchors.append(MapAnchor(
            evidence_id=str(getattr(record, 'evidence_id', '')),
            file_name=str(getattr(record, 'file_name', '')),
            latitude=lat,
            longitude=lon,
            source=source,
            confidence=max(0, min(100, confidence)),
            radius_m=max(1, radius),
            label=label,
        ))

    if not anchors:
        return MapReconstructionSummary(
            anchor_count=0,
            native_gps_count=0,
            derived_count=0,
            limitations=['No native GPS, OCR coordinate, map URL coordinate, or derived coordinate field was available.'],
            anchors=[],
        )

    native = sum(1 for anchor in anchors if anchor.source == 'native-gps')
    derived = len(anchors) - native
    latitudes = [a.latitude for a in anchors]
    longitudes = [a.longitude for a in anchors]
    centroid = {'latitude': round(sum(latitudes) / len(latitudes), 6), 'longitude': round(sum(longitudes) / len(longitudes), 6)}
    bbox = {
        'min_latitude': round(min(latitudes), 6),
        'max_latitude': round(max(latitudes), 6),
        'min_longitude': round(min(longitudes), 6),
        'max_longitude': round(max(longitudes), 6),
    }

    anomalies: list[str] = []
    for idx in range(1, len(anchors)):
        distance = _distance_km(anchors[idx - 1], anchors[idx])
        if distance >= 500:
            anomalies.append(
                f"Large spatial jump: {anchors[idx - 1].evidence_id} → {anchors[idx].evidence_id} is ~{distance:.0f} km; verify timeline/order/source before using as a route."
            )

    if len(anchors) == 1:
        story = 'Single coordinate anchor. Treat as a location lead unless native GPS/source URL corroborates it.'
    elif anomalies:
        story = 'Multiple coordinate anchors exist, but one or more large jumps need timeline corroboration.'
    else:
        story = 'Multiple coordinate anchors form a coherent local cluster; verify source-side before final reporting.'

    limitations = []
    if derived:
        limitations.append('Derived OCR/map coordinates are leads, not native device GPS.')
    if native == 0:
        limitations.append('No native GPS anchor is present in the coordinate set.')
    if len(anchors) < 2:
        limitations.append('A route cannot be reconstructed from a single anchor.')

    return MapReconstructionSummary(
        anchor_count=len(anchors),
        native_gps_count=native,
        derived_count=derived,
        centroid=centroid,
        bounding_box=bbox,
        route_story=story,
        anomalies=anomalies,
        limitations=limitations,
        anchors=[anchor.to_dict() for anchor in anchors],
    )

def render_map_reconstruction_text(records: Iterable[EvidenceRecord]) -> str:
    summary = build_map_reconstruction(records)
    lines = [
        '[MAP RECONSTRUCTION]',
        '====================',
        f"Anchors: {summary.anchor_count} | Native GPS: {summary.native_gps_count} | Derived: {summary.derived_count}",
    ]
    if summary.centroid:
        lines.append(f"Centroid: {summary.centroid['latitude']}, {summary.centroid['longitude']}")
    if summary.bounding_box:
        lines.append(f"Bounds: {summary.bounding_box}")
    lines.extend(['', f'Story: {summary.route_story}', '', 'Anchors:'])
    lines.extend([
        f"- {a['evidence_id']} | {a['latitude']}, {a['longitude']} | {a['source']} | conf {a['confidence']}% | r~{a['radius_m']}m"
        for a in summary.anchors
    ] or ['- None'])
    if summary.anomalies:
        lines.extend(['', 'Anomalies:'])
        lines.extend(f'- {item}' for item in summary.anomalies)
    if summary.limitations:
        lines.extend(['', 'Limitations:'])
        lines.extend(f'- {item}' for item in summary.limitations)
    return '\n'.join(lines).strip() + '\n'
