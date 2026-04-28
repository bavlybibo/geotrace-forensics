from __future__ import annotations

"""Common CTF image-question support helpers.

This module converts GeoTrace's CTF/OSINT state into answer-ready guidance for the
kind of image questions common in CTF/GeoGuessr challenges.

It stays conservative: it does not invent answers. Instead it maps existing signals
into clear question coverage, top answer candidates, and next-best actions.
"""

from typing import Any


def _clean(value: Any, fallback: str = "") -> str:
    text = " ".join(str(value or "").split()).strip(" -:|•·,.;")
    if not text or text.lower() in {"unknown", "unavailable", "none", "n/a", "no_signal"}:
        return fallback
    return text


def _country_pair(value: Any) -> tuple[str, int]:
    text = _clean(value)
    if not text:
        return "", 0
    if text.endswith("%)") and "(" in text:
        name, _, tail = text.rpartition("(")
        try:
            score = int(tail.replace("%)", "").strip())
        except Exception:
            score = 0
        return _clean(name), score
    return text, 0


def _active_candidates(record: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in getattr(record, "geo_candidates", []) or []:
        if isinstance(item, dict) and str(item.get("status", "needs_review")) != "rejected":
            out.append(item)
    out.sort(key=lambda row: (-int(row.get("confidence", 0) or 0), str(row.get("name", "")).lower()))
    return out


def _top_candidate(record: Any) -> dict[str, Any] | None:
    candidates = _active_candidates(record)
    return candidates[0] if candidates else None


def _question_card(question: str, status: str, answer: str = "", confidence: int = 0, why: str = "") -> dict[str, Any]:
    return {
        "question": question,
        "status": status,
        "answer": answer,
        "confidence": int(confidence or 0),
        "why": why,
    }


def build_ctf_question_support(record: Any) -> dict[str, Any]:
    top = _top_candidate(record)
    estimate_label = _clean(getattr(record, "location_estimate_label", ""))
    estimate_conf = int(getattr(record, "location_estimate_confidence", 0) or 0)
    estimate_scope = _clean(getattr(record, "location_estimate_scope", "no_signal"), "no_signal")
    estimate_tier = _clean(getattr(record, "location_estimate_source_tier", "no_signal"), "no_signal")
    country_name, country_score = _country_pair(getattr(record, "ctf_country_region_profile", "Unknown"))
    map_app = _clean(getattr(record, "map_app_detected", "Unknown"))
    map_lang = _clean(getattr(record, "map_ocr_language_hint", "Unknown"))
    search_queries = [str(item) for item in (getattr(record, "ctf_search_queries", []) or []) if _clean(item)]
    clues = [item for item in (getattr(record, "ctf_clues", []) or []) if isinstance(item, dict)]
    map_answer_readiness = int(getattr(record, "map_answer_readiness_score", 0) or 0)
    map_answer_label = _clean(getattr(record, "map_answer_readiness_label", ""), "Not answer-ready")
    hard_anchor_present = bool(
        getattr(record, "has_gps", False)
        or _clean(getattr(record, "derived_geo_display", ""))
        or any("coordinate" in str(c.get("source", "")).lower() or "map-url" in str(c.get("basis", "")).lower() for c in clues)
        or _clean(getattr(record, "candidate_city", ""))
        or _clean(getattr(record, "candidate_area", ""))
        or bool(getattr(record, "landmarks_detected", []) or [])
        or bool(getattr(record, "ocr_map_labels", []) or [])
    )

    question_cards: list[dict[str, Any]] = []

    # Exact location / coordinates.
    if estimate_scope == "exact_coordinates" and estimate_label:
        question_cards.append(
            _question_card(
                "If the challenge asks for exact coordinates",
                "supported",
                estimate_label,
                max(estimate_conf, int((top or {}).get("confidence", 0) or 0)),
                f"Source tier: {estimate_tier.replace('_', ' ')}.",
            )
        )
    else:
        question_cards.append(
            _question_card(
                "If the challenge asks for exact coordinates",
                "partial" if search_queries or top else "no_signal",
                search_queries[0] if search_queries else "No direct coordinate answer yet",
                min(60, estimate_conf),
                "Use map labels / OCR / candidate places to refine toward an exact coordinate.",
            )
        )

    # POI / landmark.
    if top and str(top.get("level", "")) in {"poi", "place", "map-url-place", "landmark"}:
        question_cards.append(
            _question_card(
                "If the challenge asks for the landmark / POI",
                "supported",
                str(top.get("name", "")),
                int(top.get("confidence", 0) or 0),
                f"Top active candidate ({top.get('evidence_strength', 'weak_signal')}).",
            )
        )
    else:
        question_cards.append(
            _question_card(
                "If the challenge asks for the landmark / POI",
                "partial" if top else "no_signal",
                str((top or {}).get("name", "No stable POI yet")),
                int((top or {}).get("confidence", 0) or 0),
                "A city/area candidate exists, but a stable landmark answer is not confirmed yet.",
            )
        )

    # City / area.
    city_area_answer = _clean(getattr(record, "candidate_area", "")) or _clean(getattr(record, "candidate_city", ""))
    if top and str(top.get("level", "")) in {"area", "city"}:
        city_area_answer = str(top.get("name", city_area_answer))
    question_cards.append(
        _question_card(
            "If the challenge asks for city / area",
            "supported" if city_area_answer else ("partial" if top else "no_signal"),
            city_area_answer or str((top or {}).get("name", "No stable city/area answer yet")),
            int((top or {}).get("confidence", 0) or estimate_conf or 0),
            "Use this when the expected flag/answer format is city, district, or area rather than exact coordinates.",
        )
    )

    # Country.
    question_cards.append(
        _question_card(
            "If the challenge asks for country / region",
            "supported" if country_name else "no_signal",
            country_name or "No stable country answer yet",
            country_score,
            "Derived from the offline country/region classifier.",
        )
    )

    # Map app.
    question_cards.append(
        _question_card(
            "If the challenge asks which map app/platform is shown",
            "supported" if map_app else "partial",
            map_app or "Map-like UI detected but app not identified",
            int(getattr(record, "map_intelligence_confidence", 0) or 0),
            "Useful for screenshot-based map CTF tasks.",
        )
    )

    # Visible language.
    question_cards.append(
        _question_card(
            "If the challenge asks about visible language / script",
            "supported" if map_lang else ("partial" if clues else "no_signal"),
            map_lang or "No stable language hint yet",
            int(getattr(record, "ocr_confidence", 0) or 0),
            "Language hints can quickly reduce the search space in CTF image tasks.",
        )
    )

    # Search pivot.
    question_cards.append(
        _question_card(
            "Best manual pivot if you need to continue solving",
            "supported" if search_queries else ("partial" if top else "no_signal"),
            search_queries[0] if search_queries else str((top or {}).get("name", "No pivot generated yet")),
            int((top or {}).get("confidence", 0) or 0),
            "Use only for authorised/manual OSINT follow-up.",
        )
    )

    top_level = str((top or {}).get("level", ""))
    top_is_visual_only = top_level in {"visual_context", "filename_hint"}
    best_answer = estimate_label or (str(top.get("name", "")) if top and not top_is_visual_only else "")
    best_conf = max(estimate_conf, int((top or {}).get("confidence", 0) or 0), country_score, map_answer_readiness)
    best_type = estimate_scope if estimate_scope != "no_signal" else str((top or {}).get("level", "country" if country_name else "no_signal"))
    if not best_answer and country_name and country_score >= 50:
        best_answer = country_name
        best_type = "country"
        best_conf = max(best_conf, country_score)
    if not best_answer or (map_answer_readiness < 50 and not hard_anchor_present):
        best_answer = "No stable answer yet"
        best_type = "needs_more_evidence"
        best_conf = min(best_conf, map_answer_readiness)
    summary = (
        f"Answer readiness: {map_answer_label} ({map_answer_readiness}%). Top answer candidate: {best_answer} ({best_conf}% confidence; {best_type.replace('_', ' ')})."
        if best_answer != "No stable answer yet"
        else f"Answer readiness: {map_answer_label} ({map_answer_readiness}%). No stable answer yet — map type/context is available, but place extraction still needs GPS, OCR labels, coordinates, map URL, or verified landmark evidence."
    )

    strongest_evidence = []
    if estimate_label:
        strongest_evidence.append(f"Location estimate: {estimate_label} ({estimate_conf}%)")
    if top:
        strongest_evidence.append(
            f"Top active candidate: {top.get('name', 'candidate')} [{top.get('level', 'level')}] ({top.get('confidence', 0)}%)"
        )
    if country_name:
        strongest_evidence.append(f"Country/region hint: {country_name} ({country_score}%)")
    if map_app:
        strongest_evidence.append(f"Map app/platform: {map_app}")
    if map_lang:
        strongest_evidence.append(f"Visible language/script: {map_lang}")

    next_actions = list(getattr(record, "location_estimate_next_actions", []) or [])
    if search_queries and not next_actions:
        next_actions.append(f"Try manual pivot: {search_queries[0]}")
    if not next_actions:
        next_actions = ["Inspect OCR labels, visible URLs, and candidate places before escalating to web pivots."]

    return {
        "summary": summary,
        "best_answer": best_answer or "No stable answer yet",
        "best_confidence": best_conf,
        "best_type": best_type,
        "map_answer_readiness": map_answer_readiness,
        "map_answer_label": map_answer_label,
        "hard_anchor_present": hard_anchor_present,
        "question_cards": question_cards,
        "strongest_evidence": strongest_evidence,
        "next_actions": next_actions[:6],
    }
