from __future__ import annotations

from typing import Dict, List

from .models import EvidenceRecord


EXPORT_LIKE = {"Screenshot", "Screenshot / Export", "Messaging Export", "Map Screenshot", "Browser Screenshot", "Chat Screenshot", "Desktop Capture", "Mobile Screenshot", "Graphic Asset"}
PHOTO_LIKE = {"Camera Photo", "Edited / Exported", "Unknown"}


def _dedupe(items: List[str], *, limit: int = 8) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        item = (item or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def build_metadata_issue_bundle(record: EvidenceRecord) -> Dict[str, object]:
    issues: List[str] = []
    strengths: List[str] = []
    recommendations: List[str] = []

    if not record.exif:
        if record.source_type in EXPORT_LIKE:
            issues.append("Thin embedded metadata is consistent with screenshot/export media, so provenance must come from timeline, OCR, and custody context instead of EXIF.")
        else:
            issues.append("No embedded EXIF/IPTC/XMP-style metadata was recovered, which weakens direct attribution to a source device or camera workflow.")
            recommendations.append("Try to recover the original file before forwarding/export, then validate it with a secondary metadata parser.")
    else:
        strengths.append(f"Embedded metadata fields recovered: {min(len(record.exif), 20)} visible tag(s).")

    if record.device_model not in {"Unknown", "N/A", ""}:
        strengths.append(f"Device fingerprint available: {record.device_model}.")
    elif record.source_type in PHOTO_LIKE:
        issues.append("No clear camera make/model fingerprint was recovered from a photo-like asset.")

    if record.software not in {"N/A", "Unknown", ""}:
        sw = record.software.lower()
        if any(term in sw for term in ["photoshop", "lightroom", "snapseed", "gimp", "canva"]):
            issues.append(f"Software tag '{record.software}' indicates an edit/export workflow rather than a clean original capture chain.")
            recommendations.append("Preserve both the current derivative and any upstream original to explain the edit/export path.")
        else:
            strengths.append(f"Software tag present: {record.software}.")

    if record.timestamp_source == "Filename Pattern":
        issues.append("The selected time anchor came from the filename pattern, so it helps triage but does not prove original capture time by itself.")
        recommendations.append("Corroborate filename-based time against uploads, chats, cloud backups, or witness timeline data.")
    elif record.timestamp_source.startswith("Filesystem"):
        issues.append("The selected time anchor came from filesystem metadata, which can drift after copy, sync, or export operations.")
        recommendations.append("Treat filesystem time as workflow context unless another native time anchor confirms it.")
    elif record.timestamp_confidence >= 80:
        strengths.append(f"Time anchor is comparatively strong: {record.timestamp_source} ({record.timestamp_confidence}%).")

    if record.time_conflicts:
        issues.append("At least one weaker time candidate materially disagrees with the chosen anchor, so chronology claims should remain conservative.")

    if record.signature_status == "Mismatch":
        issues.append("File extension and internal signature disagree, which is a structural integrity concern independent of the visible preview.")
        recommendations.append("Validate the file with a second parser and compare the working copy with the original hash-preserved source.")
    elif record.parser_status == "Valid":
        strengths.append("Primary parser decoded the media successfully.")
    else:
        issues.append("Primary parser could not decode the media cleanly, so structure assumptions remain provisional.")
        recommendations.append("Use a second parser or hex-level review before relying on content or metadata claims.")

    if record.has_gps:
        strengths.append(f"Native GPS coordinates were recovered: {record.gps_display}.")
    elif record.derived_geo_display != "Unavailable":
        issues.append("Location clue is derived from visible content rather than native EXIF GPS, so it should be treated as contextual support only.")
        recommendations.append("Preserve browser/app context and any visible map URL to corroborate screenshot-derived location claims.")
    elif record.source_type in PHOTO_LIKE:
        issues.append("No native GPS coordinates were recovered from a photo-like file.")

    if record.hidden_code_indicators:
        issues.append("The container includes code-like or credential-like strings, so the file is not safely described as image-only until manual validation is complete.")
        recommendations.append("Export and inspect the suspicious payload bytes separately, then document whether the content is benign metadata or a real embedded payload.")
    elif record.hidden_suspicious_embeds:
        issues.append("The container has structural hidden-content warnings such as trailing bytes, encoded blobs, or unusual appendices.")

    if record.duplicate_group:
        strengths.append(f"Duplicate/derivative linkage is available through {record.duplicate_group} ({record.duplicate_relation or 'visual relation'}).")

    if not recommendations:
        if record.risk_level == "High":
            recommendations.append("Review the file before presentation, then document the strongest issue, why it matters, and what corroboration is still missing.")
        else:
            recommendations.append("Preserve the current hash set and use the file as a supporting artifact rather than a standalone proof point.")

    summary = issues[0] if issues else "No major metadata red flag dominates this file; use the strongest anchor together with context and custody notes."
    return {
        "issues": _dedupe(issues, limit=8),
        "strengths": _dedupe(strengths, limit=8),
        "recommendations": _dedupe(recommendations, limit=6),
        "summary": summary,
    }


def build_gps_verification_ladder(record: EvidenceRecord) -> Dict[str, object]:
    ladder: List[str] = []
    if record.has_gps:
        ladder.append(f"1. Native EXIF GPS — PASS ({record.gps_display}, {record.gps_confidence}%).")
        ladder.append(f"2. Native GPS reasoning — {record.gps_verification}")
        if record.gps_altitude is not None:
            ladder.append(f"3. Altitude — {record.gps_altitude:.2f} m recovered from EXIF GPSAltitude.")
        else:
            ladder.append("3. Altitude — not available in the native GPS tags.")
        if record.derived_geo_display != "Unavailable":
            ladder.append(f"4. Visible-content geo — secondary clue also exists ({record.derived_geo_display}).")
        else:
            ladder.append("4. Visible-content geo — no separate screenshot/browser clue was needed.")
        primary_issue = "Native GPS is present; remaining work is external corroboration rather than coordinate recovery."
        ladder.append("5. Analyst action — validate the place externally and compare the route/time with surrounding evidence.")
        return {"ladder": ladder, "primary_issue": primary_issue}

    ladder.append("1. Native EXIF GPS — FAIL (no native coordinates recovered).")
    if record.derived_latitude is not None and record.derived_longitude is not None:
        ladder.append(f"2. Visible URL / coordinate text — PASS ({record.derived_geo_display}, {record.derived_geo_confidence}%).")
        ladder.append(f"3. Derived source — {record.derived_geo_source}. {record.derived_geo_note}")
        primary_issue = "Only screenshot/browser-derived coordinates are available, so the location is contextual rather than device-native."
    elif record.possible_geo_clues:
        ladder.append("2. Visible URL / coordinate text — no stable coordinates parsed.")
        ladder.append(f"3. OCR place labels — PASS ({'; '.join(record.possible_geo_clues[:3])}).")
        primary_issue = "Only OCR place labels were recovered, so there is a geo lead but not a stable coordinate anchor."
    else:
        ladder.append("2. Visible URL / coordinate text — no stable coordinates parsed.")
        ladder.append("3. OCR place labels — no reliable venue/label clue recovered.")
        primary_issue = "No native GPS and no reliable screenshot-derived geo clue were recovered."

    ladder.append(f"4. Source posture — {record.source_type} / {record.source_subtype}.")
    if record.source_type in EXPORT_LIKE:
        ladder.append("5. Analyst action — missing GPS may be normal for screenshot/export media; pivot to OCR, URLs, timeline, and source application context.")
    else:
        ladder.append("5. Analyst action — request the original acquisition file or upstream cloud copy to determine whether GPS was stripped during export.")
    return {"ladder": ladder, "primary_issue": primary_issue}


def build_score_explainability(record: EvidenceRecord) -> Dict[str, str]:
    main_issue = "No single dominant red flag was identified."
    why = record.metadata_issue_summary or (record.anomaly_reasons[0] if record.anomaly_reasons else "The file currently looks low-risk but still needs context.")
    next_step = "Preserve hashes and use surrounding evidence to corroborate time, origin, and context."

    if record.parser_status == "Failed":
        main_issue = "Parser failure / malformed media"
        why = record.parse_error or "The primary parser could not decode the media cleanly."
        next_step = "Validate the file with a second parser before making content or metadata claims."
    elif record.signature_status == "Mismatch":
        main_issue = "Signature mismatch"
        why = "The extension and internal signature disagree, which is stronger than a cosmetic naming issue."
        next_step = "Compare the staged copy with the original, then inspect the file header and magic bytes manually."
    elif record.hidden_code_indicators:
        main_issue = "Embedded code/payload markers"
        why = record.hidden_code_summary
        next_step = "Inspect the carved or suspicious payload region separately and document whether it is benign or intentional content embedding."
    elif record.hidden_suspicious_embeds:
        main_issue = "Hidden-content structural warning"
        why = record.hidden_code_summary
        next_step = "Review the suspicious appended/encoded region and explain whether it is packaging noise, derivative export data, or a true embedded payload."
    elif record.time_conflicts:
        main_issue = "Time-anchor conflict"
        why = "Multiple time candidates disagree, so chronology should remain conservative."
        next_step = "Cross-check filename, visible time, filesystem time, and external logs before claiming sequence or recency."
    elif record.duplicate_group:
        main_issue = f"{record.duplicate_relation or 'Duplicate/derivative'} linkage"
        why = record.similarity_note
        next_step = "Compare this file against its closest peer to separate original capture, repost, crop, or edited derivative."
    elif not record.exif and record.source_type not in EXPORT_LIKE:
        main_issue = "Missing embedded metadata"
        why = record.metadata_issue_summary
        next_step = "Recover the upstream original if possible and validate the acquisition workflow."
    elif not record.has_gps and record.derived_geo_display != "Unavailable":
        main_issue = "Derived geo only"
        why = record.gps_primary_issue
        next_step = "Treat the location as contextual support until a URL, browser history, or original file confirms it."
    elif record.software not in {"N/A", "Unknown", ""} and any(term in record.software.lower() for term in ["photoshop", "lightroom", "snapseed", "gimp", "canva"]):
        main_issue = "Edited/exported workflow"
        why = f"Software tag '{record.software}' indicates the file likely passed through an editing/export chain."
        next_step = "Explain the edit history and preserve both derivative and upstream versions."
    elif record.risk_level == "Low":
        main_issue = "Low-risk supporting artifact"
        why = "The file does not currently show a dominant structural or provenance red flag."
        next_step = "Use it to support timeline, source, or scene reasoning alongside stronger anchors."

    summary = f"Main issue: {main_issue}. Why: {why} Next step: {next_step}"
    return {
        "primary_issue": main_issue,
        "reason": why,
        "next_step": next_step,
        "summary": summary,
    }


def apply_explainability(record: EvidenceRecord) -> EvidenceRecord:
    metadata = build_metadata_issue_bundle(record)
    gps = build_gps_verification_ladder(record)
    score = build_score_explainability(record)
    record.metadata_issues = list(metadata["issues"])
    record.metadata_strengths = list(metadata["strengths"])
    record.metadata_recommendations = list(metadata["recommendations"])
    record.metadata_issue_summary = str(metadata["summary"])
    record.gps_ladder = list(gps["ladder"])
    record.gps_primary_issue = str(gps["primary_issue"])
    record.score_primary_issue = str(score["primary_issue"])
    record.score_reason = str(score["reason"])
    record.score_next_step = str(score["next_step"])
    record.score_summary = str(score["summary"])
    return record
