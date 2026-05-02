from __future__ import annotations

"""Map URL and coordinate parsers used by OSINT and Map Intelligence.

This parser is intentionally offline and non-invasive: it only parses text already
present in the evidence item or filename/context strings. It also de-duplicates URL
signals conservatively so a single Google Maps URL with coordinates does not produce
both a precise coordinate signal and a redundant generic provider signal.
"""

from dataclasses import asdict, dataclass
import re
from typing import Iterable
from urllib.parse import unquote


@dataclass(slots=True)
class MapURLSignal:
    provider: str
    raw: str
    coordinates: tuple[float, float] | None = None
    place_name: str = "Unavailable"
    zoom: str = "Unavailable"
    source: str = "visible_text"
    confidence: int = 0

    def to_dict(self) -> dict:
        row = asdict(self)
        if self.coordinates is not None:
            row["coordinates"] = [self.coordinates[0], self.coordinates[1]]
        return row


_URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>'\"()]+", re.IGNORECASE)
_GOOGLE_AT_RE = re.compile(r"@\s*(-?\d{1,2}\.\d{4,})\s*,\s*(-?\d{1,3}\.\d{4,})(?:\s*,\s*(\d+(?:\.\d+)?z))?", re.I)
_QUERY_COORD_RE = re.compile(r"(?:q|ll|center|query|destination|origin|daddr|saddr)\s*=\s*(-?\d{1,2}\.\d{4,})\s*(?:,|;|\+|\s)+\s*(-?\d{1,3}\.\d{4,})", re.I)
_OSM_MLAT_RE = re.compile(r"(?:mlat|lat)=\s*(-?\d{1,2}\.\d{4,}).{0,80}?(?:mlon|lon)=\s*(-?\d{1,3}\.\d{4,})", re.I)
_OSM_HASH_RE = re.compile(r"#map=\d+(?:\.\d+)?/(-?\d{1,2}\.\d{4,})/(-?\d{1,3}\.\d{4,})", re.I)
_GOOGLE_BANG_RE = re.compile(r"!3d(-?\d{1,2}\.\d{4,})!4d(-?\d{1,3}\.\d{4,})", re.I)
_LABELLED_COORD_RE = re.compile(r"(?:lat(?:itude)?|خط العرض)\s*[:=]\s*(-?\d{1,2}\.\d{4,}).{0,80}?(?:lon(?:gitude)?|lng|خط الطول)\s*[:=]\s*(-?\d{1,3}\.\d{4,})", re.I)
_PLAIN_COORD_RE = re.compile(r"\b(-?\d{1,2}\.\d{4,})\s*,\s*(-?\d{1,3}\.\d{4,})\b")
_GEO_RE = re.compile(r"\bgeo:\s*(-?\d{1,2}\.\d{4,})\s*,\s*(-?\d{1,3}\.\d{4,})", re.I)
_DMS_RE = re.compile(
    r"(?P<lat_deg>\d{1,2})[°\s]+(?P<lat_min>\d{1,2})['′\s]+(?P<lat_sec>\d{1,2}(?:\.\d+)?)?[\"″\s]*(?P<lat_hemi>[NS])\s+"
    r"(?P<lon_deg>\d{1,3})[°\s]+(?P<lon_min>\d{1,2})['′\s]+(?P<lon_sec>\d{1,2}(?:\.\d+)?)?[\"″\s]*(?P<lon_hemi>[EW])",
    re.I,
)
_PLUS_CODE_RE = re.compile(r"\b(?:[23456789CFGHJMPQRVWX]{4,8}\+[23456789CFGHJMPQRVWX]{2,3})(?:\s+[\w\u0600-\u06ff .'-]+)?\b", re.I)


def _provider(text: str) -> str:
    lower = text.lower()
    if "google.com/maps" in lower or "maps.app.goo.gl" in lower or "goo.gl/maps" in lower:
        return "Google Maps"
    if "maps.apple" in lower or "maps.apple.com" in lower:
        return "Apple Maps"
    if "openstreetmap.org" in lower or "osm.org" in lower:
        return "OpenStreetMap"
    if lower.startswith("geo:"):
        return "Geo URI"
    return "Map/coordinate text"


