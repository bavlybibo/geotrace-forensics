from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..models import EvidenceRecord


@dataclass(frozen=True)
class ConfidenceSignal:
    name: str
    weight: int
    reason: str


def clamp_score(value: int, *, floor: int = 0, ceiling: int = 100) -> int:
    return max(floor, min(ceiling, int(value)))


def calculate_confidence(signals: Iterable[ConfidenceSignal], *, base: int = 0) -> tuple[int, list[str]]:
    total = base
    basis: list[str] = []
    for signal in signals:
        total += max(0, int(signal.weight))
        basis.append(f"{signal.name}: +{max(0, int(signal.weight))} — {signal.reason}")
    return clamp_score(total), basis[:12]


def confidence_signals_for_record(record: EvidenceRecord) -> list[ConfidenceSignal]:
    signals: list[ConfidenceSignal] = []
    if record.integrity_status == "Verified":
        signals.append(ConfidenceSignal("integrity_verified", 22, "source and working-copy hashes were verified"))
    elif record.integrity_status == "Partial":
        signals.append(ConfidenceSignal("integrity_partial", 12, "partial integrity information is available"))
    if record.parser_status == "Valid" and record.signature_status != "Mismatch":
        signals.append(ConfidenceSignal("parser_valid", 14, "media parser accepted the file and no extension/signature mismatch was detected"))
    if record.timestamp_confidence >= 80:
        signals.append(ConfidenceSignal("strong_time_anchor", 18, "strong timestamp anchor recovered"))
    elif record.timestamp_confidence > 0:
        signals.append(ConfidenceSignal("weak_time_anchor", 8, "some timestamp context was recovered"))
    if record.has_gps and record.gps_confidence >= 80:
        signals.append(ConfidenceSignal("native_gps", 18, "native GPS metadata recovered with high confidence"))
    elif record.derived_geo_confidence > 0:
        signals.append(ConfidenceSignal("derived_geo", 8, "derived screenshot/location clue recovered"))
    if getattr(record, "map_intelligence_confidence", 0) >= 70:
        signals.append(ConfidenceSignal("map_intelligence", 10, "map/navigation intelligence produced a high-confidence lead"))
    if record.ocr_confidence >= 70:
        signals.append(ConfidenceSignal("ocr_context", 8, "OCR recovered high-confidence visible context"))
    if record.osint_scene_confidence >= 70:
        signals.append(ConfidenceSignal("scene_classifier", 6, "OSINT scene classifier produced a stable content label"))
    return signals


def record_confidence_profile(record: EvidenceRecord) -> tuple[int, list[str]]:
    return calculate_confidence(confidence_signals_for_record(record), base=8)
