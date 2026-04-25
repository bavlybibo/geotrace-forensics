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
from .planning import assign_priority_ranks, attach_plans
from .context_reasoner import attach_deep_context_reasoning


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
    attach_plans(records_list, findings)
    attach_deep_context_reasoning(records_list, findings)
    _attach_graph_and_readiness(records_list, findings)
    assign_priority_ranks(records_list, findings)
    for finding in findings.values():
        finding.finalize()
    return findings