def _normalise_raw(text: str) -> str:
    return re.sub(r"\s+", " ", unquote(str(text or "")).strip().rstrip(".,;]")).lower()


def _to_float_pair(lat: str, lon: str) -> tuple[float, float] | None:
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except Exception:
        return None
    if -90 <= lat_f <= 90 and -180 <= lon_f <= 180:
        return lat_f, lon_f
    return None


def _dms_to_decimal(match: re.Match[str]) -> tuple[float, float] | None:
    def convert(prefix: str) -> float:
        deg = float(match.group(f"{prefix}_deg") or 0)
        minutes = float(match.group(f"{prefix}_min") or 0)
        seconds = float(match.group(f"{prefix}_sec") or 0)
        hemi = (match.group(f"{prefix}_hemi") or "").upper()
        value = deg + minutes / 60 + seconds / 3600
        if hemi in {"S", "W"}:
            value *= -1
        return value

    lat = convert("lat")
    lon = convert("lon")
    if -90 <= lat <= 90 and -180 <= lon <= 180:
        return round(lat, 7), round(lon, 7)
    return None


def extract_candidate_texts(text: str) -> list[str]:
    value = unquote(str(text or ""))
    candidates: list[str] = []
    seen: set[str] = set()
    for match in _URL_RE.finditer(value):
        candidate = match.group(0).rstrip(".,;]")
        key = _normalise_raw(candidate)
        if key and key not in seen:
            seen.add(key)
            candidates.append(candidate)
    raw_key = _normalise_raw(value)
    if value.strip() and raw_key not in seen:
        candidates.append(value)
    return candidates


def _place_from_url(decoded: str) -> str:
    place_match = re.search(r"/place/([^/?#]+)", decoded, re.I)
    if not place_match:
        return "Unavailable"
    return re.sub(r"[+_]+", " ", place_match.group(1)).strip() or "Unavailable"


def _append_coordinate_signal(out: list[MapURLSignal], seen: set[str], *, provider: str, raw: str, coords: tuple[float, float] | None, source: str, confidence: int, key_prefix: str, zoom: str = "Unavailable") -> bool:
    if not coords:
        return False
    key = f"coord:{key_prefix}:{provider}:{coords}:{raw[:180].lower()}"
    if key in seen:
        return False
    seen.add(key)
    out.append(MapURLSignal(provider, raw, coords, zoom=zoom, source=source, confidence=confidence))
    return True


