from __future__ import annotations

from typing import Dict, Iterable

from ..models import EvidenceRecord
from .confidence import record_confidence_profile
from .detectors import (
    detect_duplicate_context_conflicts,
    detect_impossible_travel,
    detect_location_outliers,
    detect_source_timeline_anomalies,
    metadata_authenticity_review,
)
from .evidence_graph import (
    build_evidence_graph,
    courtroom_readiness,
    explain_contradictions,
    next_best_action,
    privacy_audit_status,
)
from .evidence_strength import assess_map_strength, assess_record_strength
from .findings import BatchAIFinding
from .evidence_fusion import attach_fused_claims_to_finding
from .planning import assign_priority_ranks, attach_plans


def _attach_strength_and_confidence(records: list[EvidenceRecord], findings: Dict[str, BatchAIFinding]) -> None:
    for record in records:
        finding = findings[record.evidence_id]
        strength = assess_record_strength(record)
        confidence, confidence_basis = record_confidence_profile(record)
        map_strength = assess_map_strength(record)
        finding.evidence_strength = strength.label.value
        finding.evidence_strength_score = strength.score
        finding.evidence_strength_reasons = list(strength.reasons)
        finding.evidence_strength_limitations = list(strength.limitations)
        finding.confidence_basis = confidence_basis
        if strength.limitations:
            finding.add_action("Corroborate evidence strength limitation: " + strength.limitations[0])
        if map_strength.reasons and map_strength.label.value in {"lead", "weak_signal"}:
            finding.add_action("Treat map/location signals as investigative leads until independently corroborated.")
        # Keep confidence_delta as a small additive signal, not the raw confidence score.
        finding.confidence_delta = max(finding.confidence_delta, min(12, max(0, confidence - 65) // 3))



def _attach_deep_image_methodology(records: list[EvidenceRecord], findings: Dict[str, BatchAIFinding]) -> None:
    """Promote image-detail methodology into the batch AI plan.

    This keeps the AI layer explainable: high-priority visual regions become
    actions, limitations become guardrails, and scene descriptors become
    corroboration context.
    """
    for record in records:
        finding = findings[record.evidence_id]
        confidence = int(getattr(record, "image_detail_confidence", 0) or 0)
        regions = list(getattr(record, "image_attention_regions", []) or [])
        descriptors = list(getattr(record, "image_scene_descriptors", []) or [])
        methodology = list(getattr(record, "image_analysis_methodology", []) or [])
        quality = list(getattr(record, "image_quality_flags", []) or [])
        metrics = dict(getattr(record, "image_detail_metrics", {}) or {})
        strategy = str(metrics.get("analysis_strategy", "") or "")
        quality_gate = str(metrics.get("quality_gate", "") or "")
        corroboration_target = str(metrics.get("corroboration_target", "") or "")
        if confidence <= 0 and not regions and not descriptors:
            continue
        if strategy:
            finding.add_matrix_line(
                "Image reasoning strategy: "
                + strategy
                + (
                    f" | OCR {metrics.get('ocr_priority_score', 0)} | Map {metrics.get('map_review_priority_score', 0)} | Geo {metrics.get('geolocation_potential_score', 0)}"
                    if metrics
                    else ""
                )
            )
            finding.add_action("Apply image reasoning strategy: " + strategy + (f" — {corroboration_target}" if corroboration_target else ""))
        if quality_gate and quality_gate != "ready_for_triage":
            finding.add_action("Pass image quality gate before final claims: " + quality_gate)
        if descriptors:
            finding.add_matrix_line("Image scene descriptors: " + " | ".join(str(x) for x in descriptors[:3]))
        if regions and isinstance(regions[0], dict):
            top = regions[0]
            reasons = ", ".join(str(x) for x in (top.get("reasons", []) or [])[:3]) or "high visual attention score"
            finding.add_action(
                f"Prioritize crop/OCR review for {top.get('region', 'top image region')} "
                f"box={top.get('original_box', 'unknown')} because {reasons}."
            )
            finding.add_matrix_line(
                f"Deep image attention: {top.get('region', '?')} score {top.get('attention_score', 0)} — {reasons}"
            )
        if methodology:
            finding.add_action("Follow image methodology: " + str(methodology[min(2, len(methodology) - 1)]))
        if quality:
            finding.add_action("Resolve image-quality limitation before final wording: " + str(quality[0]))
        if confidence >= 72 and regions:
            finding.confidence_delta = max(finding.confidence_delta, 3)

def _attach_image_threat_decision(records: list[EvidenceRecord], findings: Dict[str, BatchAIFinding]) -> None:
    """Promote the per-image danger decision into the AI review queue."""
    for record in records:
        finding = findings[record.evidence_id]
        label = str(getattr(record, "image_risk_label", "SAFE") or "SAFE").upper()
        score = int(getattr(record, "image_risk_score", 0) or 0)
        summary = str(getattr(record, "image_risk_summary", "") or "")
        primary = str(getattr(record, "image_risk_primary_reason", "") or "")
        zones = list(getattr(record, "image_risk_danger_zones", []) or [])
        matrix = list(getattr(record, "image_risk_evidence_matrix", []) or [])
        actions = list(getattr(record, "image_risk_next_actions", []) or [])
        payload = getattr(record, "image_risk_verdict_payload", {}) or {}
        grade = str(getattr(record, "image_risk_evidence_grade", payload.get("evidence_grade", "D")) or "D")
        priority = str(getattr(record, "image_risk_review_priority", payload.get("review_priority", "P3")) or "P3")
        temperature = str(getattr(record, "image_risk_risk_temperature", payload.get("risk_temperature", "COOL")) or "COOL")
        export_policy = str(getattr(record, "image_risk_export_policy", payload.get("export_policy", "")) or "")
        missing = list(getattr(record, "image_risk_missing_evidence", payload.get("missing_evidence", [])) or [])
        calibration = list(getattr(record, "image_risk_calibration_notes", payload.get("calibration_notes", [])) or [])
        if priority in {"P0", "P1"} or grade in {"A", "B", "C"}:
            finding.add_matrix_line(f"Image AI triage: grade {grade} | priority {priority} | temperature {temperature}")
            if export_policy:
                finding.add_action("Apply Image AI export policy: " + export_policy)
            if missing:
                finding.add_matrix_line("Image AI missing evidence: " + " | ".join(str(x) for x in missing[:3]))
            if calibration:
                finding.add_matrix_line("Image AI calibration: " + " | ".join(str(x) for x in calibration[:4]))
        if label in {"HIGH", "CRITICAL"} and bool(getattr(record, "image_risk_is_dangerous", False)):
            finding.add(
                flag="image_threat_dangerous",
                reason=primary or summary or "Image Threat AI marked this file dangerous.",
                contributor="Image Threat AI",
                delta=22 if label == "CRITICAL" else 16,
                confidence_delta=5,
                breakdown_detail=f"image threat verdict {label} ({score}%)",
            )
        elif label == "MEDIUM":
            finding.add_matrix_line(f"Image Threat AI: {label} ({score}%) — {primary or summary}")
            finding.add_action("Review Image Threat AI medium-risk indicators before export or public sharing.")
        elif label == "LOW":
            finding.add_matrix_line(f"Image Threat AI: LOW ({score}%) — privacy/weak-signal review only.")
        if zones and zones != ["none"]:
            finding.add_matrix_line("Image danger zones: " + " | ".join(str(x) for x in zones[:4]))
        if matrix:
            finding.add_matrix_line("Image risk evidence: " + " | ".join(str(x) for x in matrix[:3]))
        for action in actions[:2]:
            finding.add_action(str(action))


def _attach_evidence_fusion(records: list[EvidenceRecord], findings: Dict[str, BatchAIFinding]) -> None:
    for record in records:
        attach_fused_claims_to_finding(record, findings[record.evidence_id])


def _attach_graph_and_readiness(records: list[EvidenceRecord], findings: Dict[str, BatchAIFinding]) -> None:
    edges = build_evidence_graph(records)
    contradictions = explain_contradictions(records)
    privacy = privacy_audit_status(records, privacy_level="redacted_text")
    for edge in edges:
        for eid in (edge.source_id, edge.target_id):
            if eid in findings:
                findings[eid].add_graph_line(
                    f"{edge.source_id} ↔ {edge.target_id} [{edge.relation}, {edge.weight}%]: {edge.reason}"
                )
                findings[eid].add_link(
                    f"Graph relation with {edge.target_id if eid == edge.source_id else edge.source_id}: {edge.relation}"
                )
    for explanation in contradictions:
        touched = [r.evidence_id for r in records if r.evidence_id in explanation]
        for eid in touched:
            f = findings[eid]
            f.add_contradiction(explanation)
            if "ai_contradiction_explainer" not in f.flags:
                f.add(
                    flag="ai_contradiction_explainer",
                    reason="AI contradiction explainer found a timeline/location pair that requires manual verification.",
                    contributor="AI contradiction explainer",
                    delta=6,
                    confidence_delta=2,
                    breakdown_detail="human-readable contradiction explanation",
                )
    for record in records:
        ready, reasons = courtroom_readiness(record)
        label = "Yes" if ready else "No"
        f = findings[record.evidence_id]
        f.courtroom_readiness = "Ready for courtroom: " + label + "\nReason:\n- " + "\n- ".join(reasons)
        f.next_best_action = next_best_action(record)
        f.privacy_audit = privacy["summary"]
        f.add_matrix_line(f.courtroom_readiness.replace("\n", " | "))
        f.add_action(f.next_best_action)


def run_ai_batch_assessment(records: Iterable[EvidenceRecord]) -> Dict[str, BatchAIFinding]:
    records_list = list(records)
    findings = {r.evidence_id: BatchAIFinding() for r in records_list}
    detect_location_outliers(records_list, findings)
    detect_impossible_travel(records_list, findings)
    detect_duplicate_context_conflicts(records_list, findings)
    detect_source_timeline_anomalies(records_list, findings)
    for record in records_list:
        metadata_authenticity_review(record, findings)
    _attach_strength_and_confidence(records_list, findings)
    _attach_deep_image_methodology(records_list, findings)
    _attach_image_threat_decision(records_list, findings)
    _attach_evidence_fusion(records_list, findings)
    attach_plans(records_list, findings)
    _attach_graph_and_readiness(records_list, findings)
    assign_priority_ranks(records_list, findings)
    for finding in findings.values():
        finding.finalize()
    return findings
