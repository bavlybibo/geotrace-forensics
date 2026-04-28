from __future__ import annotations

"""Offline map/geocoder helpers for GeoTrace.

This module is deliberately offline and deterministic. It is not a replacement for a
real geocoder; it gives analysts a bigger local seed index, route-label extraction,
label clustering, confidence-radius estimates, and source-comparison text so map
screenshots are not treated as magic location proof.
"""

from dataclasses import asdict, dataclass
import re
from typing import Any, Iterable


@dataclass(slots=True)
class OfflinePlaceHit:
    name: str
    level: str
    country: str
    city: str
    latitude: float | None
    longitude: float | None
    confidence: int
    source: str
    aliases_hit: list[str]
    limitations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


GLOBAL_PLACE_INDEX: list[dict[str, Any]] = [
    {"name": "Cairo Tower", "level": "poi", "country": "Egypt", "city": "Cairo", "lat": 30.0459, "lon": 31.2243, "aliases": ["cairo tower", "برج القاهرة", "برج القاهره"]},
    {"name": "Tahrir Square", "level": "area", "country": "Egypt", "city": "Cairo", "lat": 30.0444, "lon": 31.2357, "aliases": ["tahrir square", "tahrir", "ميدان التحرير", "التحرير"]},
    {"name": "Pyramids of Giza", "level": "poi", "country": "Egypt", "city": "Giza", "lat": 29.9792, "lon": 31.1342, "aliases": ["pyramids of giza", "giza pyramids", "pyramids", "الأهرامات", "الاهرامات"]},
    {"name": "Stanley Bridge", "level": "poi", "country": "Egypt", "city": "Alexandria", "lat": 31.2242, "lon": 29.9668, "aliases": ["stanley bridge", "stanley", "كوبرى ستانلى", "كوبري ستانلي"]},
    {"name": "Bibliotheca Alexandrina", "level": "poi", "country": "Egypt", "city": "Alexandria", "lat": 31.2089, "lon": 29.9092, "aliases": ["bibliotheca alexandrina", "alexandria library", "مكتبة الإسكندرية", "مكتبه الاسكندريه"]},
    {"name": "Eiffel Tower", "level": "poi", "country": "France", "city": "Paris", "lat": 48.8584, "lon": 2.2945, "aliases": ["eiffel tower", "tour eiffel"]},
    {"name": "Louvre Museum", "level": "poi", "country": "France", "city": "Paris", "lat": 48.8606, "lon": 2.3376, "aliases": ["louvre", "louvre museum", "musée du louvre"]},
    {"name": "Colosseum", "level": "poi", "country": "Italy", "city": "Rome", "lat": 41.8902, "lon": 12.4922, "aliases": ["colosseum", "colosseo"]},
    {"name": "Burj Khalifa", "level": "poi", "country": "United Arab Emirates", "city": "Dubai", "lat": 25.1972, "lon": 55.2744, "aliases": ["burj khalifa", "برج خليفة", "برج خليفه"]},
    {"name": "Dubai Mall", "level": "poi", "country": "United Arab Emirates", "city": "Dubai", "lat": 25.1975, "lon": 55.2796, "aliases": ["dubai mall", "دبي مول"]},
    {"name": "Doha Corniche", "level": "area", "country": "Qatar", "city": "Doha", "lat": 25.2948, "lon": 51.5392, "aliases": ["doha corniche", "corniche doha", "كورنيش الدوحة"]},
    {"name": "Aspire Tower", "level": "poi", "country": "Qatar", "city": "Doha", "lat": 25.2625, "lon": 51.4489, "aliases": ["aspire tower", "torch doha", "the torch"]},
    {"name": "Statue of Liberty", "level": "poi", "country": "United States", "city": "New York", "lat": 40.6892, "lon": -74.0445, "aliases": ["statue of liberty", "liberty island"]},
    {"name": "Times Square", "level": "area", "country": "United States", "city": "New York", "lat": 40.7580, "lon": -73.9855, "aliases": ["times square"]},
    {"name": "Golden Gate Bridge", "level": "poi", "country": "United States", "city": "San Francisco", "lat": 37.8199, "lon": -122.4783, "aliases": ["golden gate bridge"]},
    {"name": "Christ the Redeemer", "level": "poi", "country": "Brazil", "city": "Rio de Janeiro", "lat": -22.9519, "lon": -43.2105, "aliases": ["christ the redeemer", "cristo redentor"]},
    {"name": "Sugarloaf Mountain", "level": "poi", "country": "Brazil", "city": "Rio de Janeiro", "lat": -22.9492, "lon": -43.1545, "aliases": ["sugarloaf mountain", "pão de açúcar", "pao de acucar"]},
    {"name": "Tokyo Tower", "level": "poi", "country": "Japan", "city": "Tokyo", "lat": 35.6586, "lon": 139.7454, "aliases": ["tokyo tower", "東京タワー"]},
    {"name": "Shibuya Crossing", "level": "area", "country": "Japan", "city": "Tokyo", "lat": 35.6595, "lon": 139.7005, "aliases": ["shibuya crossing", "shibuya scramble"]},
    {"name": "Sydney Opera House", "level": "poi", "country": "Australia", "city": "Sydney", "lat": -33.8568, "lon": 151.2153, "aliases": ["sydney opera house"]},
    {"name": "Big Ben", "level": "poi", "country": "United Kingdom", "city": "London", "lat": 51.5007, "lon": -0.1246, "aliases": ["big ben", "elizabeth tower"]},
    {"name": "Tower Bridge", "level": "poi", "country": "United Kingdom", "city": "London", "lat": 51.5055, "lon": -0.0754, "aliases": ["tower bridge"]},
    {"name": "Hagia Sophia", "level": "poi", "country": "Türkiye", "city": "Istanbul", "lat": 41.0086, "lon": 28.9802, "aliases": ["hagia sophia", "ayasofya", "آيا صوفيا"]},
    {"name": "Blue Mosque", "level": "poi", "country": "Türkiye", "city": "Istanbul", "lat": 41.0054, "lon": 28.9768, "aliases": ["blue mosque", "sultan ahmed mosque", "جامع السلطان أحمد"]},
    {"name": "Petra Treasury", "level": "poi", "country": "Jordan", "city": "Petra", "lat": 30.3285, "lon": 35.4444, "aliases": ["petra treasury", "al khazneh", "الخزنة"]},
    {"name": "Sheikh Zayed Grand Mosque", "level": "poi", "country": "United Arab Emirates", "city": "Abu Dhabi", "lat": 24.4128, "lon": 54.4749, "aliases": ["sheikh zayed grand mosque", "جامع الشيخ زايد"]},
]