def parse_map_url_signals(texts: Iterable[str], *, source: str = "visible_text", limit: int = 12) -> list[MapURLSignal]:
    out: list[MapURLSignal] = []
    seen: set[str] = set()

    for text in texts:
        for candidate in extract_candidate_texts(text):
            decoded = unquote(candidate).strip()
            if not decoded:
                continue

            provider = _provider(decoded)
            raw_key = _normalise_raw(decoded)
            candidate_has_precise_signal = False

            for match in _GOOGLE_AT_RE.finditer(decoded):
                coords = _to_float_pair(match.group(1), match.group(2))
                zoom = match.group(3) or "Unavailable"
                candidate_has_precise_signal |= _append_coordinate_signal(out, seen, provider=provider, raw=decoded, coords=coords, source=source, confidence=92, key_prefix="google-at", zoom=zoom)

            for match in _QUERY_COORD_RE.finditer(decoded):
                coords = _to_float_pair(match.group(1), match.group(2))
                candidate_has_precise_signal |= _append_coordinate_signal(out, seen, provider=provider, raw=decoded, coords=coords, source=source, confidence=88, key_prefix="query")

            for match in _GEO_RE.finditer(decoded):
                coords = _to_float_pair(match.group(1), match.group(2))
                candidate_has_precise_signal |= _append_coordinate_signal(out, seen, provider="Geo URI", raw=decoded, coords=coords, source=source, confidence=90, key_prefix="geo")

            for match in _OSM_MLAT_RE.finditer(decoded):
                coords = _to_float_pair(match.group(1), match.group(2))
                provider_for_osm = provider if provider != "Map/coordinate text" else "OpenStreetMap"
                candidate_has_precise_signal |= _append_coordinate_signal(out, seen, provider=provider_for_osm, raw=decoded, coords=coords, source=source, confidence=88, key_prefix="osm-mlat")

            for match in _OSM_HASH_RE.finditer(decoded):
                coords = _to_float_pair(match.group(1), match.group(2))
                provider_for_osm = provider if provider != "Map/coordinate text" else "OpenStreetMap"
                candidate_has_precise_signal |= _append_coordinate_signal(out, seen, provider=provider_for_osm, raw=decoded, coords=coords, source=source, confidence=87, key_prefix="osm-hash")

            for match in _GOOGLE_BANG_RE.finditer(decoded):
                coords = _to_float_pair(match.group(1), match.group(2))
                candidate_has_precise_signal |= _append_coordinate_signal(out, seen, provider="Google Maps", raw=decoded, coords=coords, source=source, confidence=90, key_prefix="google-bang")

            for match in _LABELLED_COORD_RE.finditer(decoded):
                coords = _to_float_pair(match.group(1), match.group(2))
                candidate_has_precise_signal |= _append_coordinate_signal(out, seen, provider="Visible labelled coordinate", raw=match.group(0), coords=coords, source=source, confidence=84, key_prefix="labelled")

            for match in _DMS_RE.finditer(decoded):
                coords = _dms_to_decimal(match)
                candidate_has_precise_signal |= _append_coordinate_signal(out, seen, provider="DMS coordinate text", raw=match.group(0), coords=coords, source=source, confidence=84, key_prefix="dms")

            for match in _PLAIN_COORD_RE.finditer(decoded):
                # A provider URL such as Google Maps @lat,lon is already captured
                # above. Do not emit a second generic/plain coordinate signal for
                # the same candidate URL. Plain-coordinate extraction still runs
                # for non-provider text and for candidates without a stronger
                # provider-specific coordinate pattern.
                if candidate_has_precise_signal and provider != "Map/coordinate text":
                    continue
                coords = _to_float_pair(match.group(1), match.group(2))
                provider_for_plain = provider if provider != "Map/coordinate text" else "Visible coordinate text"
                candidate_has_precise_signal |= _append_coordinate_signal(out, seen, provider=provider_for_plain, raw=match.group(0), coords=coords, source=source, confidence=86, key_prefix="plain")

            if provider != "Map/coordinate text":
                place = _place_from_url(decoded)
                if place != "Unavailable" or not candidate_has_precise_signal:
                    key = f"provider-url:{provider}:{place.lower()}:{raw_key[:180]}"
                    if key not in seen:
                        seen.add(key)
                        confidence = 72 if place == "Unavailable" else 82
                        out.append(MapURLSignal(provider, decoded, place_name=place, source=source, confidence=confidence))

            for match in _PLUS_CODE_RE.finditer(decoded):
                plus_code = match.group(0).strip()
                key = f"plus:{plus_code.lower()}"
                if key not in seen:
                    seen.add(key)
                    out.append(MapURLSignal("Plus Code", plus_code, place_name=plus_code, source=source, confidence=72))

            if len(out) >= limit:
                return out[:limit]

    return out[:limit]


def parse_first_coordinate(texts: Iterable[str]) -> tuple[float, float] | None:
    for signal in parse_map_url_signals(texts):
        if signal.coordinates is not None:
            return signal.coordinates
    for text in texts:
        for match in _PLAIN_COORD_RE.finditer(str(text or "")):
            coords = _to_float_pair(match.group(1), match.group(2))
            if coords:
                return coords
    return None
