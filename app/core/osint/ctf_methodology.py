from __future__ import annotations

"""CTF/OSINT investigation methodology layer.

This module turns the already extracted GeoTrace signals into a repeatable hacker/
researcher workflow. It is intentionally conservative: it grades readiness and
source independence instead of pretending a visual guess is proof.
"""

from typing import Any, Iterable


def _value(record: Any, name: str, default: Any = None) -> Any:
    return getattr(record, name, default)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except Exception:
        return default


def _as_list(value: Any) -> list[Any]:
    return list(value or []) if isinstance(value, (list, tuple, set)) else ([] if value in (None, "") else [value])


def _candidate_sources(candidates: Iterable[dict[str, Any]]) -> set[str]:
    sources: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        for basis in _as_list(candidate.get("basis", [])):
            text = str(basis or "").lower()
            if "gps" in text:
                sources.add("native_gps")
            elif "map-url" in text or "coordinate" in text:
                sources.add("map_or_visible_coordinates")
            elif "ocr" in text or "label" in text or "text" in text:
                sources.add("ocr_visible_text")
            elif "landmark" in text or "dataset" in text:
                sources.add("offline_landmark_match")
            elif "country" in text or "region" in text:
                sources.add("country_region_classifier")
            elif "filename" in text:
                sources.add("filename_hint")
            else:
                sources.add(text[:40] or "other")
    return sources


def _readiness_label(score: int, blocker_count: int) -> str:
    if blocker_count and score < 70:
        return "Not answer-ready"
    if score >= 85:
        return "Challenge-ready"
    if score >= 70:
        return "Answer-ready with manual verification"
    if score >= 45:
        return "Promising lead"
    return "Recon only"


