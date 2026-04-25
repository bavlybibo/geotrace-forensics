from __future__ import annotations

from typing import Iterable

from ..models import EvidenceRecord
from .evidence_strength import EvidenceStrength, assess_record_strength


def mini_case_narrative(records: Iterable[EvidenceRecord]) -> str:
    """Generate a compact deterministic case narrative for analyst review."""
    items = list(records)
    if not items:
        return "No evidence has been analyzed yet."
    high = sum(1 for r in items if r.risk_level in {"High", "Critical"})
    map_items = [r for r in items if getattr(r, "map_intelligence_confidence", 0) > 0]
    ocr_items = [r for r in items if getattr(r, "ocr_confidence", 0) > 0 or getattr(r, "ocr_note", "") != "OCR not attempted."]
    content_items = [r for r in items if getattr(r, "osint_content_confidence", 0) > 0]
    strength = {r.evidence_id: assess_record_strength(r) for r in items}
    proof_like = sum(1 for assessment in strength.values() if assessment.label in {EvidenceStrength.PROOF, EvidenceStrength.STRONG_INDICATOR})
    lead_like = sum(1 for assessment in strength.values() if assessment.label == EvidenceStrength.LEAD)
    strongest = max(
        items,
        key=lambda r: (
            strength[r.evidence_id].score,
            r.suspicion_score,
            r.map_intelligence_confidence,
            r.ocr_confidence,
            r.evidence_id,
        ),
    )
    strongest_strength = strength[strongest.evidence_id]
    return (
        f"Case Narrator: {len(items)} evidence item(s) reviewed; {high} high-risk item(s); "
        f"{proof_like} proof/strong-indicator item(s), {lead_like} investigative lead(s). "
        f"Strongest current item is {strongest.evidence_id}: strength {strongest_strength.label.value} "
        f"({strongest_strength.score}%), risk {strongest.risk_level}, score {strongest.suspicion_score}, "
        f"map confidence {strongest.map_intelligence_confidence}%, OCR confidence {strongest.ocr_confidence}%. "
        f"Map intelligence appears in {len(map_items)} item(s); OSINT content profiling appears in {len(content_items)} item(s); OCR/context extraction appears in {len(ocr_items)} item(s). "
        "Treat OCR/map-derived places as leads until corroborated with acquisition logs, source-app data, native GPS, or manual review."
    )
