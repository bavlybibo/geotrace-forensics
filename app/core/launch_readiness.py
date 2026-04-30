from __future__ import annotations

"""Launch-readiness gate for GeoTrace handoff packages.

The gate is intentionally conservative. It does not decide whether an evidence
item is "true"; it tells the analyst whether the current case is safe to demo,
share, or rely on as a courtroom-style package.  It exists to prevent a polished
UI/report from hiding missing anchors such as native GPS, strong time, privacy
redaction, validation data, or unresolved pixel/OCR findings.
"""

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Any

from .models import EvidenceRecord


@dataclass
class LaunchReadinessGate:
    label: str
    score: int
    status: str
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "score": int(self.score),
            "status": self.status,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "strengths": list(self.strengths),
            "next_actions": list(self.next_actions),
        }


def _pct(part: int, total: int) -> int:
    if total <= 0:
        return 0
    return round((part / total) * 100)


def _has_sensitive_export_mode(privacy_level: str) -> bool:
    return (privacy_level or "full").strip().lower().replace("-", "_") in {"full", "path_only"}


def evaluate_launch_readiness(
    records: Iterable[EvidenceRecord],
    *,
    privacy_level: str = "redacted_text",
    validation_metrics: Mapping[str, Any] | None = None,
    verification_passed: bool | None = None,
) -> LaunchReadinessGate:
    record_list = list(records)
    total = len(record_list)
    validation_metrics = validation_metrics or {}
    blockers: list[str] = []
    warnings: list[str] = []
    strengths: list[str] = []
    next_actions: list[str] = []

    if total == 0:
        blockers.append("No evidence has been imported into the active case.")
        next_actions.append("Import at least one evidence item before exporting or presenting the case.")
        return LaunchReadinessGate("No evidence", 0, "blocked", blockers, warnings, strengths, next_actions)

    parser_ok = sum(1 for r in record_list if r.parser_status == "Valid")
    integrity_ok = sum(1 for r in record_list if r.integrity_status == "Verified")
    native_gps = sum(1 for r in record_list if r.gps_confidence >= 80)
    derived_geo = sum(1 for r in record_list if r.derived_geo_display != "Unavailable" or bool(r.possible_geo_clues))
    strong_time = sum(1 for r in record_list if r.timestamp_confidence >= 80)
    court_ready = sum(1 for r in record_list if r.courtroom_strength >= 60)
    claim_ready = sum(1 for r in record_list if getattr(r, "claim_to_evidence_links", None))
    hidden_review = sum(
        1 for r in record_list
        if getattr(r, "pixel_hidden_score", 0) >= 40 or getattr(r, "hidden_code_indicators", None) or getattr(r, "hidden_suspicious_embeds", None)
    )
    route_screens = sum(1 for r in record_list if getattr(r, "route_overlay_detected", False))
    map_items = sum(1 for r in record_list if getattr(r, "map_intelligence_confidence", 0) > 0)

    if parser_ok == total:
        strengths.append(f"Parser/render check passed for {parser_ok}/{total} evidence item(s).")
    else:
        blockers.append(f"Parser/render check is incomplete: {parser_ok}/{total} passed.")
        next_actions.append("Validate parser-failed media with a second parser before relying on content claims.")

    if integrity_ok == total:
        strengths.append(f"Working-copy integrity verified for {integrity_ok}/{total} item(s).")
    else:
        blockers.append(f"Hash/custody integrity is not fully verified: {integrity_ok}/{total} verified.")
        next_actions.append("Re-import or re-hash items with non-verified source/working-copy integrity.")

    if _has_sensitive_export_mode(privacy_level):
        blockers.append(f"Current export privacy level is '{privacy_level}', which is internal-only for sharing.")
        next_actions.append("Generate Shareable Redacted or Courtroom Redacted before sending the package externally.")
    else:
        strengths.append(f"Privacy gate is using a redacted sharing mode: {privacy_level}.")

    if validation_metrics and validation_metrics.get("ground_truth_loaded"):
        strengths.append(str(validation_metrics.get("summary", "Validation dataset loaded.")))
    else:
        warnings.append("No linked validation dataset was found; accuracy is not measured against ground truth.")
        next_actions.append("Add validation_ground_truth.json beside the evidence set to produce measurable accuracy results.")

    if native_gps:
        strengths.append(f"Native GPS anchors available for {native_gps}/{total} item(s).")
    elif derived_geo:
        warnings.append(f"Location is based on derived/visible map context for {derived_geo}/{total} item(s), not native device GPS.")
        next_actions.append("Corroborate derived coordinates with source app history, map share URL, browser history, or surrounding case context.")
    else:
        warnings.append("No native GPS or stable derived geo anchor is present.")
        next_actions.append("Use OCR, filename, source app logs, witness context, or manual map/landmark review to build location support.")

    if strong_time:
        strengths.append(f"Strong time anchor present for {strong_time}/{total} item(s).")
    else:
        warnings.append("No strong native/embedded time anchor was found; chronology remains provisional.")
        next_actions.append("Confirm filename/filesystem times against upload, chat, cloud, or witness timeline data.")

    if court_ready:
        strengths.append(f"Courtroom-strength threshold reached by {court_ready}/{total} item(s).")
    else:
        warnings.append("No item currently reaches the 60% courtroom-strength threshold.")
        next_actions.append("Treat the current case as investigative/CTF support until independent time/location corroboration is added.")

    if hidden_review:
        warnings.append(f"{hidden_review} item(s) have hidden-content/pixel findings that still need analyst review.")
        next_actions.append("Review LSB/container findings manually before saying the file is clean or stego-positive.")

    if map_items:
        strengths.append(f"Map intelligence produced deterministic signals for {map_items}/{total} item(s).")
    if route_screens == 0:
        warnings.append("No route overlay/start-end signal was detected; route reconstruction is unavailable for this case.")

    if claim_ready:
        strengths.append(f"Claim-to-evidence rows are attached for {claim_ready}/{total} item(s).")
    else:
        warnings.append("Claim-to-evidence rows are missing or not persisted for the active record set.")
        next_actions.append("Run/re-run analysis so every major statement has a claim row and basis/limitation text.")

    if verification_passed is True:
        strengths.append("Package verifier passed for the last export.")
    elif verification_passed is False:
        blockers.append("Package verifier reported REVIEW/FAIL for the last export.")
        next_actions.append("Open package_verification.txt and fix missing/changed artifacts before handoff.")

    # Conservative weighted score. Blockers cap the case below external-launch range.
    score = 0
    score += _pct(parser_ok, total) * 0.14
    score += _pct(integrity_ok, total) * 0.18
    score += (0 if _has_sensitive_export_mode(privacy_level) else 100) * 0.14
    score += (100 if validation_metrics.get("ground_truth_loaded") else 35) * 0.12
    score += max(_pct(native_gps, total), min(_pct(derived_geo, total), 85)) * 0.12
    score += _pct(strong_time, total) * 0.10
    score += _pct(court_ready, total) * 0.10
    score += _pct(claim_ready, total) * 0.07
    score += (100 if hidden_review == 0 else 55) * 0.03
    score = max(0, min(100, round(score)))

    if blockers:
        label = "Internal only / blocked for external handoff"
        status = "blocked"
        score = min(score, 69)
    elif score >= 82 and not warnings:
        label = "External handoff ready"
        status = "ready"
    elif score >= 70:
        label = "Demo-ready with review notes"
        status = "review"
    elif score >= 55:
        label = "Investigative lead package"
        status = "review"
    else:
        label = "Needs more evidence"
        status = "needs_work"

    # Deduplicate while keeping the analyst-facing order stable.
    def dedupe(items: list[str], limit: int = 8) -> list[str]:
        seen = set()
        out = []
        for item in items:
            clean = str(item).strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            out.append(clean)
            if len(out) >= limit:
                break
        return out

    return LaunchReadinessGate(
        label=label,
        score=score,
        status=status,
        blockers=dedupe(blockers),
        warnings=dedupe(warnings),
        strengths=dedupe(strengths),
        next_actions=dedupe(next_actions, limit=10),
    )


def render_launch_gate_text(gate: LaunchReadinessGate) -> str:
    lines = [
        f"Launch readiness gate: {gate.label} ({gate.score}%)",
        f"Status: {gate.status}",
    ]
    if gate.blockers:
        lines.append("Blockers:")
        lines.extend(f"- {item}" for item in gate.blockers)
    if gate.warnings:
        lines.append("Warnings:")
        lines.extend(f"- {item}" for item in gate.warnings)
    if gate.strengths:
        lines.append("Strengths:")
        lines.extend(f"- {item}" for item in gate.strengths)
    if gate.next_actions:
        lines.append("Next actions:")
        lines.extend(f"- {item}" for item in gate.next_actions)
    return "\n".join(lines)