_ROUTE_PATTERNS = [
    re.compile(r"\bfrom\s+([A-Za-z\u0600-\u06ff][A-Za-z0-9\u0600-\u06ff'’ .-]{2,60}?)\s+(?:to|→|->)\s+([A-Za-z\u0600-\u06ff][A-Za-z0-9\u0600-\u06ff'’ .-]{2,60}?)(?=$|,|\||•)", re.I),
    re.compile(r"^([A-Za-z\u0600-\u06ff][A-Za-z0-9\u0600-\u06ff'’ .-]{2,60}?)\s+(?:to|→|->)\s+([A-Za-z\u0600-\u06ff][A-Za-z0-9\u0600-\u06ff'’ .-]{2,60}?)(?=$|,|\||•)", re.I),
    re.compile(r"(?:من)\s+(.{3,60}?)\s+(?:إلى|الى)\s+(.{3,60}?)(?:\n|$|,|\||•)", re.I),
]


def _norm(text: str) -> str:
    text = str(text or "").replace("\u200f", " ").replace("\u200e", " ")
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي").replace("ة", "ه")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _good_label(text: str) -> bool:
    clean = _norm(text).strip(" -:|•·")
    if len(clean) < 3:
        return False
    if re.fullmatch(r"[\d\s:.,/-]+", clean):
        return False
    if clean.lower() in {"google maps", "maps", "route", "directions", "screenshot", "image"}:
        return False
    return any(ch.isalpha() or "\u0600" <= ch <= "\u06ff" for ch in clean)


def _route_endpoint_cleanup(value: str, *, side: str) -> str:
    cleaned = _norm(value).strip(" -:|•·")
    # Remove OCR/UI prefixes that can bleed into route phrases.
    for token in ("google maps route from ", "route from ", "directions from ", "from "):
        if cleaned.lower().startswith(token):
            cleaned = cleaned[len(token):].strip(" -:|•·")
    # If OCR concatenated two route lines, trim at the repeated connector.
    cleaned = re.split(r"\b(?:from|route|directions)\b", cleaned, maxsplit=1, flags=re.I)[0].strip(" -:|•·")
    if side == "start" and re.search(r"\s+(?:to|→|->)\s+", cleaned, re.I):
        cleaned = re.split(r"\s+(?:to|→|->)\s+", cleaned, maxsplit=1, flags=re.I)[0].strip(" -:|•·")
    if side == "end" and re.search(r"\s+(?:to|→|->)\s+", cleaned, re.I):
        cleaned = re.split(r"\s+(?:to|→|->)\s+", cleaned, maxsplit=1, flags=re.I)[-1].strip(" -:|•·")
    return cleaned


