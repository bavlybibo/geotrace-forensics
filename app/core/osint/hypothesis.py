from __future__ import annotations

"""Build structured OSINT hypotheses from record and map signals."""

from typing import Any, Iterable

from .gazetteer import classify_known_places, unique
from .map_url_parser import MapURLSignal
from .models import CorroborationItem, OSINTHypothesis


def _value(record: Any, name: str, default: Any = None) -> Any:
    return getattr(record, name, default)


def _safe_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item or "").strip()]
    if value:
        return [str(value)]
    return []


def _strength_from_basis(*, has_gps: bool, confidence: int, basis: Iterable[str]) -> str:
    basis_set = {str(item) for item in basis}
    if has_gps and confidence >= 80:
        return "proof"
    if confidence >= 65 and basis_set.intersection({"ocr/text", "url", "map-url", "known-place-dictionary", "derived-coordinate"}):
        return "lead"
    if confidence > 0 or basis_set:
        return "weak_signal"
    return "no_signal"


def build_location_hypotheses(record: Any, map_signals: Iterable[MapURLSignal] = ()) -> list[OSINTHypothesis]:
    hypotheses: list[OSINTHypothesis] = []
    has_gps = bool(_value(record, "has_gps", False))
    if has_gps:
        hypotheses.append(
            OSINTHypothesis(
                title="Native GPS location anchor",
                claim=f"Native GPS places the evidence at {_value(record, 'gps_display', 'Unavailable')}.",
                strength="proof" if int(_value(record, "gps_confidence", 0) or 0) >= 80 else "lead",
                confidence=int(_value(record, "gps_confidence", 0) or 0),
                basis=["native-gps", str(_value(record, "gps_source", "GPS metadata"))],
                limitations=["Still validate acquisition chain, timestamp, and coordinate parser output."],
                next_actions=["Compare GPS timestamp/source with device timeline and custody notes."],
                source="metadata",
            )
        )

    derived_display = str(_value(record, "derived_geo_display", "Unavailable") or "Unavailable")
    if derived_display != "Unavailable":
        hypotheses.append(
            OSINTHypothesis(
                title="Screenshot-derived coordinate lead",
                claim=f"Visible text/map context suggests coordinates at {derived_display}.",
                strength="lead",
                confidence=int(_value(record, "derived_geo_confidence", 0) or 0),
                basis=["derived-coordinate", str(_value(record, "derived_geo_source", "visible map/OCR"))],
                limitations=["This indicates a displayed/searched place, not necessarily device physical location."],
                next_actions=["Corroborate with source-app URL, browser history, or native device location logs."],
                source="visible-context",
            )
        )

    for signal in map_signals:
        claim_target = signal.place_name if signal.place_name != "Unavailable" else "map/coordinate context"
        if signal.coordinates:
            claim_target = f"{signal.coordinates[0]:.6f}, {signal.coordinates[1]:.6f}"
        hypotheses.append(
            OSINTHypothesis(
                title=f"{signal.provider} map signal",
                claim=f"Visible/OCR context contains {signal.provider} signal for {claim_target}.",
                strength="lead" if signal.coordinates or signal.place_name != "Unavailable" else "weak_signal",
                confidence=signal.confidence,
                basis=["map-url", signal.source, signal.provider],
                limitations=["Visible map URLs prove displayed context only unless tied to original app/device logs."],
                next_actions=["Preserve the raw URL/text and verify it manually in a controlled, authorised environment."],
                source="map-url-parser",
            )
        )

    map_conf = int(_value(record, "map_intelligence_confidence", 0) or _value(record, "map_confidence", 0) or 0)
    basis = _safe_list(_value(record, "map_evidence_basis", []))
    city = str(_value(record, "candidate_city", "Unavailable") or "Unavailable")
    area = str(_value(record, "candidate_area", "Unavailable") or "Unavailable")
    landmarks = _safe_list(_value(record, "landmarks_detected", []))
    places = _safe_list(_value(record, "place_candidates", []))
    visible_place_parts = unique([city if city != "Unavailable" else "", area if area != "Unavailable" else "", *landmarks[:3], *places[:3]], limit=6)
    if visible_place_parts:
        limitations = _safe_list(_value(record, "map_limitations", [])) or [
            "Map/OCR places are investigative leads unless corroborated by native GPS or source-app records."
        ]
        actions = _safe_list(_value(record, "map_recommended_actions", [])) or [
            "Review source screenshot/app context and capture a manual analyst note before external reporting."
        ]
        hypotheses.append(
            OSINTHypothesis(
                title="Visible place/location lead",
                claim="Visible map/OCR context suggests: " + ", ".join(visible_place_parts),
                strength=_strength_from_basis(has_gps=False, confidence=map_conf, basis=basis),
                confidence=map_conf,
                basis=basis or ["visual/ocr-context"],
                limitations=limitations,
                next_actions=actions,
                source="map-intelligence",
            )
        )

    route_detected = bool(_value(record, "route_overlay_detected", False))
    has_map_visual_basis = bool(basis) and map_conf >= 50
    if not visible_place_parts and has_map_visual_basis:
        visual_label = str(_value(record, "map_type", "map/navigation context") or "map/navigation context")
        hypotheses.append(
            OSINTHypothesis(
                title="Displayed map/navigation context",
                claim=("The evidence appears to show displayed map/navigation context (" + visual_label + ")" + (" with a visible route overlay." if route_detected else ".")),
                strength="weak_signal",
                confidence=max(35, min(88, map_conf)),
                basis=basis or ["visual-map-context"],
                limitations=["Visual map layout alone does not identify a real-world place or device location.", "Treat this as a triage lead until OCR labels, a map URL, native GPS, or source-app history corroborates it."],
                next_actions=["Run map_deep OCR or preserve the original map/share URL before making any location claim."],
                source="map-visual-intelligence",
            )
        )

    rankings = _safe_list(_value(record, "place_candidate_rankings", []))
    filename_hints = _safe_list(_value(record, "filename_location_hints", []))
    if filename_hints and not visible_place_parts and not map_signals and not has_gps:
        hypotheses.append(
            OSINTHypothesis(
                title="Filename-only location hint",
                claim="Filename suggests a possible location hint: " + ", ".join(filename_hints[:3]),
                strength="weak_signal",
                confidence=35,
                basis=["filename-only"],
                limitations=["Filename hints are not location evidence by themselves and must not outrank OCR/GPS/map URL evidence."],
                next_actions=["Use this only as a triage hint; look for OCR, map, GPS, or source-app corroboration."],
                source="filename-triage",
            )
        )

    if rankings:
        hypotheses.append(
            OSINTHypothesis(
                title="Ranked place candidates",
                claim="Most likely displayed-place candidates: " + " | ".join(rankings[:3]),
                strength="lead" if map_conf >= 65 else "weak_signal",
                confidence=max(35, min(92, map_conf)),
                basis=["place-ranking", *(basis[:4] if basis else ["visual/ocr-context"])],
                limitations=["Place ranking describes displayed/searched context, not physical device presence by itself."],
                next_actions=["Mark the candidate as verified/rejected in OSINT Workbench after manual corroboration."],
                source="place-ranking",
            )
        )

    text_blob = "\n".join(
        _safe_list(_value(record, "ocr_raw_text", ""))
        + _safe_list(_value(record, "visible_text_excerpt", ""))
        + _safe_list(_value(record, "visible_text_lines", []))
    )
    known = classify_known_places(text_blob)
    if known["city"] != "Unavailable" or known["area"] != "Unavailable" or known["landmarks"]:
        parts = unique([str(known["city"]), str(known["area"]), *[str(x) for x in known["landmarks"]]], limit=5)
        if parts:
            hypotheses.append(
                OSINTHypothesis(
                    title="Offline gazetteer place match",
                    claim="Offline gazetteer matched visible/context text to: " + ", ".join(parts),
                    strength="lead" if map_conf >= 50 else "weak_signal",
                    confidence=max(52, min(86, map_conf or 58)),
                    basis=["offline-gazetteer", "ocr/context"],
                    limitations=["Gazetteer matching can be affected by OCR noise and common place names."],
                    next_actions=["Validate the matched place manually and compare against any map URL or GPS anchor."],
                    source="offline-gazetteer",
                )
            )

    seen: set[tuple[str, str]] = set()
    out: list[OSINTHypothesis] = []
    for item in hypotheses:
        key = (item.title.lower(), item.claim.lower())
        if key in seen:
            continue
        seen.add(key)
        item.confidence = max(0, min(100, int(item.confidence or 0)))
        out.append(item)
        if len(out) >= 10:
            break
    return out


