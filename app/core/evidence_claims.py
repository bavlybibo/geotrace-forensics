from __future__ import annotations

"""Claim-to-evidence linking helpers.

This module keeps GeoTrace's AI/OSINT language evidence-grounded.  It does not
make new claims; it converts already-computed record fields into auditable claim
rows that can be shown in the dashboard, JSON export, and report-builder index.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable
import logging
from .structured_logging import log_failure

try:  # pragma: no cover - import fallback for direct script execution
    from .models import EvidenceRecord
except Exception:  # pragma: no cover
    from app.core.models import EvidenceRecord


@dataclass(slots=True)
class EvidenceClaim:
    claim_id: str
    evidence_id: str
    claim: str
    source_family: str
    confidence: int
    strength: str
    status: str
    basis: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        basis = "; ".join(self.basis[:4]) or "no basis captured"
        limitations = "; ".join(self.limitations[:3]) or "none recorded"
        return (
            f"- **{self.claim_id}** [{self.status}] {self.claim} "
            f"— confidence {self.confidence}% / {self.strength}. Basis: {basis}. Limits: {limitations}."
        )


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _bounded(value: Any) -> int:
    try:
        return max(0, min(100, int(value or 0)))
    except Exception:
        return 0


def _unique(items: Iterable[Any], limit: int = 8) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _clean(item).strip(" -|•")
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _status_from_confidence(confidence: int, *, needs_anchor: bool = False) -> str:
    if confidence >= 85 and not needs_anchor:
        return "proof"
    if confidence >= 70:
        return "strong_lead"
    if confidence >= 45:
        return "lead"
    return "weak_signal"


def build_claim_links(record: EvidenceRecord) -> list[EvidenceClaim]:
    """Build conservative claim rows for a single evidence record."""

    claims: list[EvidenceClaim] = []
    eid = _clean(getattr(record, "evidence_id", "IMG")) or "IMG"

    # Acquisition / integrity proof.
    integrity_conf = 95 if getattr(record, "copy_verified", False) else max(45, _bounded(getattr(record, "confidence_score", 0)))
    claims.append(
        EvidenceClaim(
            claim_id=f"{eid}-integrity",
            evidence_id=eid,
            claim="Working copy integrity is tracked with source/working hashes." if getattr(record, "copy_verified", False) else "Working copy integrity still needs manual verification.",
            source_family="custody/hash",
            confidence=integrity_conf,
            strength="proof" if getattr(record, "copy_verified", False) else "lead",
            status="proof" if getattr(record, "copy_verified", False) else "needs_review",
            basis=_unique([
                f"source_sha256={_clean(getattr(record, 'source_sha256', ''))[:16]}",
                f"working_sha256={_clean(getattr(record, 'working_sha256', ''))[:16]}",
                _clean(getattr(record, "acquisition_note", "")),
            ], 4),
            limitations=[] if getattr(record, "copy_verified", False) else ["copy verification was not recorded as true"],
            next_actions=["Keep the original file and exported manifest together for handoff."],
        )
    )

    # Timeline claim.
    time_conf = _bounded(getattr(record, "timestamp_confidence", 0))
    if _clean(getattr(record, "timestamp", "Unknown")) != "Unknown" or time_conf > 0:
        claims.append(
            EvidenceClaim(
                claim_id=f"{eid}-time",
                evidence_id=eid,
                claim=f"Timeline anchor: {_clean(getattr(record, 'timestamp', 'Unknown'))} from {_clean(getattr(record, 'timestamp_source', 'Unavailable'))}.",
                source_family="timeline",
                confidence=time_conf,
                strength=_status_from_confidence(time_conf, needs_anchor=time_conf < 80),
                status="proof" if time_conf >= 85 else "needs_corroboration",
                basis=_unique([
                    _clean(getattr(record, "timestamp_verdict", "")),
                    *list(getattr(record, "time_candidates", []) or [])[:3],
                ], 5),
                limitations=_unique(list(getattr(record, "time_conflicts", []) or []) or ["corroborate with upload/chat/cloud history before final chronology"], 4),
                next_actions=["Compare the recovered time with external upload logs, chat timestamps, or witness timeline."],
            )
        )

    # GPS / derived geo claim.
    native_conf = _bounded(getattr(record, "gps_confidence", 0))
    derived_conf = _bounded(getattr(record, "derived_geo_confidence", 0))
    map_conf = _bounded(getattr(record, "map_intelligence_confidence", 0))
    if native_conf or derived_conf or map_conf or _clean(getattr(record, "geo_status", "")):
        best_conf = max(native_conf, derived_conf, map_conf)
        has_native = bool(getattr(record, "has_gps", False))
        claim_text = "Native GPS recovered" if has_native else "Location evidence is derived or visual/contextual only"
        if has_native:
            claim_text += f": {_clean(getattr(record, 'gps_display', 'Unavailable'))}"
        elif _clean(getattr(record, "derived_geo_display", "Unavailable")) != "Unavailable":
            claim_text += f": {_clean(getattr(record, 'derived_geo_display', 'Unavailable'))}"
        elif _clean(getattr(record, "possible_place", "Unavailable")) not in {"", "Unavailable", "Unknown", "N/A"}:
            claim_text += f": {_clean(getattr(record, 'possible_place', 'Unavailable'))}"
        claims.append(
            EvidenceClaim(
                claim_id=f"{eid}-geo",
                evidence_id=eid,
                claim=claim_text,
                source_family="geo/map",
                confidence=best_conf,
                strength="proof" if has_native and best_conf >= 85 else _status_from_confidence(best_conf, needs_anchor=not has_native),
                status="proof" if has_native and best_conf >= 85 else "lead_only",
                basis=_unique([
                    _clean(getattr(record, "gps_source", "")),
                    _clean(getattr(record, "derived_geo_source", "")),
                    *_unique(getattr(record, "map_evidence_basis", []) or [], 4),
                    *_unique(getattr(record, "place_candidate_rankings", []) or [], 2),
                ], 8),
                limitations=_unique([
                    *_unique(getattr(record, "map_limitations", []) or [], 4),
                    *_unique(getattr(record, "location_estimate_limitations", []) or [], 3),
                    "displayed map context is not proof of device location" if not has_native else "",
                ], 8),
                next_actions=_unique(getattr(record, "map_recommended_actions", []) or getattr(record, "location_estimate_next_actions", []) or ["Verify the place with a source URL, OCR labels, or native device/app logs."], 6),
            )
        )

    # OCR / visible text claim.
    ocr_conf = _bounded(getattr(record, "ocr_confidence", 0))
    if ocr_conf or getattr(record, "visible_text_lines", []) or getattr(record, "ocr_map_labels", []):
        claims.append(
            EvidenceClaim(
                claim_id=f"{eid}-ocr",
                evidence_id=eid,
                claim=f"OCR recovered visible text/map labels with {ocr_conf}% confidence.",
                source_family="ocr/visible-text",
                confidence=ocr_conf,
                strength=_status_from_confidence(ocr_conf),
                status="evidence" if ocr_conf >= 65 else "needs_review",
                basis=_unique([
                    *_unique(getattr(record, "ocr_map_labels", []) or [], 5),
                    *_unique(getattr(record, "visible_text_lines", []) or [], 5),
                    _clean(getattr(record, "ocr_note", "")),
                ], 8),
                limitations=["OCR may misread small, low-contrast, rotated, or mixed-language labels."],
                next_actions=["Use Manual Crop OCR on labels/search bars if the answer depends on text."],
            )
        )

    # Hidden/pixel claim.
    hidden_conf = max(_bounded(getattr(record, "pixel_hidden_score", 0)), 55 if getattr(record, "hidden_code_indicators", []) else 0)
    if hidden_conf or getattr(record, "hidden_suspicious_embeds", []) or getattr(record, "pixel_lsb_strings", []):
        claims.append(
            EvidenceClaim(
                claim_id=f"{eid}-hidden",
                evidence_id=eid,
                claim=_clean(getattr(record, "pixel_hidden_summary", "Hidden-content indicators were detected.")) or "Hidden-content indicators were detected.",
                source_family="hidden-content/pixel",
                confidence=hidden_conf,
                strength=_status_from_confidence(hidden_conf),
                status="needs_review" if hidden_conf < 80 else "evidence",
                basis=_unique([
                    *_unique(getattr(record, "pixel_hidden_indicators", []) or [], 5),
                    *_unique(getattr(record, "hidden_code_indicators", []) or [], 5),
                    *_unique(getattr(record, "hidden_suspicious_embeds", []) or [], 4),
                ], 8),
                limitations=_unique(getattr(record, "pixel_hidden_limitations", []) or ["pixel anomalies are triage signals until manually validated"], 4),
                next_actions=_unique(getattr(record, "pixel_hidden_next_actions", []) or ["Review extracted strings/crops before using this in a final report."], 5),
            )
        )

    # AI/context claim kept as advisory, not proof.
    ai_conf = _bounded(getattr(record, "ai_confidence", 0))
    if _clean(getattr(record, "ai_summary", "")) and _clean(getattr(record, "ai_summary", "")) != "AI batch assessment has not run for this evidence.":
        claims.append(
            EvidenceClaim(
                claim_id=f"{eid}-ai",
                evidence_id=eid,
                claim=_clean(getattr(record, "ai_executive_note", "")) or _clean(getattr(record, "ai_summary", "")),
                source_family="ai-advisory",
                confidence=ai_conf,
                strength=_clean(getattr(record, "evidence_strength_label", "weak_signal")) or "weak_signal",
                status="advisory",
                basis=_unique(getattr(record, "ai_reasons", []) or getattr(record, "ai_flags", []) or [], 6),
                limitations=["AI rows are triage guidance only; final report language must be tied to forensic/OCR/GPS/custody evidence."],
                next_actions=_unique(getattr(record, "ai_action_plan", []) or ["Validate AI recommendations manually."], 6),
            )
        )

    return claims


def build_claim_links_dicts(record: EvidenceRecord) -> list[dict[str, Any]]:
    return [claim.to_dict() for claim in build_claim_links(record)]


def attach_claim_links(record: EvidenceRecord) -> list[dict[str, Any]]:
    links = build_claim_links_dicts(record)
    try:
        setattr(record, "claim_to_evidence_links", links)
    except Exception as exc:
        log_failure(
            logging.getLogger("geotrace"),
            context="evidence_claims",
            operation="attach_claim_links",
            evidence_id=str(getattr(record, "evidence_id", "")),
            message="Could not attach claim-to-evidence links to the record object.",
            exc=exc,
            severity="warning",
            user_visible=False,
        )
    return links
