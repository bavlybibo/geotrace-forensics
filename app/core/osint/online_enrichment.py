from __future__ import annotations

"""Privacy-gated online OSINT provider helpers.

Nothing in this module runs unless the analyst explicitly opts in with:
    GEOTRACE_OSINT_ONLINE=1
or:
    GEOTRACE_ONLINE_MAP_LOOKUP=1

The helpers send only analyst-provided coordinates/place labels, never raw evidence
files.  Results are returned as review-required corroboration leads.
"""

from dataclasses import asdict, dataclass, field
import os
from typing import Any
from urllib.parse import urlencode

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    requests = None  # type: ignore[assignment]

try:
    import requests_cache  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    requests_cache = None  # type: ignore[assignment]


USER_AGENT = "GeoTraceForensicsX/12.10 optional-osint (local analyst approved)"


@dataclass(slots=True)
class OnlineLead:
    provider: str
    query_type: str
    label: str
    confidence: int
    url: str = ""
    coordinates: tuple[float, float] | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        if self.coordinates:
            row["coordinates"] = {"lat": self.coordinates[0], "lon": self.coordinates[1]}
        return row


def online_osint_enabled() -> bool:
    return os.environ.get("GEOTRACE_OSINT_ONLINE", os.environ.get("GEOTRACE_ONLINE_MAP_LOOKUP", "0")).strip().lower() in {"1", "true", "yes", "on"}


def _session():
    if requests is None:
        raise RuntimeError("requests is not installed. Install requirements-osint.txt first.")
    if requests_cache is not None:
        cache_name = os.environ.get("GEOTRACE_OSINT_CACHE", "geotrace_osint_cache")
        try:
            return requests_cache.CachedSession(cache_name, expire_after=86400)
        except Exception:
            pass
    return requests.Session()


