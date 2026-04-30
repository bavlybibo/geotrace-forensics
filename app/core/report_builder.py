from __future__ import annotations

"""Real report-builder index for handoff packages.

The generated index is a plain Markdown control document that tells the analyst what
was exported, which mode is safe to share, and which evidence claims back each major
finding. It complements the HTML/PDF rather than replacing them.
"""

from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping, Any
import json

from .evidence_claims import build_claim_links
from .launch_readiness import evaluate_launch_readiness, render_launch_gate_text
from .validation_service import build_validation_metrics
from .models import EvidenceRecord


def build_report_builder_payload(records: Iterable[EvidenceRecord], *, case_id: str, case_name: str, privacy_level: str, artifacts: Mapping[str, str]) -> dict[str, Any]:
    record_list = list(records)
    claim_rows = []
    for record in record_list:
        claim_rows.extend(claim.to_dict() for claim in build_claim_links(record))
    validation = build_validation_metrics(record_list)
    launch_gate = evaluate_launch_readiness(record_list, privacy_level=privacy_level, validation_metrics=validation)
    return {
        "case_id": case_id,
        "case_name": case_name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "privacy_level": privacy_level,
        "evidence_count": len(record_list),
        "artifacts": dict(artifacts),
        "claim_count": len(claim_rows),
        "launch_gate": launch_gate.to_dict(),
        "validation_summary": validation.get("summary", "No linked validation dataset was found."),
        "claims": claim_rows,
        "handoff_checklist": [
            "Open package_verification.txt and confirm PASS before sharing.",
            "Use Shareable Redacted/Courtroom Redacted for external recipients.",
            "Treat visual-only location/map context as a lead unless GPS, coordinates, map URL, OCR labels, or source-app logs corroborate it.",
            "Keep export_manifest.json and export_manifest.sha256 with the final report package.",
            "Resolve Launch Readiness Gate blockers before calling the package externally/courtroom ready.",
        ],
    }


def render_report_builder_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# GeoTrace Report Builder Index",
        "",
        f"Case ID: `{payload.get('case_id', '')}`",
        f"Case Name: **{payload.get('case_name', '')}**",
        f"Generated: {payload.get('generated_at', '')}",
        f"Privacy Level: **{payload.get('privacy_level', '')}**",
        f"Evidence Items: {payload.get('evidence_count', 0)}",
        f"Claim Links: {payload.get('claim_count', 0)}",
        "",
        "## Launch Readiness Gate",
    ]
    gate = payload.get("launch_gate", {}) or {}
    if gate:
        lines.append(f"**{gate.get('label', 'Unknown')}** — score **{gate.get('score', 0)}%** — status `{gate.get('status', 'review')}`")
        for section, title in [("blockers", "Blockers"), ("warnings", "Warnings"), ("strengths", "Strengths"), ("next_actions", "Next actions")]:
            items = gate.get(section, []) or []
            if items:
                lines.append(f"\n### {title}")
                lines.extend(f"- {item}" for item in items)
    else:
        lines.append("No launch gate was generated for this package.")
    lines.extend(["", "## Artifact Map"])
    artifacts = payload.get("artifacts", {}) or {}
    for key, path in artifacts.items():
        lines.append(f"- **{key}**: `{Path(str(path)).name}`")
    lines.extend(["", "## Handoff Checklist"])
    for item in payload.get("handoff_checklist", []) or []:
        lines.append(f"- [ ] {item}")
    lines.extend(["", "## Claim-to-Evidence Matrix"])
    claims = payload.get("claims", []) or []
    if not claims:
        lines.append("No claim rows generated yet.")
    else:
        for claim in claims:
            basis = "; ".join((claim.get("basis") or [])[:4]) or "no basis captured"
            limits = "; ".join((claim.get("limitations") or [])[:3]) or "none recorded"
            lines.append(
                f"- **{claim.get('claim_id')}** `{claim.get('source_family')}` `{claim.get('status')}` "
                f"{claim.get('claim')} — confidence **{claim.get('confidence')}%** / {claim.get('strength')}. "
                f"Basis: {basis}. Limits: {limits}."
            )
    lines.extend(["", "## Analyst Notes", "", "Use this file as the package table of contents and verification checklist before final delivery."])
    return "\n".join(lines).strip() + "\n"


def write_report_builder_index(export_dir: Path, records: Iterable[EvidenceRecord], *, case_id: str, case_name: str, privacy_level: str, artifacts: Mapping[str, str]) -> dict[str, str]:
    export_dir.mkdir(parents=True, exist_ok=True)
    payload = build_report_builder_payload(records, case_id=case_id, case_name=case_name, privacy_level=privacy_level, artifacts=artifacts)
    json_path = export_dir / "report_builder_index.json"
    md_path = export_dir / "report_builder_index.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_report_builder_markdown(payload), encoding="utf-8")
    return {"report_builder": str(md_path), "report_builder_json": str(json_path)}
