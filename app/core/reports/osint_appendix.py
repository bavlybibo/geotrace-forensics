from __future__ import annotations

"""OSINT appendix rendering helpers.

Kept outside report_service.py so export logic can shrink gradually without a
risky rewrite. The caller provides redaction callbacks from ReportService.
"""

from datetime import datetime
from typing import Any, Callable, Iterable

from ..models import EvidenceRecord

TextFn = Callable[[str], str]
JoinFn = Callable[[Iterable[Any], int, str], str]
FileFn = Callable[[EvidenceRecord], str]


def _safe(value: Any) -> str:
    return str(value if value is not None else "")


def _dict_labels(items: Iterable[Any], template: str, limit: int = 8) -> list[str]:
    labels: list[str] = []
    for item in list(items or [])[:limit]:
        if not isinstance(item, dict):
            continue
        try:
            labels.append(template.format(**item))
        except Exception:
            labels.append(str(item))
    return labels


def build_osint_appendix_text(
    records: list[EvidenceRecord],
    *,
    case_id: str,
    case_name: str,
    privacy_level: str,
    file_name: FileFn,
    redact_text: TextFn,
    join_redacted: JoinFn,
) -> str:
    lines: list[str] = [
        "GeoTrace Forensics X — OSINT Appendix",
        f"Case ID: {case_id}",
        f"Case Name: {case_name}",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Privacy level: {privacy_level}",
        "",
        "Purpose",
        "-------",
        "This appendix separates OSINT/location leads from forensic proof. Use proof / lead / weak_signal wording and preserve corroboration notes before external sharing.",
        "",
    ]

    total_cards = sum(len(r.osint_hypothesis_cards or []) for r in records)
    total_entities = sum(len(r.osint_entities or []) for r in records)
    total_decisions = sum(len(r.osint_analyst_decisions or []) for r in records)
    total_ctf_clues = sum(len(getattr(r, "ctf_clues", []) or []) for r in records)
    max_solvability = max([int(getattr(r, "location_solvability_score", 0) or 0) for r in records], default=0)
    lines.extend(
        [
            "Case OSINT Metrics",
            "------------------",
            f"Evidence items: {len(records)}",
            f"Hypothesis cards: {total_cards}",
            f"Structured entities: {total_entities}",
            f"Analyst decisions: {total_decisions}",
            f"CTF GeoLocator clues: {total_ctf_clues}",
            f"Top location solvability: {max_solvability}%",
            "",
        ]
    )

    for record in records:
        has_osint = bool(
            record.osint_hypothesis_cards
            or record.osint_entities
            or record.place_candidate_rankings
            or record.ocr_region_signals
            or getattr(record, "ctf_clues", [])
            or getattr(record, "geo_candidates", [])
        )
        if not has_osint:
            continue

        hypothesis_labels = _dict_labels(
            record.osint_hypothesis_cards or [],
            "{title} | {strength} | {confidence}%",
            limit=8,
        )
        entity_labels = _dict_labels(record.osint_entities or [], "{entity_type}:{value}", limit=10)
        region_labels = _dict_labels(record.ocr_region_signals or [], "{region}:{weight}%", limit=8)
        decision_labels = _dict_labels(record.osint_analyst_decisions or [], "{decision} — {analyst_note}", limit=8)
        ctf_candidate_labels = _dict_labels(
            getattr(record, "geo_candidates", []) or [],
            "{name} | {level} | {confidence}% | {evidence_strength} | {status}",
            limit=8,
        )
        ctf_clue_labels = _dict_labels(getattr(record, "ctf_clues", []) or [], "{clue_type}:{value}", limit=10)

        safe_name = file_name(record)
        solvability_label = getattr(record, "location_solvability_label", "No useful geo clue")
        solvability_score = getattr(record, "location_solvability_score", 0)
        filename_hints = getattr(record, "filename_location_hints", []) or []
        image_existence = getattr(record, "ctf_image_existence_profile", {}) or {}
        online_gate = getattr(record, "ctf_online_privacy_review", {}) or {}

        lines.extend(
            [
                f"[{record.evidence_id}] {safe_name}",
                "-" * (len(record.evidence_id) + len(safe_name) + 3),
                f"Evidence strength: {_safe(record.evidence_strength_label)} ({_safe(record.evidence_strength_score)}%)",
                f"Map strength: {_safe(record.map_evidence_strength)} | map confidence: {_safe(record.map_intelligence_confidence)}%",
                f"Detected map context: {redact_text(_safe(record.detected_map_context))}",
                f"Possible place: {redact_text(_safe(record.possible_place))}",
                f"Derived geo: {redact_text(_safe(record.derived_geo_display))} ({_safe(record.derived_geo_confidence)}%)",
                f"OCR profile: {_safe(record.ocr_confidence)}% | {redact_text(_safe(record.ocr_analyst_relevance))}",
                f"CTF solvability: {_safe(solvability_label)} ({_safe(solvability_score)}%)",
                f"Filename-only hints: {join_redacted(filename_hints, 6, '[REDACTED_FILENAME_HINT]')}",
                f"Hypotheses: {join_redacted(hypothesis_labels, 8, '[REDACTED_OSINT_CARD]')}",
                f"Entities: {join_redacted(entity_labels, 10, '[REDACTED_OSINT_ENTITY]')}",
                f"Place rankings: {join_redacted(record.place_candidate_rankings or [], 8, '[REDACTED_LOCATION_RANKING]')}",
                f"CTF candidates: {join_redacted(ctf_candidate_labels, 8, '[REDACTED_CTF_CANDIDATE]')}",
                f"CTF clues: {join_redacted(ctf_clue_labels, 10, '[REDACTED_CTF_CLUE]')}",
                f"Image existence: exact_duplicate={_safe(image_existence.get('exact_duplicate_in_case', False))} | near_duplicate={_safe(image_existence.get('near_duplicate_in_case', False))} | landmark_match={_safe(image_existence.get('known_landmark_match', False))}",
                f"Map evidence ladder: {join_redacted(getattr(record, 'map_evidence_ladder', []) or [], 8, '[REDACTED_MAP_LADDER]')}",
                f"Online privacy gate: required={_safe(online_gate.get('required_before_online_search', True))} | blocked={join_redacted(online_gate.get('blocked_by_default', []), 6, '[REDACTED_ONLINE_BLOCK]')}",
                f"OCR region signals: {join_redacted(region_labels, 8, '[REDACTED_OCR_REGION]')}",
                f"Analyst decisions: {join_redacted(decision_labels, 8, '[REDACTED_ANALYST_DECISION]')}",
                "Corroboration posture: treat OSINT output as a lead unless backed by native GPS, source URL, device logs, or independent map/history evidence.",
                "",
            ]
        )

    if len(lines) <= 20:
        lines.append("No structured OSINT leads were available for this case.")
    return "\n".join(lines).strip() + "\n"