def match_offline_places(texts: Iterable[str], *, limit: int = 8) -> list[dict[str, Any]]:
    blob = _norm("\n".join(str(x or "") for x in texts)).lower()
    hits: list[OfflinePlaceHit] = []
    for item in GLOBAL_PLACE_INDEX:
        aliases = [str(a) for a in item.get("aliases", [])]
        alias_hits = [alias for alias in aliases if _norm(alias).lower() in blob]
        if not alias_hits:
            continue
        score = min(94, 68 + min(16, len(alias_hits) * 8))
        hits.append(
            OfflinePlaceHit(
                name=str(item.get("name", "Unknown")),
                level=str(item.get("level", "poi")),
                country=str(item.get("country", "Unknown")),
                city=str(item.get("city", "Unknown")),
                latitude=float(item["lat"]) if item.get("lat") is not None else None,
                longitude=float(item["lon"]) if item.get("lon") is not None else None,
                confidence=score,
                source="offline-global-seed-geocoder",
                aliases_hit=alias_hits[:4],
                limitations=["Text match only; verify visually/source-side before final reporting."],
            )
        )
    hits.sort(key=lambda hit: (-hit.confidence, hit.name.lower()))
    return [hit.to_dict() for hit in hits[:limit]]


def cluster_place_labels(labels: Iterable[str], *, limit: int = 8) -> list[dict[str, Any]]:
    clusters: dict[str, dict[str, Any]] = {}
    for raw in labels:
        label = _norm(str(raw or "")).strip(" -:|•·")
        if not _good_label(label):
            continue
        key_tokens = re.findall(r"[\w\u0600-\u06ff]{3,}", _norm(label).lower())
        key = " ".join(key_tokens[:3]) or _norm(label).lower()
        bucket = clusters.setdefault(key, {"label": label, "members": [], "count": 0, "confidence": 0})
        bucket["members"].append(label)
        bucket["count"] += 1
        bucket["confidence"] = min(92, 48 + int(bucket["count"]) * 12 + min(20, len(label) // 3))
    out = list(clusters.values())
    out.sort(key=lambda row: (-int(row["confidence"]), -int(row["count"]), str(row["label"]).lower()))
    return out[:limit]


def extract_route_endpoints(texts: Iterable[str]) -> tuple[str, str, list[str]]:
    candidates = [re.sub(r"\s+", " ", str(x or "")).strip() for x in texts if str(x or "").strip()]
    # Prefer short OCR lines over the concatenated full OCR blob so "from A to B" is
    # not accidentally extended by a second repeated line.
    candidates.sort(key=len)
    for candidate in candidates:
        for pattern in _ROUTE_PATTERNS:
            match = pattern.search(candidate)
            if not match:
                continue
            start = _route_endpoint_cleanup(match.group(1), side="start")
            end = _route_endpoint_cleanup(match.group(2), side="end")
            if _good_label(start) and _good_label(end) and start.lower() != end.lower():
                return start[:90], end[:90], [f"route endpoints parsed with pattern: {pattern.pattern[:24]}..."]
    return "", "", []


def estimate_confidence_radius_meters(*, has_native_gps: bool, has_coordinates: bool, has_map_url: bool, place_level: str, confidence: int) -> int:
    if has_native_gps:
        return 25 if confidence >= 90 else 75
    if has_coordinates:
        return 50 if confidence >= 85 else 150
    if has_map_url:
        return 250 if confidence >= 75 else 750
    if place_level == "poi":
        return 350 if confidence >= 80 else 900
    if place_level == "area":
        return 1500 if confidence >= 70 else 3000
    if place_level == "city":
        return 10000 if confidence >= 65 else 25000
    return 50000


def build_source_comparison(*, native_gps: str = "", derived_geo: str = "", map_url: str = "", ocr_places: Iterable[str] = (), landmarks: Iterable[str] = (), offline_hits: Iterable[dict[str, Any]] = ()) -> list[str]:
    rows: list[str] = []
    rows.append(f"Native GPS: {native_gps or 'missing'}")
    rows.append(f"Derived coordinates/map URL: {derived_geo or map_url or 'missing'}")
    places = [str(x) for x in ocr_places if str(x).strip()]
    rows.append("OCR/place labels: " + (", ".join(places[:5]) if places else "missing"))
    lm = [str(x) for x in landmarks if str(x).strip()]
    rows.append("Known landmark dictionary: " + (", ".join(lm[:5]) if lm else "missing"))
    seed = [str(hit.get("name", "")) for hit in offline_hits if isinstance(hit, dict)]
    rows.append("Offline geocoder seed: " + (", ".join(seed[:5]) if seed else "missing"))
    hard = bool(native_gps or derived_geo or map_url)
    rows.append("Decision: " + ("hard coordinate source available; use labels as corroboration." if hard else "no hard coordinate source; keep result as a lead until manual verification."))
    return rows


def build_interactive_map_payload(*, latitude: float | None, longitude: float | None, label: str, radius_m: int, source: str) -> dict[str, Any]:
    if latitude is None or longitude is None:
        return {"available": False, "reason": "No coordinate candidate available for embedded map preview."}
    return {
        "available": True,
        "latitude": latitude,
        "longitude": longitude,
        "label": label,
        "radius_m": radius_m,
        "source": source,
        "privacy": "Offline payload only. Render locally; do not upload case evidence to third-party maps without approval.",
    }
