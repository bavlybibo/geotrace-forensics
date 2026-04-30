from __future__ import annotations

"""Privacy-gated map provider bridge for location verification.

The bridge does not upload evidence.  It converts recovered anchors (native GPS,
visible map coordinates, or strong place labels) into provider search links and,
only when explicitly enabled by environment variable, performs a bounded online
geocode/reverse-geocode lookup.
"""

from dataclasses import asdict, dataclass, field

from .evidence import anchor_kind_from_source, claim_policy_for_anchor
import json
import os
from typing import Any, Iterable
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen


@dataclass(slots=True)
class MapProviderLink:
    provider: str
    label: str
    url: str
    kind: str = "coordinate"
    privacy_note: str = "Opens the recovered anchor in a third-party map. Do not use with sensitive evidence unless approved."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MapProviderBridge:
    status: str = "not_evaluated"
    anchor_source: str = "Unavailable"
    anchor_label: str = "Unavailable"
    latitude: float | None = None
    longitude: float | None = None
    provider_links: list[MapProviderLink] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    reverse_lookup_label: str = "Unavailable"
    reverse_lookup_confidence: int = 0
    online_lookup_enabled: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["provider_links"] = [item.to_dict() for item in self.provider_links]
        return row

    def to_summary_lines(self) -> list[str]:
        lines = [
            f"Bridge status: {self.status}",
            f"Anchor source: {self.anchor_source}",
            f"Anchor label: {self.anchor_label}",
        ]
        if self.latitude is not None and self.longitude is not None:
            lines.append(f"Coordinates: {self.latitude:.6f}, {self.longitude:.6f}")
        if self.reverse_lookup_label != "Unavailable":
            lines.append(f"Reverse lookup: {self.reverse_lookup_label} ({self.reverse_lookup_confidence}%)")
        if self.search_queries:
            lines.append("Search queries: " + " | ".join(self.search_queries[:4]))
        if self.provider_links:
            lines.append("Provider links:")
            lines.extend(f"- {item.provider}: {item.url}" for item in self.provider_links[:6])
        if self.warnings:
            lines.append("Warnings:")
            lines.extend(f"- {warning}" for warning in self.warnings[:4])
        return lines


def _env_online_enabled() -> bool:
    return os.environ.get("GEOTRACE_ONLINE_MAP_LOOKUP", "0").strip().lower() in {"1", "true", "yes", "on"}


def _coerce_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        out = float(value)
    except Exception:
        return None
    return out


def _valid_pair(lat: float | None, lon: float | None) -> bool:
    return lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180


def _first_clean(items: Iterable[Any]) -> str:
    for item in items:
        text = str(item or "").strip()
        if text and text not in {"Unavailable", "Unknown", "None", "N/A", "—"}:
            return text
    return ""


def _unique(items: Iterable[str], limit: int = 8) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = " ".join(str(item or "").split()).strip(" -:|•·")
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _coordinate_links(lat: float, lon: float, label: str, *, kind: str = "coordinate") -> list[MapProviderLink]:
    coord = f"{lat:.6f},{lon:.6f}"
    label_q = quote_plus(label or "GeoTrace evidence anchor")
    return [
        MapProviderLink("Google Maps", label or coord, f"https://www.google.com/maps/search/?api=1&query={coord}", kind),
        MapProviderLink("OpenStreetMap", label or coord, f"https://www.openstreetmap.org/?mlat={lat:.6f}&mlon={lon:.6f}#map=16/{lat:.6f}/{lon:.6f}", kind),
        MapProviderLink("Apple Maps", label or coord, f"https://maps.apple.com/?ll={coord}&q={label_q}", kind),
    ]


def _place_links(query: str) -> list[MapProviderLink]:
    q = quote_plus(query)
    return [
        MapProviderLink("Google Maps", query, f"https://www.google.com/maps/search/?api=1&query={q}", "place_search"),
        MapProviderLink("OpenStreetMap", query, f"https://www.openstreetmap.org/search?query={q}", "place_search"),
        MapProviderLink("Apple Maps", query, f"https://maps.apple.com/?q={q}", "place_search"),
    ]


def _reverse_nominatim(lat: float, lon: float, *, timeout: float = 3.0) -> tuple[str, int, str]:
    params = urlencode({"format": "jsonv2", "lat": f"{lat:.7f}", "lon": f"{lon:.7f}", "zoom": "16", "addressdetails": "1"})
    url = f"https://nominatim.openstreetmap.org/reverse?{params}"
    request = Request(url, headers={"User-Agent": "GeoTraceForensicsX/12.10 map-verification (local analyst approved)"})
    with urlopen(request, timeout=timeout) as response:  # nosec: URL is fixed to OSM reverse endpoint; opt-in only.
        payload = json.loads(response.read(80_000).decode("utf-8", errors="replace"))
    label = str(payload.get("display_name", "")).strip()
    if not label:
        return "Unavailable", 0, "Nominatim returned no display_name."
    return label[:240], 78, "Nominatim reverse lookup completed after explicit online opt-in."


def _forward_nominatim(query: str, *, timeout: float = 3.0) -> tuple[float | None, float | None, str, int, str]:
    params = urlencode({"format": "jsonv2", "q": query, "limit": "1", "addressdetails": "1"})
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    request = Request(url, headers={"User-Agent": "GeoTraceForensicsX/12.10 map-verification (local analyst approved)"})
    with urlopen(request, timeout=timeout) as response:  # nosec: URL is fixed to OSM search endpoint; opt-in only.
        payload = json.loads(response.read(80_000).decode("utf-8", errors="replace"))
    if not isinstance(payload, list) or not payload:
        return None, None, "Unavailable", 0, "Nominatim returned no search candidate."
    top = payload[0]
    lat = _coerce_float(top.get("lat"))
    lon = _coerce_float(top.get("lon"))
    label = str(top.get("display_name", query)).strip()[:240]
    return lat, lon, label or query, 72, "Nominatim forward lookup completed after explicit online opt-in."


