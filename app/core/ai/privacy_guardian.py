from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from ..models import EvidenceRecord


@dataclass(frozen=True)
class PrivacyIssue:
    evidence_id: str
    issue_type: str
    detail: str
    severity: str = "Medium"


@dataclass(frozen=True)
class PrivacyAudit:
    status: str
    privacy_level: str
    issues: list[PrivacyIssue] = field(default_factory=list)
    recommendation: str = "Use redacted_text for external sharing and courtroom_redacted for legal/courtroom packages."

    @property
    def summary(self) -> str:
        high = sum(1 for issue in self.issues if issue.severity == "High")
        medium = sum(1 for issue in self.issues if issue.severity == "Medium")
        low = sum(1 for issue in self.issues if issue.severity == "Low")
        lines = [
            f"Shareable export status: {self.status}",
            f"Privacy level: {self.privacy_level}",
            f"Issues: High {high} / Medium {medium} / Low {low}",
            f"Recommendation: {self.recommendation}",
        ]
        for issue in self.issues[:10]:
            lines.append(f"- {issue.evidence_id}: {issue.severity} {issue.issue_type} — {issue.detail}")
        return "\n".join(lines)


def audit_records(records: Iterable[EvidenceRecord], privacy_level: str = "redacted_text") -> PrivacyAudit:
    strict = privacy_level in {"redacted_text", "courtroom_redacted"}
    issues: list[PrivacyIssue] = []
    for record in records:
        if strict and record.file_name:
            issues.append(PrivacyIssue(record.evidence_id, "raw_filename", "original filename should be replaced with evidence ID in external exports", "Low"))
        if strict and (record.has_gps or record.derived_latitude is not None or record.derived_longitude is not None):
            issues.append(PrivacyIssue(record.evidence_id, "coordinates", "native or derived coordinates require redaction", "High"))
        if strict and (record.ocr_raw_text or record.visible_text_lines or record.visible_urls):
            issues.append(PrivacyIssue(record.evidence_id, "ocr_text", "visible OCR text/URLs/usernames may expose private context", "High"))
        if strict and (record.ocr_username_entities or record.ocr_location_entities or record.ocr_url_entities):
            issues.append(PrivacyIssue(record.evidence_id, "entities", "OCR entities require replacement tokens before external sharing", "Medium"))
        if not strict:
            issues.append(PrivacyIssue(record.evidence_id, "internal_export", "internal/full export can include previews, paths, and raw text", "Medium"))
    status = "Safe" if strict else "Needs review"
    if any(issue.severity == "High" for issue in issues) and not strict:
        status = "Unsafe for external sharing"
    return PrivacyAudit(status=status, privacy_level=privacy_level, issues=issues)
