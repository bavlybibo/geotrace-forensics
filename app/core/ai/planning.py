from __future__ import annotations

"""Action planning and evidence-priority helpers for GeoTrace AI."""

from collections import Counter
from typing import Dict, Iterable, List

from ..models import EvidenceRecord
from .features import has_hidden_content_signal, has_textual_location_lead
from .findings import BatchAIFinding


def build_corroboration_plan(record: EvidenceRecord) -> List[str]:
    plan: List[str] = []
    if record.timestamp_confidence >= 80:
        plan.append("Corroborate the selected timestamp against source-system logs, chat/export metadata, upload history, or device logs.")
    elif record.timestamp_confidence > 0:
        plan.append("Treat the recovered timestamp as provisional and confirm it against at least one independent time source.")
    else:
        plan.append("Recover an independent time anchor before using this item in a final timeline.")

    if record.has_gps:
        plan.append("Verify native GPS with an external map and compare it with adjacent case items for travel plausibility.")
    elif record.derived_geo_confidence >= 45:
        plan.append("Treat derived map/place clues as leads and confirm them with browser history, source app records, or manual map review.")
    elif has_textual_location_lead(record):
        plan.append("Run deep OCR/manual review to convert visible place labels into a corroborated location hypothesis.")
    else:
        plan.append("Avoid location claims; use source profile, visual context, and custody trail instead.")

    if record.signature_status == "Mismatch" or record.parser_status != "Valid":
        plan.append("Validate container structure with a second parser before relying on extracted metadata.")
    if record.duplicate_group:
        plan.append("Compare duplicate-group peers side by side to determine whether the item is original, edited, reused, or context-shifted.")
    if has_hidden_content_signal(record):
        plan.append("Review hidden/appended-content findings in a safe viewer and preserve carved artifacts separately.")
    if record.visible_text_excerpt or record.ocr_raw_text:
        plan.append("Preserve OCR/entity evidence as context, but redact it from shareable reports unless disclosure is approved.")
    return plan[:6]


def build_corroboration_matrix(record: EvidenceRecord) -> List[str]:
    rows: List[str] = []
    rows.append(f"Time: {record.timestamp_source} / {record.timestamp_confidence}% — {'strong' if record.timestamp_confidence >= 80 else 'needs external confirmation'}.")
    if record.has_gps:
        rows.append(f"Location: native GPS / {record.gps_confidence}% — verify map context and movement sequence.")
    elif record.derived_geo_confidence >= 45:
        rows.append(f"Location: derived geo / {record.derived_geo_confidence}% — treat as a lead, not proof.")
    elif has_textual_location_lead(record):
        rows.append("Location: OCR/place label lead — convert to a checked hypothesis before reporting.")
    else:
        rows.append("Location: no reliable anchor — do not make a location claim from this item alone.")
    rows.append(f"Integrity: {record.integrity_status or 'Pending'} — {record.parser_status}/{record.signature_status}.")
    if record.duplicate_group:
        rows.append(f"Relationship: duplicate group {record.duplicate_group} — compare peer context before assigning originality.")
    if has_hidden_content_signal(record):
        rows.append("Hidden content: signal present — preserve safely and explain before courtroom use.")
    if record.ai_flags:
        rows.append("AI posture: batch anomaly flag present — analyst confirmation required.")
    return rows[:8]


def attach_plans(records: Iterable[EvidenceRecord], findings: Dict[str, BatchAIFinding]) -> None:
    for record in records:
        finding = findings.setdefault(record.evidence_id, BatchAIFinding())
        for action in build_corroboration_plan(record):
            finding.add_action(action)
            detail = f"AI plan — {action}"
            if detail not in finding.breakdown:
                finding.breakdown.append(detail)
        for row in build_corroboration_matrix(record):
            finding.add_matrix_line(row)
        if not finding.flags:
            first = finding.action_plan[0] if finding.action_plan else "manual analyst review."
            finding.summary = "AI batch assessment completed; no cross-evidence anomaly was identified. Suggested first step: " + first


def assign_priority_ranks(records: List[EvidenceRecord], findings: Dict[str, BatchAIFinding]) -> None:
    def key(record: EvidenceRecord) -> tuple[int, int, int, str]:
        finding = findings.get(record.evidence_id, BatchAIFinding())
        flag_weight = len(finding.flags) * 10
        hidden_weight = 8 if has_hidden_content_signal(record) else 0
        parser_weight = 6 if record.parser_status != "Valid" or record.signature_status == "Mismatch" else 0
        return (finding.score_delta + flag_weight + hidden_weight + parser_weight, record.suspicion_score, record.confidence_score, record.evidence_id)

    ordered = sorted(records, key=key, reverse=True)
    for rank, record in enumerate(ordered, start=1):
        finding = findings.setdefault(record.evidence_id, BatchAIFinding())
        finding.priority_rank = rank
        if rank <= 3:
            finding.add_matrix_line(f"Priority rank: #{rank} in this case by AI/anomaly/context signals.")


def case_level_summary(records: Iterable[EvidenceRecord]) -> str:
    records_list = list(records)
    if not records_list:
        return "No evidence has been analyzed yet."
    sources = Counter(record.source_type for record in records_list).most_common(2)
    flagged = sum(1 for record in records_list if record.ai_flags)
    gps = sum(1 for record in records_list if record.has_gps)
    derived = sum(1 for record in records_list if record.derived_geo_display != "Unavailable" or has_textual_location_lead(record))
    source_text = ", ".join(f"{name}: {count}" for name, count in sources) or "Unknown"
    return f"Local AI case view: {len(records_list)} item(s), {flagged} AI-flagged, {gps} native GPS anchor(s), {derived} derived/text location lead(s). Dominant sources: {source_text}."