def build_map_provider_bridge(record: Any) -> MapProviderBridge:
    """Build map provider links for a single evidence record without needing a huge local DB."""

    warnings: list[str] = []
    online = _env_online_enabled()
    lat = _coerce_float(getattr(record, "gps_latitude", None))
    lon = _coerce_float(getattr(record, "gps_longitude", None))
    anchor_source = "Native EXIF GPS" if _valid_pair(lat, lon) else "Unavailable"
    anchor_label = str(getattr(record, "gps_display", "Unavailable") or "Unavailable")

    if not _valid_pair(lat, lon):
        lat = _coerce_float(getattr(record, "derived_latitude", None))
        lon = _coerce_float(getattr(record, "derived_longitude", None))
        if _valid_pair(lat, lon):
            anchor_source = str(getattr(record, "derived_geo_source", "Derived map/OCR coordinate") or "Derived map/OCR coordinate")
            anchor_label = str(getattr(record, "derived_geo_display", "Derived coordinate") or "Derived coordinate")

    if not _valid_pair(lat, lon):
        payload = getattr(record, "map_interactive_payload", {}) or {}
        if isinstance(payload, dict) and payload.get("available"):
            lat = _coerce_float(payload.get("latitude"))
            lon = _coerce_float(payload.get("longitude"))
            if _valid_pair(lat, lon):
                anchor_source = str(payload.get("source", "Map interactive payload") or "Map interactive payload")
                anchor_label = str(payload.get("label", "Map anchor") or "Map anchor")

    place_query = _first_clean([
        getattr(record, "possible_place", ""),
        getattr(record, "location_estimate_label", ""),
        getattr(record, "candidate_area", ""),
        getattr(record, "candidate_city", ""),
        *((getattr(record, "landmarks_detected", []) or [])[:2]),
        *((getattr(record, "place_candidates", []) or [])[:2]),
    ])
    search_queries = _unique([
        place_query,
        *list(getattr(record, "place_candidates", []) or [])[:4],
        *list(getattr(record, "landmarks_detected", []) or [])[:4],
        getattr(record, "candidate_area", ""),
        getattr(record, "candidate_city", ""),
    ], limit=6)

    links: list[MapProviderLink] = []
    status = "no_anchor"
    reverse_label = "Unavailable"
    reverse_conf = 0

    if _valid_pair(lat, lon):
        anchor_kind = anchor_kind_from_source(anchor_source, has_native_gps=anchor_source == "Native EXIF GPS", has_coordinates=True)
        policy = claim_policy_for_anchor(anchor_kind, confidence=int(getattr(record, "gps_confidence", 0) or getattr(record, "derived_geo_confidence", 0) or 0), source=anchor_source)
        if anchor_kind == "native_gps":
            status = "native_gps_bridge_ready"
            link_kind = "native_gps_coordinate"
        elif anchor_kind == "derived_coordinate":
            status = "derived_coordinate_bridge_ready"
            link_kind = "derived_coordinate"
        else:
            status = "approximate_place_bridge_review_required"
            link_kind = "approximate_coordinate"
            warnings.append("Coordinates are from an approximate/offline place candidate; do not report them as exact GPS.")
        warnings.append(f"Claim policy: {policy.claim_label}; radius ~{policy.radius_m}m; {policy.verification_rule}")
        links.extend(_coordinate_links(float(lat), float(lon), anchor_label, kind=link_kind))
        if online:
            try:
                reverse_label, reverse_conf, note = _reverse_nominatim(float(lat), float(lon))
                warnings.append(note)
            except Exception as exc:
                warnings.append(f"Online reverse lookup failed: {exc.__class__.__name__}: {exc}")
    elif place_query:
        status = "place_search_bridge_ready"
        anchor_source = "OCR/place label search"
        anchor_label = place_query
        links.extend(_place_links(place_query))
        if online:
            try:
                f_lat, f_lon, label, conf, note = _forward_nominatim(place_query)
                warnings.append(note)
                reverse_label = label
                reverse_conf = conf
                if _valid_pair(f_lat, f_lon):
                    lat = float(f_lat)  # type: ignore[arg-type]
                    lon = float(f_lon)  # type: ignore[arg-type]
                    links = _coordinate_links(lat, lon, label, kind="online_place_coordinate_review_required") + links
                    status = "online_place_resolved_review_required"
                    warnings.append("Online forward lookup returned a coordinate candidate; keep it as review-required, not native GPS.")
            except Exception as exc:
                warnings.append(f"Online forward lookup failed: {exc.__class__.__name__}: {exc}")
    else:
        warnings.append("No native GPS, derived coordinate, map URL coordinate, or strong place label is available yet.")

    if not online:
        warnings.append("Online geocoding is OFF by default. Set GEOTRACE_ONLINE_MAP_LOOKUP=1 only after privacy approval.")

    return MapProviderBridge(
        status=status,
        anchor_source=anchor_source,
        anchor_label=anchor_label,
        latitude=float(lat) if _valid_pair(lat, lon) else None,
        longitude=float(lon) if _valid_pair(lat, lon) else None,
        provider_links=links[:9],
        search_queries=search_queries,
        reverse_lookup_label=reverse_label,
        reverse_lookup_confidence=reverse_conf,
        online_lookup_enabled=online,
        warnings=_unique(warnings, limit=6),
    )