def _get_json(url: str, *, params: dict[str, Any] | None = None, timeout: float = 8.0) -> Any:
    if not online_osint_enabled():
        raise PermissionError("Online OSINT is disabled. Set GEOTRACE_OSINT_ONLINE=1 after case/privacy approval.")
    session = _session()
    response = session.get(url, params=params or {}, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def nominatim_search(query: str, *, limit: int = 3) -> list[dict[str, Any]]:
    params = {"format": "jsonv2", "q": query, "limit": str(max(1, min(limit, 10))), "addressdetails": "1"}
    payload = _get_json("https://nominatim.openstreetmap.org/search", params=params)
    leads: list[OnlineLead] = []
    for item in payload if isinstance(payload, list) else []:
        try:
            lat, lon = float(item.get("lat")), float(item.get("lon"))
        except Exception:
            lat = lon = None  # type: ignore[assignment]
        label = str(item.get("display_name") or query).strip()
        leads.append(OnlineLead(
            provider="Nominatim",
            query_type="place_search",
            label=label[:260],
            confidence=72,
            url="https://nominatim.openstreetmap.org/search?" + urlencode(params),
            coordinates=(lat, lon) if lat is not None and lon is not None else None,
            raw={k: item.get(k) for k in ("place_id", "osm_type", "osm_id", "class", "type", "importance")},
            limitations=["Online geocoder result; corroboration lead only, not native GPS."],
        ))
    return [lead.to_dict() for lead in leads]


def nominatim_reverse(lat: float, lon: float) -> dict[str, Any]:
    params = {"format": "jsonv2", "lat": f"{lat:.7f}", "lon": f"{lon:.7f}", "zoom": "16", "addressdetails": "1"}
    payload = _get_json("https://nominatim.openstreetmap.org/reverse", params=params)
    label = str(payload.get("display_name", "")).strip() if isinstance(payload, dict) else ""
    return OnlineLead(
        provider="Nominatim",
        query_type="reverse_geocode",
        label=(label or "Unavailable")[:260],
        confidence=78 if label else 0,
        url="https://nominatim.openstreetmap.org/reverse?" + urlencode(params),
        coordinates=(float(lat), float(lon)),
        raw={k: payload.get(k) for k in ("place_id", "osm_type", "osm_id", "class", "type")} if isinstance(payload, dict) else {},
        limitations=["Online reverse geocode; validates map context, not device-origin GPS."],
    ).to_dict()


def overpass_nearby(lat: float, lon: float, *, radius_m: int = 750, tags: list[str] | None = None) -> list[dict[str, Any]]:
    wanted = tags or ["amenity", "tourism", "historic", "railway", "highway", "shop", "leisure"]
    tag_filters = "\n".join(f'  node(around:{int(radius_m)},{lat:.7f},{lon:.7f})["{tag}"];' for tag in wanted[:12])
    query = f"[out:json][timeout:12];(\\n{tag_filters}\\n);out center 25;"
    payload = _get_json("https://overpass-api.de/api/interpreter", params={"data": query}, timeout=16.0)
    leads: list[OnlineLead] = []
    for item in (payload.get("elements", []) if isinstance(payload, dict) else [])[:25]:
        tags_payload = item.get("tags", {}) if isinstance(item, dict) else {}
        name = str(tags_payload.get("name") or tags_payload.get("name:en") or tags_payload.get("amenity") or tags_payload.get("tourism") or "OSM feature").strip()
        ilat = item.get("lat") or (item.get("center") or {}).get("lat")
        ilon = item.get("lon") or (item.get("center") or {}).get("lon")
        try:
            coords = (float(ilat), float(ilon))
        except Exception:
            coords = None
        leads.append(OnlineLead(
            provider="Overpass/OSM",
            query_type="nearby_features",
            label=name[:180],
            confidence=60,
            coordinates=coords,
            raw={"id": item.get("id"), "type": item.get("type"), "tags": {k: tags_payload.get(k) for k in list(tags_payload)[:12]}},
            limitations=["Nearby public OSM feature; useful for clue matching, not proof by itself."],
        ))
    return [lead.to_dict() for lead in leads]


def wikidata_search(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    sparql = f"""
SELECT ?item ?itemLabel ?coord WHERE {{
  SERVICE wikibase:mwapi {{
    bd:serviceParam wikibase:endpoint "www.wikidata.org";
                    wikibase:api "EntitySearch";
                    mwapi:search "{query.replace('"', ' ')}";
                    mwapi:language "en".
    ?item wikibase:apiOutputItem mwapi:item.
  }}
  OPTIONAL {{ ?item wdt:P625 ?coord. }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,ar". }}
}}
LIMIT {max(1, min(limit, 20))}
""".strip()
    payload = _get_json("https://query.wikidata.org/sparql", params={"query": sparql, "format": "json"}, timeout=12.0)
    bindings = (((payload or {}).get("results") or {}).get("bindings") or []) if isinstance(payload, dict) else []
    leads: list[OnlineLead] = []
    for item in bindings:
        label = ((item.get("itemLabel") or {}).get("value") or query)
        coord = ((item.get("coord") or {}).get("value") or "")
        coords = None
        if coord.startswith("Point(") and coord.endswith(")"):
            try:
                lon_s, lat_s = coord[6:-1].split()
                coords = (float(lat_s), float(lon_s))
            except Exception:
                coords = None
        leads.append(OnlineLead(
            provider="Wikidata",
            query_type="entity_search",
            label=str(label)[:180],
            confidence=64,
            coordinates=coords,
            raw={"item": (item.get("item") or {}).get("value"), "coord": coord},
            limitations=["Knowledge-graph clue; verify against image/map evidence before reporting."],
        ))
    return [lead.to_dict() for lead in leads]


def mapillary_nearby_link(lat: float, lon: float) -> dict[str, Any]:
    token_present = bool(os.environ.get("GEOTRACE_MAPILLARY_TOKEN", "").strip())
    params = {"closeto": f"{lon:.7f},{lat:.7f}", "fields": "id,computed_geometry,captured_at"}
    return OnlineLead(
        provider="Mapillary",
        query_type="street_level_imagery_link",
        label="Mapillary nearby imagery lookup" + (" (token configured)" if token_present else " (token not configured)"),
        confidence=50 if token_present else 20,
        url="https://www.mapillary.com/app/?" + urlencode({"lat": f"{lat:.7f}", "lng": f"{lon:.7f}", "z": "17"}),
        coordinates=(float(lat), float(lon)),
        raw={"api_params": params, "token_configured": token_present},
        limitations=["Manual/approved visual verification step; do not upload sensitive evidence."],
    ).to_dict()
