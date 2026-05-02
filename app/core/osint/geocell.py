from __future__ import annotations

"""Optional H3/shapely helpers for privacy-safe geo confidence zones.

This module is deliberately optional.  If h3/shapely are not installed, GeoTrace
falls back to a simple bounding box so the application still starts.
"""

from dataclasses import asdict, dataclass
import math
from typing import Any

try:
    import h3  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    h3 = None  # type: ignore[assignment]

try:
    from shapely.geometry import Point, mapping  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Point = None  # type: ignore[assignment]
    mapping = None  # type: ignore[assignment]


@dataclass(slots=True)
class GeoConfidenceZone:
    available: bool
    method: str
    latitude: float | None = None
    longitude: float | None = None
    radius_m: int = 0
    h3_index: str = ""
    h3_resolution: int = 0
    geojson: dict[str, Any] | None = None
    limitations: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["limitations"] = list(self.limitations or [])
        return row


def _valid(lat: float | None, lon: float | None) -> bool:
    return lat is not None and lon is not None and -90 <= float(lat) <= 90 and -180 <= float(lon) <= 180


def _resolution_for_radius(radius_m: int) -> int:
    # Conservative visual buckets: smaller radius => higher H3 resolution.
    if radius_m <= 75:
        return 10
    if radius_m <= 250:
        return 9
    if radius_m <= 900:
        return 8
    if radius_m <= 3000:
        return 7
    if radius_m <= 10000:
        return 6
    return 5


def _fallback_box(lat: float, lon: float, radius_m: int) -> dict[str, Any]:
    # Approximate meters -> degrees; enough for UI visualization, not surveying.
    d_lat = radius_m / 111_320.0
    d_lon = radius_m / max(1.0, 111_320.0 * math.cos(math.radians(lat)))
    coords = [
        [lon - d_lon, lat - d_lat],
        [lon + d_lon, lat - d_lat],
        [lon + d_lon, lat + d_lat],
        [lon - d_lon, lat + d_lat],
        [lon - d_lon, lat - d_lat],
    ]
    return {"type": "Polygon", "coordinates": [coords]}


def build_geo_confidence_zone(lat: float | None, lon: float | None, *, radius_m: int, source: str = "derived") -> GeoConfidenceZone:
    if not _valid(lat, lon):
        return GeoConfidenceZone(False, "unavailable", limitations=["No valid coordinate pair was supplied."])
    latitude = float(lat)
    longitude = float(lon)
    limitations = [
        "Confidence zone is for review/visualization only.",
        "Derived/OCR/OSINT coordinates must not be described as native GPS.",
    ]
    resolution = _resolution_for_radius(max(1, int(radius_m or 0)))
    if h3 is not None:
        try:
            # h3-py v4 uses latlng_to_cell/cell_to_boundary. Older versions use geo_to_h3/h3_to_geo_boundary.
            if hasattr(h3, "latlng_to_cell"):
                cell = h3.latlng_to_cell(latitude, longitude, resolution)
                boundary = h3.cell_to_boundary(cell)
            else:  # pragma: no cover - old h3-py compatibility
                cell = h3.geo_to_h3(latitude, longitude, resolution)
                boundary = h3.h3_to_geo_boundary(cell)
            coords = [[float(lng), float(lat)] for lat, lng in boundary]
            if coords and coords[0] != coords[-1]:
                coords.append(coords[0])
            return GeoConfidenceZone(
                True,
                f"h3:{source}",
                latitude=latitude,
                longitude=longitude,
                radius_m=int(radius_m),
                h3_index=str(cell),
                h3_resolution=resolution,
                geojson={"type": "Polygon", "coordinates": [coords]},
                limitations=limitations,
            )
        except Exception as exc:
            limitations.append(f"H3 zone failed, fallback box used: {exc.__class__.__name__}")
    return GeoConfidenceZone(
        True,
        f"fallback-box:{source}",
        latitude=latitude,
        longitude=longitude,
        radius_m=int(radius_m),
        h3_resolution=resolution,
        geojson=_fallback_box(latitude, longitude, int(radius_m)),
        limitations=limitations + ["Install requirements-geo.txt to enable H3 hex cells."],
    )