def build_ctf_methodology(record: Any) -> dict[str, Any]:
    """Build a structured methodology card for one evidence item.

    The score is not a truth score. It is an operational readiness score based on
    source hierarchy, independence, and known blockers/noise.
    """
    candidates = [c for c in _as_list(_value(record, "geo_candidates", [])) if isinstance(c, dict)]
    active_candidates = [c for c in candidates if str(c.get("status", "needs_review")) != "rejected"]
    verified_candidates = [c for c in candidates if str(c.get("status", "")) == "verified"]
    clues = [c for c in _as_list(_value(record, "ctf_clues", [])) if isinstance(c, dict)]
    sources = _candidate_sources(active_candidates)

    has_gps = bool(_value(record, "has_gps", False)) or str(_value(record, "gps_display", "Unavailable")) != "Unavailable"
    has_derived_coordinate = str(_value(record, "derived_geo_display", "Unavailable")) != "Unavailable"
    has_map_url_or_coord = any("map" in str(c.get("source", "")).lower() or "coordinate" in str(c.get("source", "")).lower() for c in clues)
    has_ocr = _as_int(_value(record, "ocr_confidence", 0)) > 0 or bool(_as_list(_value(record, "ocr_map_labels", [])))
    has_visual = bool(_as_list(_value(record, "osint_visual_cues", []))) or bool(_value(record, "ctf_visual_clue_profile", {}))
    attention_regions = _as_list(_value(record, "image_attention_regions", []))
    image_methodology = _as_list(_value(record, "image_analysis_methodology", []))
    scene_descriptors = _as_list(_value(record, "image_scene_descriptors", []))
    has_deep_visual = bool(_as_list(_value(record, "image_layout_hints", [])) or _as_list(_value(record, "image_object_hints", [])) or attention_regions or scene_descriptors)
    pixel_score = _as_int(_value(record, "pixel_hidden_score", 0))
    pixel_verdict = str(_value(record, "pixel_hidden_verdict", "Not evaluated") or "Not evaluated")
    map_answer_readiness = _as_int(_value(record, "map_answer_readiness_score", 0))
    map_answer_label = str(_value(record, "map_answer_readiness_label", "Not answer-ready") or "Not answer-ready")
    best_candidate_conf = max([_as_int(c.get("confidence", 0)) for c in active_candidates], default=0)
    solvability = _as_int(_value(record, "location_solvability_score", 0))

    score = max(solvability, best_candidate_conf, map_answer_readiness)
    if has_gps:
        score = max(score, 90)
    elif has_derived_coordinate or has_map_url_or_coord:
        score = max(score, 78)
    if len(sources - {"filename_hint"}) >= 2 and best_candidate_conf >= 50:
        score = min(100, score + 8)
    if has_deep_visual and (has_ocr or has_map_url_or_coord) and best_candidate_conf >= 45:
        score = min(100, score + 4)
    if verified_candidates:
        score = min(100, max(score, 82) + 6)
    if pixel_score >= 70:
        score = min(100, score + 5)
    if active_candidates and all(str(c.get("level", "")) in {"filename_hint", "visual_context"} for c in active_candidates):
        score = min(score, 38)

    blockers: list[str] = []
    if not active_candidates:
        blockers.append("No active candidate after filtering rejected/noisy leads.")
    if not (has_gps or has_derived_coordinate or has_map_url_or_coord or has_ocr):
        blockers.append("No hard location anchor: GPS, visible coordinates, map URL, or OCR label missing.")
    if active_candidates and len(sources - {"filename_hint"}) < 2 and not has_gps:
        blockers.append("Only one independent source family supports the lead; needs corroboration.")
    if any(str(c.get("level", "")) == "filename_hint" for c in active_candidates) and not (has_ocr or has_map_url_or_coord or has_gps):
        blockers.append("Filename hints are present but are not proof.")

    phases = [
        {
            "phase": "1. Evidence intake",
            "status": "done" if str(_value(record, "sha256", "")) else "needs_review",
            "signals": [
                f"SHA-256: {str(_value(record, 'sha256', 'missing'))[:16]}…" if str(_value(record, "sha256", "")) else "No hash recorded",
                f"Dimensions: {_value(record, 'dimensions', 'Unknown')}",
                f"Source type: {_value(record, 'source_type', 'Unknown')}",
            ],
        },
        {
            "phase": "2. Hidden-content triage",
            "status": "review" if pixel_score >= 45 else "ok",
            "signals": [
                f"Pixel hidden-content score: {pixel_score}% ({pixel_verdict})",
                *[str(x) for x in _as_list(_value(record, "pixel_hidden_indicators", []))[:3]],
            ],
        },
        {
            "phase": "3. Hard anchors first",
            "status": "strong" if (has_gps or has_derived_coordinate or has_map_url_or_coord) else "missing",
            "signals": [
                f"GPS: {_value(record, 'gps_display', 'Unavailable')}",
                f"Derived/visible coordinates: {_value(record, 'derived_geo_display', 'Unavailable')}",
                f"Map URL / coordinate clues: {'yes' if has_map_url_or_coord else 'no'}",
                f"Map answer readiness: {map_answer_label} ({map_answer_readiness}%)",
            ],
        },
        {
            "phase": "4. OCR + visual narrowing",
            "status": "usable" if has_ocr or has_visual or has_deep_visual else "missing",
            "signals": [
                f"OCR confidence: {_as_int(_value(record, 'ocr_confidence', 0))}%",
                f"Map labels: {', '.join(str(x) for x in _as_list(_value(record, 'ocr_map_labels', []))[:4]) or 'none'}",
                f"Visual cues: {', '.join(str(x) for x in _as_list(_value(record, 'osint_visual_cues', []))[:3]) or 'none'}",
                f"Deep image cues: {', '.join(str(x) for x in (_as_list(_value(record, 'image_layout_hints', [])) + _as_list(_value(record, 'image_object_hints', [])))[:4]) or 'none'}",
            ],
        },
        {
            "phase": "4b. Pixel/object/detail review",
            "status": "usable" if has_deep_visual else "missing",
            "signals": [
                f"Image profile: {_value(record, 'image_detail_label', 'Unavailable')} ({_as_int(_value(record, 'image_detail_confidence', 0))}%)",
                f"Quality flags: {', '.join(str(x) for x in _as_list(_value(record, 'image_quality_flags', []))[:3]) or 'none'}",
                f"Object hints: {', '.join(str(x) for x in _as_list(_value(record, 'image_object_hints', []))[:3]) or 'none'}",
                f"Attention regions: {', '.join(str((x or {}).get('region', '?')) for x in attention_regions[:3] if isinstance(x, dict)) or 'none'}",
                f"Scene descriptors: {' | '.join(str(x) for x in scene_descriptors[:2]) or 'none'}",
                f"Methodology: {' | '.join(str(x) for x in image_methodology[:2]) or 'none'}",
            ],
        },
        {
            "phase": "5. Candidate validation",
            "status": "ready" if active_candidates and not blockers and map_answer_readiness >= 50 else "needs_review",
            "signals": [
                f"Active candidates: {len(active_candidates)} / total {len(candidates)}",
                f"Independent source families: {len(sources - {'filename_hint'})}",
                f"Verified candidates: {len(verified_candidates)}",
                f"Final-answer posture: {map_answer_label}",
            ],
        },
    ]

    next_actions: list[str] = []
    if pixel_score >= 45:
        next_actions.append("Run dedicated steganography review before treating the image as visually clean.")
    if map_answer_readiness < 50:
        next_actions.append("Do not submit a final location answer yet; extract OCR labels, coordinates, share URL, GPS, or landmark proof first.")
    if not has_ocr:
        next_actions.append("Run map_deep OCR or manual crop OCR on signs, map labels, URLs, and small text.")
    if not has_deep_visual:
        next_actions.append("Regenerate deep image intelligence after import/rescan to guide crop priority and visual verification.")
    if active_candidates and len(sources - {"filename_hint"}) < 2 and not has_gps:
        next_actions.append("Corroborate the top candidate with a second independent source family before final answer.")
    if active_candidates and not verified_candidates:
        next_actions.append("Mark the strongest candidate verified/rejected after manual researcher review.")
    if not next_actions:
        next_actions.append("Export writeup with strongest evidence, limitations, and privacy note.")

    score = max(0, min(100, int(score)))
    return {
        "evidence_id": str(_value(record, "evidence_id", "EV")),
        "readiness_score": score,
        "readiness_label": _readiness_label(score, len(blockers)),
        "map_answer_readiness": map_answer_readiness,
        "map_answer_label": map_answer_label,
        "source_families": sorted(sources),
        "blockers": blockers,
        "phases": phases,
        "next_actions": next_actions[:6],
    }


def render_ctf_methodology_text(records: Iterable[Any], limit: int = 8) -> str:
    blocks: list[str] = []
    for record in list(records or [])[:limit]:
        card = build_ctf_methodology(record)
        blocks.append(
            f"{card['evidence_id']}: {card['readiness_label']} ({card['readiness_score']}%)"
        )
        if card.get("source_families"):
            blocks.append(f"  Source families: {', '.join(card['source_families'])}")
        blockers = card.get("blockers", []) or []
        if blockers:
            blocks.append("  Blockers:")
            blocks.extend(f"  - {item}" for item in blockers[:4])
        blocks.append("  Methodology phases:")
        for phase in card.get("phases", [])[:6]:
            blocks.append(f"  - {phase.get('phase')}: {phase.get('status')}")
            for signal in (phase.get("signals", []) or [])[:2]:
                if signal:
                    blocks.append(f"      • {signal}")
        actions = card.get("next_actions", []) or []
        if actions:
            blocks.append("  Next actions:")
            blocks.extend(f"  - {item}" for item in actions[:4])
        blocks.append("")
    return "\n".join(blocks).strip() or "No evidence has been analyzed for OSINT/CTF methodology yet."
