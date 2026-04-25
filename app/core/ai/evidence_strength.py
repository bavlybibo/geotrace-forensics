from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ..models import EvidenceRecord


class EvidenceStrength(StrEnum):
    PROOF = "proof"
    STRONG_INDICATOR = "strong_indicator"
    LEAD = "lead"
    WEAK_SIGNAL = "weak_signal"
    NO_SIGNAL = "no_signal"


@dataclass(frozen=True)
class StrengthAssessment:
    label: EvidenceStrength = EvidenceStrength.NO_SIGNAL
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    @property
    def human_label(self) -> str:
        return self.label.value


def assess_record_strength(record: EvidenceRecord) -> StrengthAssessment:
    reasons: list[str] = []
    limitations: list[str] = []
    score = 0

    if record.integrity_status == "Verified":
        score += 24
        reasons.append("working copy integrity is verified")
    else:
        limitations.append("integrity chain should be verified before relying on this item")

    if record.parser_status == "Valid" and record.signature_status != "Mismatch":
        score += 14
        reasons.append("container parsed successfully without extension/signature conflict")
    else:
        limitations.append("file structure/signature requires secondary validation")

    if record.timestamp_confidence >= 80:
        score += 20
        reasons.append("strong timestamp anchor recovered")
    elif record.timestamp_confidence > 0:
        score += 8
        reasons.append("weak timestamp context recovered")
        limitations.append("timestamp is not strong enough for final timeline without corroboration")
    else:
        limitations.append("no strong timestamp anchor recovered")

    if record.has_gps and record.gps_confidence >= 80:
        score += 24
        reasons.append("native GPS metadata recovered")
    elif record.has_gps:
        score += 16
        reasons.append("native GPS exists but confidence is limited")
        limitations.append("GPS confidence should be manually checked")
    elif record.derived_geo_confidence > 0:
        score += 8
        reasons.append("screenshot/browser-derived location clue recovered")
        limitations.append("derived geolocation is a lead, not proof")
    elif record.ocr_map_labels or record.possible_geo_clues or getattr(record, "map_intelligence_confidence", 0) > 0:
        score += 5
        reasons.append("OCR/map intelligence produced a possible location lead")
        limitations.append("OCR/map clues are investigative leads only")

    if record.ocr_confidence >= 70:
        score += 6
        reasons.append("OCR produced readable context")

    score = max(0, min(100, score))
    if score >= 78 and record.integrity_status == "Verified" and (record.has_gps or record.timestamp_confidence >= 80):
        label = EvidenceStrength.PROOF
    elif score >= 55:
        label = EvidenceStrength.STRONG_INDICATOR
    elif score >= 20:
        label = EvidenceStrength.LEAD
    elif score > 0:
        label = EvidenceStrength.WEAK_SIGNAL
    else:
        label = EvidenceStrength.NO_SIGNAL

    if label == EvidenceStrength.PROOF and limitations:
        # Keep forensic language conservative: even strong items can have caveats.
        label = EvidenceStrength.STRONG_INDICATOR

    return StrengthAssessment(label=label, score=score, reasons=reasons[:8], limitations=limitations[:8])


def assess_map_strength(record: EvidenceRecord) -> StrengthAssessment:
    reasons: list[str] = []
    limitations: list[str] = []
    score = 0
    if record.has_gps and record.gps_confidence >= 80:
        return StrengthAssessment(EvidenceStrength.PROOF, 86, ["native GPS recovered"], ["verify acquisition source and timezone separately"])
    if record.derived_geo_confidence >= 65:
        score = max(score, 52)
        reasons.append("derived geolocation coordinates recovered from visible/map context")
        limitations.append("derived coordinates require manual/source-app corroboration")
    if getattr(record, "map_intelligence_confidence", 0) >= 70:
        score = max(score, 45)
        reasons.append("high-confidence map/navigation screenshot detection")
        limitations.append("map screenshot detection is a lead, not native location proof")
    if record.ocr_map_labels or record.possible_geo_clues or record.place_candidates:
        score = max(score, 32)
        reasons.append("visible place/map labels recovered")
        limitations.append("OCR labels can be misread or refer to a searched place rather than actual device location")
    if "filename" in getattr(record, "map_evidence_basis", []) and len(getattr(record, "map_evidence_basis", [])) == 1:
        score = min(score, 38)
        limitations.append("map/location hint is filename-only")
    if score >= 70:
        label = EvidenceStrength.STRONG_INDICATOR
    elif score >= 30:
        label = EvidenceStrength.LEAD
    elif score > 0:
        label = EvidenceStrength.WEAK_SIGNAL
    else:
        label = EvidenceStrength.NO_SIGNAL
    return StrengthAssessment(label, score, reasons[:6], limitations[:6])
