from __future__ import annotations

"""AI Guardian card payload builder."""

from dataclasses import asdict, dataclass
from typing import Iterable, Any

from .models import EvidenceRecord

@dataclass(slots=True)
class GuardianCard:
    title: str
    value: str
    note: str
    severity: str = 'info'

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def build_guardian_cards(records: Iterable[EvidenceRecord], readiness: dict[str, Any] | None = None) -> list[GuardianCard]:
    rows = list(records)
    readiness = readiness or {}
    high = sum(1 for r in rows if getattr(r, 'risk_level', 'Low') == 'High')
    gps = sum(1 for r in rows if getattr(r, 'has_gps', False))
    derived = sum(1 for r in rows if getattr(r, 'derived_geo_confidence', 0) > 0 or getattr(r, 'map_intelligence_confidence', 0) > 0)
    hidden = sum(1 for r in rows if getattr(r, 'digital_final_call', 'CLEAR') in {'ISOLATE', 'REVIEW'} or getattr(r, 'pixel_hidden_score', 0) >= 40 or getattr(r, 'hidden_code_indicators', []))
    verified = sum(1 for r in rows if getattr(r, 'integrity_status', '') == 'Verified')
    dangerous_images = sum(1 for r in rows if getattr(r, 'image_risk_is_dangerous', False))
    review_images = sum(1 for r in rows if getattr(r, 'image_risk_label', 'SAFE') in {'MEDIUM', 'HIGH', 'CRITICAL'})
    max_image_score = max((int(getattr(r, 'image_risk_score', 0) or 0) for r in rows), default=0)
    active_lanes = sorted({str(getattr(r, 'image_risk_decision_lane', getattr(r, 'image_risk_verdict_payload', {}).get('decision_lane', '')) or '') for r in rows if getattr(r, 'image_risk_score', 0)})
    cards = [
        GuardianCard('Case Readiness', f"{readiness.get('case_readiness', 0)}%", readiness.get('summary', 'Readiness is calculated after evidence import.')[:160], 'success' if readiness.get('case_readiness', 0) >= 75 else 'warning'),
        GuardianCard('Evidence Queue', str(len(rows)), 'Active isolated case item count.', 'info'),
        GuardianCard('High Risk', str(high), 'Items requiring early analyst review.', 'danger' if high else 'success'),
        GuardianCard('Location Anchors', f"{gps} GPS / {derived} derived", 'Derived map/OCR anchors are leads, not native GPS proof.', 'warning' if derived and not gps else 'info'),
        GuardianCard('Integrity', f"{verified}/{len(rows)}", 'Working-copy hash/custody verification state.', 'success' if rows and verified == len(rows) else 'warning'),
        GuardianCard('Digital Risk', str(hidden), 'ISOLATE/REVIEW decisions from container, LSB, alpha, and injection triage.', 'danger' if hidden else 'success'),
        GuardianCard('Image Threat AI', f"{dangerous_images} dangerous / {review_images} review", f"Max score {max_image_score}%. Lane: {', '.join(active_lanes[:2]) or 'clean'}.", 'danger' if dangerous_images else 'warning' if review_images else 'success'),
    ]
    return cards

def render_guardian_cards_text(records: Iterable[EvidenceRecord], readiness: dict[str, Any] | None = None) -> str:
    return '\n'.join(f"[{card.severity.upper()}] {card.title}: {card.value} — {card.note}" for card in build_guardian_cards(records, readiness)) + '\n'
