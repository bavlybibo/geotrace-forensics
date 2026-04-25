from __future__ import annotations

"""Deep local reasoning layer for AI Guardian.

This layer sits after the detectors and planning modules.  It does not call any
external model.  It makes the existing local AI feel more analyst-like by
combining map, OCR, GPS, duplicate, privacy, and timeline signals into a
conservative reasoning posture for every evidence item.
"""

from collections import Counter, defaultdict
from typing import Dict, Iterable

from ..models import EvidenceRecord
from .features import has_hidden_content_signal, has_textual_location_lead
from .findings import BatchAIFinding


_UNKNOWN = {"", "Unknown", "Unavailable", "N/A", "None", "not evaluated"}


def _clean(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _non_empty(value: object) -> bool:
    return _clean(value) not in _UNKNOWN


def _safe_list(value: object) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [_clean(item) for item in value if _non_empty(item)]
    if _non_empty(value):
        return [_clean(value)]
    return []


def _unique(items: Iterable[str], limit: int = 10) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = _clean(item).strip(" -:|•·")
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
        if len(out) >= limit:
            break
    return out


def _location_label(record: EvidenceRecord) -> str:
    if record.has_gps:
        return _clean(record.gps_display) or "native GPS"
    if _non_empty(record.derived_geo_display):
        return _clean(record.derived_geo_display)
    for attr in ("candidate_area", "candidate_city"):
        value = getattr(record, attr, "Unavailable")
        if _non_empty(value):
            return _clean(value)
    for attr in ("landmarks_detected", "place_candidates", "visible_location_strings", "ocr_location_entities"):
        values = _safe_list(getattr(record, attr, []))
        if values:
            return values[0]
    return "Unavailable"


def _location_posture(record: EvidenceRecord) -> tuple[str, list[str], list[str]]:
    basis = _safe_list(getattr(record, "map_evidence_basis", []))
    map_conf = int(getattr(record, "map_intelligence_confidence", 0) or getattr(record, "map_confidence", 0) or 0)
    place = _location_label(record)
    reasons: list[str] = []
    actions: list[str] = []

    if record.has_gps and record.gps_confidence >= 80:
        posture = "Location posture: native GPS anchor — strongest location evidence, still compare against timeline and custody."
        reasons.append(f"Native GPS available at {record.gps_display} ({record.gps_confidence}%).")
        actions.append("Validate the GPS coordinate externally and compare it with adjacent timestamps for movement plausibility.")
    elif _non_empty(record.derived_geo_display):
        posture = "Location posture: derived coordinate lead — useful but not physical-device proof without app/device corroboration."
        reasons.append(f"Derived coordinate/context recovered at {record.derived_geo_display} ({record.derived_geo_confidence}%).")
        actions.append("Preserve source screenshot/share URL and verify whether it is a searched/displayed place or actual device location.")
    elif map_conf >= 65 and (has_textual_location_lead(record) or basis):
        posture = f"Location posture: strong displayed-place lead — {place}; treat as displayed/searched context until corroborated."
        reasons.append(f"Map/OCR confidence is {map_conf}% with basis: {', '.join(basis[:4]) if basis else 'visual/text context'}.")
        actions.append("Corroborate visible place labels with map URL, source-app history, native GPS, or an analyst verification note.")
    elif map_conf >= 45 or has_textual_location_lead(record):
        posture = "Location posture: weak-to-moderate location lead — useful for triage, not for final claims."
        reasons.append("Location context exists, but lacks a strong coordinate/native-source anchor.")
        actions.append("Run Deep OCR/manual review and mark each place candidate as verified or rejected in OSINT Workbench.")
    else:
        posture = "Location posture: no reliable location anchor — avoid location claims from this item alone."
        actions.append("Use source profile, timestamp, custody, and visual context as primary anchors.")

    if getattr(record, "filename_location_hints", []):
        reasons.append("Filename location hints exist but are intentionally kept below OCR/GPS/map evidence.")
    if basis == ["filename"]:
        actions.append("Do not promote filename-only location hints beyond weak triage leads.")
    if getattr(record, "route_overlay_detected", False) and not record.has_gps:
        reasons.append("Route overlay indicates a displayed route, not necessarily user movement.")
        actions.append("Confirm route start/end from source-app history before using it as movement evidence.")
    return posture, _unique(reasons, limit=5), _unique(actions, limit=5)


def _privacy_posture(record: EvidenceRecord) -> tuple[str, list[str]]:
    pivots = []
    if _safe_list(getattr(record, "visible_urls", [])) or _safe_list(getattr(record, "ocr_url_entities", [])):
        pivots.append("visible URLs")
    if _safe_list(getattr(record, "ocr_username_entities", [])):
        pivots.append("usernames/entities")
    if record.has_gps or _non_empty(record.derived_geo_display) or _safe_list(getattr(record, "place_candidates", [])):
        pivots.append("location pivots")
    if has_hidden_content_signal(record):
        pivots.append("hidden/appended content")
    if not pivots:
        return "Privacy posture: no obvious OSINT-sensitive pivot detected.", []
    return (
        "Privacy posture: sensitive OSINT pivot(s) present — " + ", ".join(pivots[:4]) + ".",
        [
            "Apply redaction/privacy review before shareable export.",
            "Keep raw URLs, usernames, coordinates, and hidden payload details out of external reports unless needed and authorised.",
        ],
    )


def _timeline_posture(record: EvidenceRecord) -> tuple[str, list[str]]:
    if record.timestamp_confidence >= 80:
        return (
            f"Timeline posture: strong time anchor from {record.timestamp_source} ({record.timestamp_confidence}%).",
            ["Compare this time anchor with neighbouring evidence and source-system logs."],
        )
    if record.timestamp_confidence > 0:
        return (
            f"Timeline posture: provisional time anchor from {record.timestamp_source} ({record.timestamp_confidence}%).",
            ["Do not finalize sequence until at least one independent time source corroborates it."],
        )
    return (
        "Timeline posture: no reliable time anchor recovered.",
        ["Recover creation/import/source-app time before using this item in the final timeline."],
    )


def _record_reasoning(record: EvidenceRecord) -> tuple[list[str], list[str], list[str]]:
    location_line, location_reasons, location_actions = _location_posture(record)
    privacy_line, privacy_actions = _privacy_posture(record)
    timeline_line, timeline_actions = _timeline_posture(record)
    reasoning = [location_line, timeline_line, privacy_line]
    if getattr(record, "osint_content_label", "Unclassified image content") not in {"", "Unclassified image content"}:
        reasoning.append(f"Content posture: {record.osint_content_label} ({record.osint_content_confidence}%).")
    if getattr(record, "osint_scene_label", "Unclassified") not in {"", "Unclassified"}:
        reasoning.append(f"Scene posture: {record.osint_scene_label} ({record.osint_scene_confidence}%).")
    if record.duplicate_group:
        reasoning.append(f"Relationship posture: duplicate group {record.duplicate_group}; compare peers before claiming originality.")
    if record.parser_status != "Valid" or record.signature_status == "Mismatch":
        reasoning.append("Integrity posture: parser/signature issue requires second-parser validation.")
    if has_hidden_content_signal(record):
        reasoning.append("Hidden-content posture: preserve carved/embedded artifacts separately and explain handling before reporting.")
    actions = _unique([*location_actions, *timeline_actions, *privacy_actions], limit=8)
    confidence_basis = _unique([*location_reasons, location_line, timeline_line, privacy_line], limit=10)
    return _unique(reasoning, limit=8), actions, confidence_basis


def _case_distribution(records: list[EvidenceRecord]) -> dict[str, Counter[str]]:
    distributions: dict[str, Counter[str]] = {
        "location": Counter(),
        "source": Counter(),
        "scene": Counter(),
    }
    for record in records:
        loc = _location_label(record)
        if loc != "Unavailable":
            distributions["location"][loc] += 1
        if _non_empty(record.source_type):
            distributions["source"][_clean(record.source_type)] += 1
        scene = _clean(getattr(record, "osint_content_label", "")) or _clean(getattr(record, "osint_scene_label", ""))
        if scene and scene not in {"Unclassified image content", "Unclassified"}:
            distributions["scene"][scene] += 1
    return distributions


def _attach_cross_case_context(records: list[EvidenceRecord], findings: Dict[str, BatchAIFinding]) -> None:
    distributions = _case_distribution(records)
    dominant_location = distributions["location"].most_common(1)[0][0] if distributions["location"] else "Unavailable"
    dominant_source = distributions["source"].most_common(1)[0][0] if distributions["source"] else "Unknown"

    duplicate_locations: dict[str, set[str]] = defaultdict(set)
    for record in records:
        if record.duplicate_group:
            loc = _location_label(record)
            if loc != "Unavailable":
                duplicate_locations[record.duplicate_group].add(loc.lower())

    for record in records:
        finding = findings.setdefault(record.evidence_id, BatchAIFinding())
        loc = _location_label(record)
        if dominant_location != "Unavailable" and loc != "Unavailable" and loc != dominant_location:
            finding.add_matrix_line(f"Case context: location differs from dominant visible/native location '{dominant_location}'.")
        if dominant_source != "Unknown" and _clean(record.source_type) and _clean(record.source_type) != dominant_source:
            finding.add_matrix_line(f"Case context: source type differs from dominant source profile '{dominant_source}'.")
        if record.duplicate_group and len(duplicate_locations.get(record.duplicate_group, set())) > 1:
            finding.add(
                flag="duplicate_location_context_mismatch",
                reason="Duplicate-group peers carry different location labels or anchors.",
                contributor="AI deep context reasoner",
                delta=6,
                confidence_delta=2,
                breakdown_detail="duplicate peer locations disagree; compare original/edit/export context",
            )
            finding.add_action("Review duplicate peers side-by-side and decide whether location context was edited, searched, or reused.")


def attach_deep_context_reasoning(records: Iterable[EvidenceRecord], findings: Dict[str, BatchAIFinding]) -> None:
    records_list = list(records)
    _attach_cross_case_context(records_list, findings)
    for record in records_list:
        finding = findings.setdefault(record.evidence_id, BatchAIFinding())
        reasoning, actions, basis = _record_reasoning(record)
        for line in reasoning:
            finding.add_matrix_line("AI reasoning: " + line)
            if line not in finding.breakdown:
                finding.breakdown.append("AI reasoning — " + line)
        for action in actions:
            finding.add_action(action)
        for line in basis:
            if line not in finding.confidence_basis:
                finding.confidence_basis.append(line)

        # Promote review priority for risky combinations, while staying conservative.
        if not record.has_gps and int(getattr(record, "map_intelligence_confidence", 0) or 0) >= 70:
            finding.add(
                flag="displayed_location_not_device_proof",
                reason="Strong map/OCR location context exists without native GPS; it must be framed as displayed/searched context.",
                contributor="AI deep context reasoner",
                delta=4,
                confidence_delta=1,
                breakdown_detail="strong displayed-place lead without native GPS anchor",
            )
        if (_safe_list(getattr(record, "visible_urls", [])) or _safe_list(getattr(record, "ocr_username_entities", []))) and not finding.privacy_audit.startswith("Privacy posture"):
            finding.add_matrix_line("AI reasoning: OSINT pivots require privacy-aware export handling.")
        if (record.timestamp_confidence == 0 and str(record.timestamp or "").strip() in {"", "Unknown", "Unavailable", "N/A"} and (record.has_gps or has_textual_location_lead(record) or int(getattr(record, "map_intelligence_confidence", 0) or 0) >= 45 or _non_empty(getattr(record, "derived_geo_display", "Unavailable")))):
            finding.add(
                flag="location_without_time_anchor",
                reason="Location context exists but no reliable timestamp anchor was recovered.",
                contributor="AI deep context reasoner",
                delta=5,
                confidence_delta=1,
                breakdown_detail="location lead needs independent timeline corroboration",
            )
        if has_hidden_content_signal(record) and (record.visible_text_excerpt or record.ocr_raw_text):
            finding.add_matrix_line("AI reasoning: visible and hidden text contexts should be separated in the final report.")
