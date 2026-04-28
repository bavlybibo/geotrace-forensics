from __future__ import annotations

"""Deterministic offline location estimator.

This layer sits above the lower-level OSINT/map modules and answers a simple question:
"What is the best location read GeoTrace can safely give for this image right now?"

It does **not** claim magical geolocation. Instead it merges native GPS, visible map
coordinates, ranked place candidates, OCR place strings, landmarks, and regional hints
into a single conservative estimate with clear source hierarchy and limitations.
"""

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(slots=True)
class LocationEstimate:
    best_location: str = "Unavailable"
    confidence: int = 0
    scope: str = "no_signal"  # exact_coordinates / poi / area / city / country / context_only / no_signal
    source_tier: str = "no_signal"  # native_gps / displayed_coordinate / ranked_candidate / regional_hint / visual_context / no_signal
    summary: str = "No stable location estimate was recovered yet."
    supporting_signals: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    alternate_candidates: list[str] = field(default_factory=list)


_STABLE_SCOPE_ORDER = {
    "exact_coordinates": 0,
    "poi": 1,
    "area": 2,
    "city": 3,
    "country": 4,
    "context_only": 5,
    "no_signal": 9,
}


def _clean(value: Any, fallback: str = "") -> str:
    text = " ".join(str(value or "").split()).strip(" -:|•·,.;")
    if not text or text.lower() in {"unknown", "unavailable", "none", "n/a"}:
        return fallback
    return text


def _unique(values: Iterable[str], limit: int = 8) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = _clean(raw)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _country_name(profile: str) -> tuple[str, int]:
    text = _clean(profile)
    if not text or text == "Unknown":
        return "", 0
    if text.endswith("%)") and "(" in text:
        name, _, tail = text.rpartition("(")
        try:
            score = int(tail.replace("%)", "").strip())
        except Exception:
            score = 0
        return _clean(name), score
    return text, 0


def _scope_from_level(level: str) -> str:
    level = _clean(level).lower()
    if level in {"coordinates", "coordinate"}:
        return "exact_coordinates"
    if level in {"poi", "landmark", "map-url-place"}:
        return "poi"
    if level == "area":
        return "area"
    if level == "city":
        return "city"
    if level in {"country", "region"}:
        return "country"
    if level in {"visual_context", "filename_hint"}:
        return "context_only"
    if level:
        return "poi"
    return "no_signal"


def _candidate_sort_key(row: dict[str, Any]) -> tuple[int, int, int, str]:
    strength_order = {"proof": 0, "lead": 1, "weak_signal": 2, "no_signal": 3}
    scope = _scope_from_level(str(row.get("level", "")))
    return (
        strength_order.get(str(row.get("evidence_strength", "weak_signal")), 5),
        _STABLE_SCOPE_ORDER.get(scope, 9),
        -int(row.get("confidence", 0) or 0),
        _clean(row.get("name", "zzzz")).lower(),
    )