def build_corroboration_matrix(record: Any, hypotheses: Iterable[OSINTHypothesis]) -> list[CorroborationItem]:
    matrix: list[CorroborationItem] = []
    has_gps = bool(_value(record, "has_gps", False))
    has_url = bool(_safe_list(_value(record, "visible_urls", [])))
    has_ocr = bool(str(_value(record, "ocr_raw_text", "") or "").strip() or _safe_list(_value(record, "visible_text_lines", [])))
    custody_ok = bool(_value(record, "copy_verified", False) or _value(record, "integrity_status", "") == "Verified")
    for hyp in hypotheses:
        supporting = list(hyp.basis)
        missing: list[str] = []
        if "location" in hyp.title.lower() or "place" in hyp.title.lower() or "map" in hyp.title.lower():
            if not has_gps:
                missing.append("native-gps")
            if not has_url:
                missing.append("source/share-url")
            if not has_ocr:
                missing.append("stable-ocr-label")
        if not custody_ok:
            missing.append("verified-working-copy")
        status = "corroborated" if hyp.strength == "proof" and not missing else "strong_lead" if hyp.strength == "lead" and len(missing) <= 2 else "needs_corroboration"
        matrix.append(
            CorroborationItem(
                claim=hyp.claim,
                status=status,
                supporting_basis=supporting,
                missing_basis=unique(missing, limit=5),
                recommended_action=hyp.next_actions[0] if hyp.next_actions else "Corroborate this lead before reporting it as fact.",
            )
        )
    return matrix[:10]
