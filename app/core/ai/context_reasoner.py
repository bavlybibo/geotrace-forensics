from __future__ import annotations

"""Conservative deep-context reasoning for forensic AI findings.

This module adds small, deterministic checks that keep location wording honest:
native GPS, displayed map text, OCR/place hints, filenames, and duplicate peers
are not the same evidentiary class.  The checks only annotate findings; they do
not mutate evidence records or promote weak leads into proof.
"""

from collections import defaultdict
import re
from typing import Dict, Iterable, List

from ..models import EvidenceRecord
from .findings import BatchAIFinding

_UNAVAILABLE = {"", "unknown", "unavailable", "n/a", "none", "null", "no native gps recovered.", "no stable map/location anchor recovered."}
_WEAK_TIME_SOURCES = {"", "unknown", "unavailable", "filename", "filename timestamp", "filesystem", "filesystem mtime", "file system", "manual"}


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _norm(value: object) -> str:
    text = _clean(value).casefold()
    text = re.sub(r"[^\w\u0600-\u06ff.+,-]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _usable(value: object) -> bool:
    return _norm(value) not in _UNAVAILABLE


def _list_values(value: object, *, limit: int = 8) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, dict):
        items = [value.get("name"), value.get("label"), value.get("place_name"), value.get("display")]
    else:
        try:
            items = list(value)  # type: ignore[arg-type]
        except Exception:
            items = [value]
    out: list[str] = []
    for item in items[:limit]:
        if isinstance(item, dict):
            for key in ("name", "label", "place_name", "display"):
                if _usable(item.get(key)):
                    out.append(_clean(item.get(key)))
                    break
        elif _usable(item):
            out.append(_clean(item))
    return out[:limit]


def _has_native_gps(record: EvidenceRecord) -> bool:
    return bool(getattr(record, "has_gps", False)) or (
        _usable(getattr(record, "gps_display", "")) and int(getattr(record, "gps_confidence", 0) or 0) >= 70
    )


def _displayed_location_labels(record: EvidenceRecord) -> list[str]:
    """Return non-native location labels shown/inferred from context."""
    values: list[str] = []
    for attr in (
        "derived_geo_display",
        "possible_place",
        "candidate_city",
        "candidate_area",
        "map_anchor_status",
    ):
        value = getattr(record, attr, "")
        if _usable(value):
            values.append(_clean(value))
    for attr in (
        "place_candidates",
        "landmarks_detected",
        "filename_location_hints",
        "ocr_location_entities",
        "ocr_map_labels",
    ):
        values.extend(_list_values(getattr(record, attr, []), limit=6))
    for hit in _list_values(getattr(record, "map_offline_geocoder_hits", []), limit=6):
        values.append(hit)
    # De-duplicate while preserving order and avoid long noisy strings.
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = _norm(value)
        if key and key not in seen:
            seen.add(key)
            out.append(value[:140])
    return out[:10]


def _has_displayed_location_without_native_gps(record: EvidenceRecord) -> bool:
    if _has_native_gps(record):
        return False
    if int(getattr(record, "derived_geo_confidence", 0) or 0) > 0 and _usable(getattr(record, "derived_geo_display", "")):
        return True
    if int(getattr(record, "map_intelligence_confidence", 0) or 0) > 0 and _displayed_location_labels(record):
        return True
    basis = {str(x).casefold() for x in (getattr(record, "map_evidence_basis", []) or [])}
    if basis.intersection({"ocr/text", "url", "map-url", "known-place-dictionary", "region-aware-ocr", "filename"}) and _displayed_location_labels(record):
        return True
    return bool(_displayed_location_labels(record))


def _has_any_location_anchor(record: EvidenceRecord) -> bool:
    return _has_native_gps(record) or _has_displayed_location_without_native_gps(record)


def _has_reliable_time_anchor(record: EvidenceRecord) -> bool:
    timestamp = _clean(getattr(record, "timestamp", ""))
    if not timestamp or timestamp.casefold() in {"unknown", "unavailable", "n/a", "none"}:
        return False
    source = _norm(getattr(record, "timestamp_source", ""))
    if source in _WEAK_TIME_SOURCES or "filename" in source:
        return False
    return True