def _candidate_rows(record: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in getattr(record, "geo_candidates", []) or []:
        if isinstance(raw, dict):
            rows.append(raw)
    if rows:
        rows = [row for row in rows if str(row.get("status", "needs_review")) != "rejected"]
        rows.sort(key=_candidate_sort_key)
        return rows

    # Fallback when the structured OSINT layer has not run yet.
    for label in getattr(record, "place_candidate_rankings", []) or []:
        parts = [part.strip() for part in str(label or "").split("—")]
        if not parts:
            continue
        name = _clean(parts[0])
        if not name:
            continue
        score = 0
        if len(parts) > 1:
            try:
                score = int(parts[1].replace("%", "").strip())
            except Exception:
                score = 0
        category = parts[2] if len(parts) > 2 else "candidate"
        rows.append(
            {
                "level": category.split(":", 1)[0].strip(),
                "name": name,
                "confidence": score,
                "evidence_strength": "lead" if score >= 55 else "weak_signal",
                "basis": ["place-ranking"],
                "limitations": ["Offline ranked candidate — manual validation required."],
                "status": "needs_review",
            }
        )
    rows.sort(key=_candidate_sort_key)
    return rows


def _support_signal_count(record: Any, candidate_name: str) -> int:
    if not candidate_name:
        return 0
    needle = candidate_name.lower()
    buckets = [
        getattr(record, "ocr_map_labels", []) or [],
        getattr(record, "visible_location_strings", []) or [],
        getattr(record, "ocr_location_entities", []) or [],
        getattr(record, "place_candidates", []) or [],
        getattr(record, "landmarks_detected", []) or [],
        [getattr(record, "candidate_city", "")],
        [getattr(record, "candidate_area", "")],
        getattr(record, "possible_geo_clues", []) or [],
    ]
    count = 0
    for bucket in buckets:
        joined = " | ".join(_clean(item) for item in bucket if _clean(item))
        if joined and needle in joined.lower():
            count += 1
    country_name, _ = _country_name(getattr(record, "ctf_country_region_profile", "Unknown"))
    if country_name and needle in country_name.lower():
        count += 1
    return count


def _context_only_estimate(record: Any) -> LocationEstimate:
    signals: list[str] = []
    if getattr(record, "map_app_detected", "Unknown") not in {"Unknown", "Unavailable", "N/A", ""}:
        signals.append(f"App context: {record.map_app_detected}")
    if getattr(record, "route_overlay_detected", False):
        signals.append(f"Route/navigation overlay detected ({int(getattr(record, 'route_confidence', 0) or 0)}%)")
    if getattr(record, "map_intelligence_confidence", 0):
        signals.append(f"Map intelligence confidence {int(getattr(record, 'map_intelligence_confidence', 0) or 0)}%")
    if getattr(record, "location_solvability_label", ""):
        signals.append(f"Geo solvability: {record.location_solvability_label}")

    return LocationEstimate(
        best_location=_clean(getattr(record, "possible_place", ""), "Unavailable"),
        confidence=min(52, max(12, int(getattr(record, "map_intelligence_confidence", 0) or 0))),
        scope="context_only",
        source_tier="visual_context",
        summary=(
            "Location-aware image context was detected, but GeoTrace does not yet have a stable place name or coordinate. "
            "Treat the current result as a map/location context lead only."
        ),
        supporting_signals=_unique(signals, limit=6),
        limitations=[
            "Visual map/screenshot context shows location intent but does not identify a verified place on its own.",
        ],
        next_actions=[
            "Run deep OCR / map review and inspect visible labels, URLs, or coordinates.",
            "Corroborate with source-app history or the original share link before reporting a location.",
        ],
    )


def estimate_location(record: Any) -> LocationEstimate:
    # 1) Native GPS always wins.
    gps_display = _clean(getattr(record, "gps_display", "Unavailable"))
    gps_conf = int(getattr(record, "gps_confidence", 0) or 0)
    if getattr(record, "has_gps", False) and gps_display:
        supporting = _unique(
            [
                f"Native GPS metadata recovered ({max(90, gps_conf)}%)",
                _clean(getattr(record, "gps_source", "GPS metadata"), "GPS metadata"),
                _clean(getattr(record, "gps_verification", "")),
            ],
            limit=6,
        )
        return LocationEstimate(
            best_location=gps_display,
            confidence=max(92, gps_conf),
            scope="exact_coordinates",
            source_tier="native_gps",
            summary=(
                f"Best location estimate: {gps_display} ({max(92, gps_conf)}% confidence). "
                "This estimate is anchored by native GPS metadata and is the strongest location source in the record."
            ),
            supporting_signals=supporting,
            limitations=[
                "Native GPS is strong, but custody, parser integrity, and timestamp context should still be validated.",
            ],
            next_actions=[
                "Verify the coordinate against source acquisition notes and device timeline.",
            ],
            alternate_candidates=[],
        )

    # 2) Visible/derived coordinates are strong but reflect displayed context, not device presence.
    derived_display = _clean(getattr(record, "derived_geo_display", "Unavailable"))
    derived_conf = int(getattr(record, "derived_geo_confidence", 0) or 0)
    if derived_display:
        supporting = _unique(
            [
                f"Derived/visible coordinate recovered ({max(76, derived_conf)}%)",
                _clean(getattr(record, "derived_geo_source", "visible map/OCR"), "visible map/OCR"),
                _clean(getattr(record, "detected_map_context", "")),
            ],
            limit=6,
        )
        return LocationEstimate(
            best_location=derived_display,
            confidence=max(76, derived_conf),
            scope="exact_coordinates",
            source_tier="displayed_coordinate",
            summary=(
                f"Best location estimate: {derived_display} ({max(76, derived_conf)}% confidence). "
                "The value was recovered from visible screenshot/map content, so it represents displayed context and still needs corroboration before being treated as device location."
            ),
            supporting_signals=supporting,
            limitations=[
                "Displayed coordinates may show a searched/shared location rather than where the device was physically present.",
            ],
            next_actions=[
                "Validate the coordinate against source-app history, visible map labels, or a preserved share URL.",
            ],
            alternate_candidates=[],
        )

    # 3) Use ranked candidates from the OSINT/CTF layer.
    candidate_rows = _candidate_rows(record)
    if candidate_rows:
        top = candidate_rows[0]
        name = _clean(top.get("name", "Unavailable"), "Unavailable")
        scope = _scope_from_level(str(top.get("level", "")))
        base_conf = int(top.get("confidence", 0) or 0)
        evidence_strength = str(top.get("evidence_strength", "weak_signal"))
        support_hits = _support_signal_count(record, name)
        support_bonus = min(12, support_hits * 4)
        if evidence_strength == "proof":
            support_bonus = max(support_bonus, 8)
        confidence = max(18, min(95, base_conf + support_bonus))

        if scope == "country":
            source_tier = "regional_hint"
        else:
            source_tier = "ranked_candidate"

        support_lines = []
        for basis in top.get("basis", []) or []:
            basis_text = _clean(basis)
            if basis_text:
                support_lines.append(f"Basis: {basis_text}")
        if support_hits:
            support_lines.append(f"Independent support hits: {support_hits}")
        if getattr(record, "candidate_city", "Unavailable") not in {"Unavailable", "Unknown", "N/A", ""}:
            support_lines.append(f"Candidate city: {record.candidate_city}")
        if getattr(record, "candidate_area", "Unavailable") not in {"Unavailable", "Unknown", "N/A", ""}:
            support_lines.append(f"Candidate area: {record.candidate_area}")
        if getattr(record, "landmarks_detected", []):
            support_lines.append("Landmarks: " + ", ".join(_unique(getattr(record, "landmarks_detected", []), limit=3)))
        if getattr(record, "ocr_map_labels", []):
            support_lines.append("OCR map/place labels: " + ", ".join(_unique(getattr(record, "ocr_map_labels", []), limit=3)))
        country_name, country_score = _country_name(getattr(record, "ctf_country_region_profile", "Unknown"))
        if country_name:
            support_lines.append(f"Country/region classifier: {country_name} ({country_score or 'n/a'}%)")

        limitations = list(_unique(top.get("limitations", []) or [], limit=6))
        if scope != "exact_coordinates" and "displayed-place-not-device-location" not in " ".join(limitations).lower():
            limitations.append("Best match is a displayed/visible place lead, not proof of device presence, unless corroborated.")
        if evidence_strength == "weak_signal" and not any("weak" in item.lower() for item in limitations):
            limitations.append("Current evidence is still weak and should not be reported as a confirmed location yet.")

        next_actions = list(_unique(top.get("next_actions", []) or [], limit=6))
        if not next_actions:
            next_actions.append("Corroborate the top candidate with another independent signal before reporting it as fact.")
        if scope in {"poi", "area", "city"} and not getattr(record, "has_gps", False):
            next_actions.append("Use supporting OCR labels, map history, or source-app context to distinguish displayed place from device location.")

        alternates = [
            _clean(item.get("name", ""))
            for item in candidate_rows[1:6]
            if _clean(item.get("name", "")) and _clean(item.get("name", "")) != name
        ]

        summary = (
            f"Best location estimate: {name} ({confidence}% confidence; {scope.replace('_', ' ')}). "
            f"Source tier: {source_tier.replace('_', ' ')}. "
            "This estimate comes from GeoTrace's ranked OSINT/map signals and should be treated according to its corroboration strength."
        )
        return LocationEstimate(
            best_location=name,
            confidence=confidence,
            scope=scope,
            source_tier=source_tier,
            summary=summary,
            supporting_signals=_unique(support_lines, limit=8),
            limitations=_unique(limitations, limit=6),
            next_actions=_unique(next_actions, limit=6),
            alternate_candidates=_unique(alternates, limit=5),
        )

    # 4) Country/region-only fallback.
    country_name, country_score = _country_name(getattr(record, "ctf_country_region_profile", "Unknown"))
    if country_name:
        return LocationEstimate(
            best_location=country_name,
            confidence=max(40, min(78, country_score or 45)),
            scope="country",
            source_tier="regional_hint",
            summary=(
                f"Best location estimate: {country_name} ({max(40, min(78, country_score or 45))}% confidence; country/regional scope). "
                "GeoTrace could narrow the image to a country/region-level lead, but not to a stable city/place yet."
            ),
            supporting_signals=_unique([
                f"Country/region classifier: {country_name} ({country_score or 'n/a'}%)",
                _clean(getattr(record, "location_solvability_label", "")),
            ]),
            limitations=[
                "Country/region classification is broad and should not be reported as an exact location.",
            ],
            next_actions=[
                "Combine regional hint with OCR place names, landmarks, or map URLs to narrow to city/area.",
            ],
        )

    # 5) Visual map context only.
    map_context_present = bool(
        int(getattr(record, "map_intelligence_confidence", 0) or 0) >= 35
        or bool(getattr(record, "route_overlay_detected", False))
        or str(getattr(record, "osint_scene_label", "")).startswith("Map")
    )
    if map_context_present:
        return _context_only_estimate(record)

    return LocationEstimate(
        best_location="Unavailable",
        confidence=0,
        scope="no_signal",
        source_tier="no_signal",
        summary="No stable location estimate was recovered from metadata, OCR, map context, or offline OSINT signals.",
        supporting_signals=[],
        limitations=["No strong native, textual, or map-derived location signal is available in the current evidence item."],
        next_actions=["Use OCR, source metadata, or additional corroborating evidence before attempting any location claim."],
        alternate_candidates=[],
    )
