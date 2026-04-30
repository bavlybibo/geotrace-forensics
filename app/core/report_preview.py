from __future__ import annotations

"""Pre-export report preview contract."""

from dataclasses import asdict, dataclass, field
from typing import Iterable, Any

from .launch_readiness import evaluate_launch_readiness
from .models import EvidenceRecord

@dataclass(slots=True)
class ReportPreview:
    privacy_level: str
    export_mode: str
    gate_label: str
    gate_score: int
    status: str
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    included_artifacts: list[str] = field(default_factory=list)
    required_after_export: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def build_report_preview(records: Iterable[EvidenceRecord], *, privacy_level: str = 'redacted_text', export_mode: str = 'Shareable Redacted', verification_passed: bool | None = None) -> ReportPreview:
    gate = evaluate_launch_readiness(records, privacy_level=privacy_level, verification_passed=verification_passed)
    artifacts = [
        'HTML technical report', 'PDF report', 'CSV evidence summary', 'JSON evidence export',
        'Executive summary', 'Courtroom notes', 'AI Guardian summary', 'OSINT appendix',
        'Claim-to-evidence matrix', 'Validation template', 'Export manifest', 'Package signature',
        'Package verification report',
    ]
    required = [
        'Open package_verification.txt and confirm PASS before handoff.',
        'Confirm privacy mode matches the audience before sharing.',
        'Keep original evidence outside the shareable package unless explicitly authorized.',
    ]
    return ReportPreview(
        privacy_level=privacy_level,
        export_mode=export_mode,
        gate_label=gate.label,
        gate_score=gate.score,
        status=gate.status,
        blockers=list(gate.blockers),
        warnings=list(gate.warnings),
        included_artifacts=artifacts,
        required_after_export=required,
    )

def render_report_preview(records: Iterable[EvidenceRecord], *, privacy_level: str = 'redacted_text', export_mode: str = 'Shareable Redacted', verification_passed: bool | None = None) -> str:
    preview = build_report_preview(records, privacy_level=privacy_level, export_mode=export_mode, verification_passed=verification_passed)
    lines = [
        '[REPORT PREVIEW / EXPORT CONTRACT]',
        '==================================',
        f"Mode: {preview.export_mode} | Privacy: {preview.privacy_level}",
        f"Gate: {preview.gate_label} ({preview.gate_score}%) | Status: {preview.status}",
        '',
        'Blockers:',
    ]
    lines.extend(f"- {item}" for item in (preview.blockers or ['None']))
    lines.extend(['', 'Warnings:'])
    lines.extend(f"- {item}" for item in (preview.warnings or ['None']))
    lines.extend(['', 'Included artifacts:'])
    lines.extend(f"- {item}" for item in preview.included_artifacts)
    lines.extend(['', 'Required after export:'])
    lines.extend(f"- {item}" for item in preview.required_after_export)
    return '\n'.join(lines).strip() + '\n'
