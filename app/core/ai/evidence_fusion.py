from __future__ import annotations

"""Claim-to-evidence fusion for the AI Guardian layer.

The goal is to make every AI suggestion explainable.  This module produces
conservative claims, supporting signals, contradictions, limitations, and next
best actions from already-recovered forensic evidence.  It does not infer facts
without evidence and intentionally avoids person identification.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from ..models import EvidenceRecord


@dataclass(slots=True)
class FusedClaim:
    claim: str
    status: str = "lead"  # proof | strong_lead | lead | weak_signal | unsupported
    confidence: int = 0
    evidence: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_matrix_line(self) -> str:
        ev = " | ".join(self.evidence[:3]) or "no direct support"
        lim = " | limitations: " + " | ".join(self.limitations[:2]) if self.limitations else ""
        con = " | contradictions: " + " | ".join(self.contradictions[:2]) if self.contradictions else ""
        return f"Claim [{self.status} {self.confidence}%]: {self.claim} | evidence: {ev}{con}{lim}"


def _add_unique(items: list[str], value: str) -> None:
    clean = " ".join(str(value or "").split()).strip()
    if clean and clean not in items:
        items.append(clean)


def _bounded_confidence(base: int, evidence_count: int, contradiction_count: int, limitation_count: int) -> int:
    score = base + min(20, evidence_count * 5) - min(25, contradiction_count * 12) - min(18, limitation_count * 4)
    return max(0, min(100, score))


def _gps_claim(record: EvidenceRecord) -> FusedClaim | None:
    if bool(getattr(record, "has_gps", False)):
        claim = FusedClaim(
            claim="Evidence contains a native GPS coordinate anchor.",
            status="proof" if int(getattr(record, "gps_confidence", 0) or 0) >= 80 else "strong_lead",
            confidence=int(getattr(record, "gps_confidence", 0) or 75),
            evidence=[
                f"GPS display: {getattr(record, 'gps_display', 'Unavailable')}",
                f"GPS source: {getattr(record, 'gps_source', 'Unavailable')}",
                f"SHA256: {getattr(record, 'sha256', '')[:16]}...",
            ],
            limitations=["Native GPS proves metadata content, not necessarily who captured or shared the file."],
            next_actions=["Verify coordinate against source device/timeline and map reconstruction before final wording."],
        )
        if getattr(record, "derived_geo_display", "Unavailable") != "Unavailable":
            _add_unique(claim.evidence, f"Derived geo corroboration: {getattr(record, 'derived_geo_display', '')}")
        return claim
    if getattr(record, "derived_geo_display", "Unavailable") != "Unavailable":
        evidence = [
            f"Derived display: {getattr(record, 'derived_geo_display', '')}",
            f"Derived source: {getattr(record, 'derived_geo_source', '')}",
        ]
        if getattr(record, "map_evidence_basis", []):
            evidence.extend(list(getattr(record, "map_evidence_basis", []) or [])[:3])
        return FusedClaim(
            claim="Evidence contains a derived location/map lead, but no native GPS anchor.",
            status="lead" if int(getattr(record, "derived_geo_confidence", 0) or 0) < 65 else "strong_lead",
            confidence=max(35, min(78, int(getattr(record, "derived_geo_confidence", 0) or 45))),
            evidence=evidence,
            limitations=["Derived map/OCR locations are investigative leads unless corroborated by original app logs, URL history, or source device records."],
            next_actions=["Label this as derived geo, not confirmed device location."],
        )
    return None


def _map_claim(record: EvidenceRecord) -> FusedClaim | None:
    map_conf = int(getattr(record, "map_intelligence_confidence", 0) or getattr(record, "map_confidence", 0) or 0)
    labels = list(getattr(record, "ocr_map_labels", []) or [])[:5]
    basis = list(getattr(record, "map_evidence_basis", []) or [])[:5]
    if not map_conf and not labels and not basis:
        return None
    evidence = []
    if map_conf:
        evidence.append(f"Map intelligence confidence: {map_conf}%")
    if getattr(record, "map_app_detected", "Unknown") != "Unknown":
        evidence.append(f"Map app: {getattr(record, 'map_app_detected', '')}")
    if getattr(record, "map_type", "Unknown") != "Unknown":
        evidence.append(f"Map type: {getattr(record, 'map_type', '')}")
    evidence.extend(basis)
    if labels:
        evidence.append("OCR map labels: " + ", ".join(labels))
    limitations = list(getattr(record, "map_limitations", []) or [])[:3]
    limitations.append("A displayed map can show a searched place or destination; it is not automatically the camera/device location.")
    return FusedClaim(
        claim="Evidence appears to contain map/navigation context.",
        status="strong_lead" if map_conf >= 70 else "lead" if map_conf >= 40 else "weak_signal",
        confidence=max(30, min(86, map_conf or int(getattr(record, "ocr_confidence", 0) or 35))),
        evidence=evidence[:8],
        limitations=limitations[:5],
        next_actions=list(getattr(record, "map_recommended_actions", []) or [])[:3]
        or ["Decide whether map content is current location, searched venue, route origin, or destination."],
    )


def _image_claim(record: EvidenceRecord) -> FusedClaim | None:
    conf = int(getattr(record, "image_detail_confidence", 0) or 0)
    if conf <= 0:
        return None
    metrics = dict(getattr(record, "image_detail_metrics", {}) or {})
    local_vision = metrics.get("local_vision") if isinstance(metrics.get("local_vision"), dict) else {}
    semantic = metrics.get("semantic_fingerprint") if isinstance(metrics.get("semantic_fingerprint"), dict) else {}
    evidence = [f"Image profile: {getattr(record, 'image_detail_label', '')} ({conf}%)"]
    evidence.extend(list(getattr(record, "image_scene_descriptors", []) or [])[:3])
    if semantic:
        evidence.append(f"Semantic fingerprint: {semantic.get('fingerprint', 'unavailable')} | tags={', '.join(semantic.get('tags', [])[:4])}")
    if local_vision and local_vision.get("executed"):
        evidence.append(f"Local vision runner: {local_vision.get('provider')} | {local_vision.get('scene_label') or local_vision.get('caption') or 'executed'}")
    limitations = list(getattr(record, "image_detail_limitations", []) or [])[:3]
    if not (local_vision and local_vision.get("executed")):
        limitations.append("No configured neural local vision runner executed; image reasoning is deterministic/heuristic.")
    return FusedClaim(
        claim="Image content has triage value for OCR, map review, or hidden-content prioritization.",
        status="lead" if conf < 75 else "strong_lead",
        confidence=conf,
        evidence=evidence[:8],
        limitations=limitations[:5],
        next_actions=list(getattr(record, "image_detail_next_actions", []) or [])[:3],
    )


def _hidden_claim(record: EvidenceRecord) -> FusedClaim | None:
    indicators = list(getattr(record, "hidden_code_indicators", []) or [])
    embeds = list(getattr(record, "hidden_suspicious_embeds", []) or [])
    pixel_score = int(getattr(record, "pixel_hidden_score", 0) or 0)
    if not indicators and not embeds and pixel_score <= 0:
        return None
    evidence = []
    if indicators:
        evidence.append("Embedded text/code indicators: " + ", ".join(indicators[:5]))
    if embeds:
        evidence.append("Suspicious embedded segments: " + ", ".join(embeds[:3]))
    if pixel_score:
        evidence.append(f"Pixel hidden-content score: {pixel_score}% | {getattr(record, 'pixel_hidden_verdict', '')}")
    return FusedClaim(
        claim="Evidence has hidden-content or embedded-payload signals requiring safe review.",
        status="lead" if pixel_score < 70 else "strong_lead",
        confidence=max(45, min(88, pixel_score or 55)),
        evidence=evidence,
        limitations=["Hidden-content heuristics are not exploit proof; carved payloads must be opened only in a safe analysis environment."],
        next_actions=["Review carved/embedded content with hashes and a safe viewer before describing impact."],
    )


def _integrity_claim(record: EvidenceRecord) -> FusedClaim:
    evidence = [
        f"Parser status: {getattr(record, 'parser_status', 'Unknown')}",
        f"Integrity status: {getattr(record, 'integrity_status', 'Unknown')}",
        f"Copy verified: {bool(getattr(record, 'copy_verified', False))}",
    ]
    limitations: list[str] = []
    contradictions: list[str] = []
    status = "lead"
    base = 55
    if getattr(record, "parser_status", "") != "Valid":
        contradictions.append("Parser reported a non-valid status; content-level AI claims must be delayed.")
        status = "weak_signal"
        base = 35
    if not bool(getattr(record, "copy_verified", False)):
        limitations.append("Working-copy/source hash verification is missing or incomplete.")
    if getattr(record, "exif_warning", ""):
        limitations.append("EXIF warning: " + str(getattr(record, "exif_warning", ""))[:200])
    return FusedClaim(
        claim="Evidence integrity/custody state controls how strongly AI guidance may be used.",
        status=status,
        confidence=_bounded_confidence(base, len(evidence), len(contradictions), len(limitations)),
        evidence=evidence,
        contradictions=contradictions,
        limitations=limitations,
        next_actions=["Resolve integrity/custody blockers before using AI language in a final report."],
    )


def fuse_record_claims(record: EvidenceRecord) -> list[FusedClaim]:
    claims: list[FusedClaim] = []
    for builder in (_integrity_claim, _gps_claim, _map_claim, _image_claim, _hidden_claim):
        claim = builder(record)
        if claim is not None:
            claim.confidence = max(0, min(100, int(claim.confidence)))
            claims.append(claim)
    return claims


def attach_fused_claims_to_finding(record: EvidenceRecord, finding: Any) -> None:
    claims = fuse_record_claims(record)
    if not claims:
        return
    for claim in claims[:6]:
        if hasattr(finding, "add_matrix_line"):
            finding.add_matrix_line(claim.to_matrix_line())
        if claim.contradictions and hasattr(finding, "add_contradiction"):
            for contradiction in claim.contradictions[:2]:
                finding.add_contradiction(contradiction)
        if claim.next_actions and hasattr(finding, "add_action"):
            for action in claim.next_actions[:2]:
                finding.add_action("Evidence fusion: " + action)
        if claim.status in {"weak_signal", "unsupported"} and hasattr(finding, "add_action"):
            finding.add_action("Guardrail: do not upgrade weak AI signal without independent corroboration.")
        if claim.status == "proof":
            finding.confidence_delta = max(getattr(finding, "confidence_delta", 0), 4)