def _location_signature(record: EvidenceRecord) -> str:
    """Build a conservative duplicate-comparison signature."""
    if _has_native_gps(record):
        if getattr(record, "gps_latitude", None) is not None and getattr(record, "gps_longitude", None) is not None:
            try:
                return f"gps:{float(getattr(record, 'gps_latitude')):.4f},{float(getattr(record, 'gps_longitude')):.4f}"
            except Exception:
                pass
        if _usable(getattr(record, "gps_display", "")):
            return "gps:" + _norm(getattr(record, "gps_display", ""))
    labels = _displayed_location_labels(record)
    if labels:
        return "displayed:" + _norm(labels[0])
    return ""


def apply_deep_context_reasoning(records: Iterable[EvidenceRecord], findings: Dict[str, BatchAIFinding]) -> None:
    """Attach conservative deep-context flags to existing AI findings."""
    records_list = list(records)

    for record in records_list:
        finding = findings.setdefault(record.evidence_id, BatchAIFinding())
        displayed_labels = _displayed_location_labels(record)
        if _has_displayed_location_without_native_gps(record):
            label_preview = ", ".join(displayed_labels[:3]) or "displayed/derived map context"
            finding.add(
                flag="displayed_location_not_device_proof",
                reason=(
                    "A displayed/derived location lead exists without native GPS metadata; "
                    f"treat it as a lead, not device-location proof ({label_preview})."
                ),
                contributor="AI deep context reasoner",
                delta=5,
                confidence_delta=1,
                breakdown_detail="displayed location context without native GPS proof",
            )
            finding.add_action("Separate native GPS evidence from displayed map/OCR/filename location leads in the report wording.")

        if _has_any_location_anchor(record) and not _has_reliable_time_anchor(record):
            finding.add(
                flag="location_without_time_anchor",
                reason="Location context is present, but no reliable non-filename time anchor was recovered.",
                contributor="AI deep context reasoner",
                delta=5,
                confidence_delta=1,
                breakdown_detail="location context without reliable capture/display time anchor",
            )
            finding.add_action("Corroborate the location lead with a reliable timestamp before using it in a timeline claim.")

    groups: dict[str, list[EvidenceRecord]] = defaultdict(list)
    for record in records_list:
        group = _clean(getattr(record, "duplicate_group", ""))
        if group:
            groups[group].append(record)

    for group_id, group_records in groups.items():
        signatures = { _location_signature(record) for record in group_records }
        signatures.discard("")
        if len(signatures) < 2:
            continue
        peer_ids = ", ".join(_clean(getattr(record, "evidence_id", "evidence")) for record in group_records[:6])
        for record in group_records:
            if not _location_signature(record):
                continue
            finding = findings.setdefault(record.evidence_id, BatchAIFinding())
            finding.add(
                flag="duplicate_location_context_mismatch",
                reason="Duplicate/near-duplicate items carry conflicting location context and need manual reconciliation.",
                contributor="AI deep context reasoner",
                delta=8,
                confidence_delta=2,
                breakdown_detail=f"duplicate group {group_id} has {len(signatures)} distinct location signatures",
                case_link=f"Duplicate location context group {group_id}: {peer_ids}",
            )
            finding.add_action("Compare duplicate peers side by side and keep only corroborated location claims in the final narrative.")


def attach_deep_context_reasoning(
    records: EvidenceRecord | Iterable[EvidenceRecord],
    findings: Dict[str, BatchAIFinding] | BatchAIFinding | None = None,
) -> Dict[str, BatchAIFinding]:
    """Compatibility wrapper used by older tests/extensions.

    Historically the AI engine exposed an ``attach_*`` function.  Keep that
    public behavior while delegating to the current deterministic
    implementation.  The wrapper accepts either a record iterable with a
    findings dict, a single record with a single finding, or records without
    findings (in which case findings are created and returned).
    """
    if isinstance(records, EvidenceRecord):
        records_list = [records]
    else:
        records_list = list(records)

    if findings is None:
        findings_map: Dict[str, BatchAIFinding] = {r.evidence_id: BatchAIFinding() for r in records_list}
    elif isinstance(findings, BatchAIFinding):
        if len(records_list) != 1:
            raise ValueError("A single BatchAIFinding can only be attached to one EvidenceRecord.")
        findings_map = {records_list[0].evidence_id: findings}
    else:
        findings_map = findings

    apply_deep_context_reasoning(records_list, findings_map)
    return findings_map


# Compatibility aliases for older tests/extensions.
run_deep_context_reasoning = apply_deep_context_reasoning
reason_about_deep_context = apply_deep_context_reasoning

__all__ = [
    "apply_deep_context_reasoning",
    "attach_deep_context_reasoning",
    "run_deep_context_reasoning",
    "reason_about_deep_context",
]
