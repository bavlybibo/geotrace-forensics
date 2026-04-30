from __future__ import annotations

"""Enterprise audit-mode summaries for case handoff and QA."""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Iterable, Any


@dataclass(slots=True)
class EnterpriseAuditSummary:
    generated_at: str
    evidence_count: int
    high_risk_count: int
    privacy_level: str
    custody_ready: bool
    verifier_required: bool
    blockers: list[str] = field(default_factory=list)
    controls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_enterprise_audit_summary(records: Iterable[Any], *, privacy_level: str = "redacted_text", verification_passed: bool = False) -> EnterpriseAuditSummary:
    rows = list(records)
    blockers: list[str] = []
    if not rows:
        blockers.append("No evidence imported.")
    if privacy_level == "full":
        blockers.append("Internal Full export selected; do not share externally.")
    if not verification_passed:
        blockers.append("Package verifier has not passed yet.")
    weak_location = [r for r in rows if int(getattr(r, "map_answer_readiness_score", 0) or 0) < 50 and not getattr(r, "has_gps", False)]
    if weak_location:
        blockers.append(f"{len(weak_location)} item(s) have weak/no location anchors.")
    controls = [
        "Case-scoped custody chain enabled.",
        "Manifest hashes generated for artifacts.",
        "Claim-to-evidence matrix available.",
        "Privacy mode recorded in export metadata.",
    ]
    if verification_passed:
        controls.append("Package verifier PASS recorded.")
    return EnterpriseAuditSummary(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        evidence_count=len(rows),
        high_risk_count=sum(1 for r in rows if getattr(r, "risk_level", "Low") == "High"),
        privacy_level=privacy_level,
        custody_ready=bool(rows),
        verifier_required=not verification_passed,
        blockers=blockers,
        controls=controls,
    )
