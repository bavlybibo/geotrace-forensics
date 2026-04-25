from __future__ import annotations

"""CTF GeoLocator engine owned by the OSINT layer.

The goal is not to magically identify an image location. It turns already-acquired
metadata, OCR, map URLs, visible labels, visual tags, and local landmark data into
ranked clues, manual search pivots, and a conservative solvability score.
"""

from pathlib import Path
from typing import Any, Iterable

from .country_region import classify_country_region
from .image_existence import build_image_existence_profile
from .local_landmarks import match_local_landmarks
from .online_privacy import build_online_search_privacy_gate
from .map_url_parser import MapURLSignal
from .models import CTFClue, CTFGeoProfile, GeoCandidate
from .ocr_search import generate_search_queries


def _value(record: Any, name: str, default: Any = None) -> Any:
    return getattr(record, name, default)


def _as_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item or "").strip()]
    if value:
        return [str(value)]
    return []


def _unique(items: Iterable[str], limit: int = 12) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in items:
        value = " ".join(str(raw or "").split()).strip(" -:|•·,.;")
        if not value or value.lower() in {"unknown", "unavailable", "none", "n/a"}:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
        if len(out) >= limit:
            break
    return out




def _semantic_visual_key(value: str) -> str:
    text = str(value or "").lower()
    if any(token in text for token in ("route", "line", "overlay", "blue/purple", "blue route")):
        return "route-overlay"
    if any(token in text for token in ("green", "park", "outdoor", "map-region")):
        return "green-map-regions"
    if any(token in text for token in ("tiled-map", "map canvas", "canvas", "google maps-like")):
        return "map-canvas"
    if any(token in text for token in ("english", "latin", "arabic", "visible text")):
        return "language-text"
    if any(token in text for token in ("low-detail", "flat exported", "screenshot", "exported image")):
        return "screenshot-flat-image"
    return " ".join(text.split())[:60]


def _dedupe_visual_clues(items: Iterable[str], limit: int = 8) -> list[str]:
    canonical = {
        "route-overlay": "Route overlay / blue path detected",
        "green-map-regions": "Green/park map regions detected",
        "map-canvas": "Light tiled map canvas detected",
        "language-text": "Visible language/text cue detected",
        "screenshot-flat-image": "Flat screenshot/exported-image profile",
    }
    out: list[str] = []
    seen: set[str] = set()
    for item in _unique(items, limit=30):
        key = _semantic_visual_key(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(canonical.get(key, item))
        if len(out) >= limit:
            break
    return out


def _active_candidates(candidates: Iterable[GeoCandidate]) -> list[GeoCandidate]:
    return [candidate for candidate in candidates if getattr(candidate, "status", "needs_review") != "rejected"]


def _has_stable_location_anchor(candidates: Iterable[GeoCandidate], clues: Iterable[CTFClue]) -> bool:
    stable_levels = {"coordinates", "poi", "area", "city", "country", "place"}
    stable_sources = ("native-gps", "visible-coordinate", "map-url", "ocr-visible-text", "country-region", "local-landmark")
    for candidate in candidates:
        if candidate.level in stable_levels and candidate.evidence_strength in {"proof", "lead"} and candidate.confidence >= 45:
            return True
    for clue in clues:
        if clue.clue_type in {"metadata", "map", "text", "country", "landmark"} and clue.confidence >= 45:
            if any(token in clue.source for token in stable_sources):
                return True
    return False


def _is_visual_only_context(candidates: Iterable[GeoCandidate], clues: Iterable[CTFClue]) -> bool:
    candidates = list(candidates)
    clues = list(clues)
    if not candidates and not clues:
        return False
    if _has_stable_location_anchor(candidates, clues):
        return False
    candidate_levels = {candidate.level for candidate in candidates}
    clue_types = {clue.clue_type for clue in clues}
    return candidate_levels.issubset({"visual_context", "filename_hint"}) and clue_types.issubset({"visual", "filename"})


def _candidate_level(category: str) -> str:
    category = str(category or "").lower()
    if "coordinate" in category:
        return "coordinates"
    if "landmark" in category or "poi" in category:
        return "poi"
    if "area" in category:
        return "area"
    if "city" in category:
        return "city"
    if "country" in category or "region" in category:
        return "country"
    if "filename" in category:
        return "filename_hint"
    return "place"


def _strength_for_candidate(*, source: str, confidence: int, has_gps: bool = False) -> str:
    source = source.lower()
    if has_gps and confidence >= 80:
        return "proof"
    if "filename" in source:
        return "weak_signal"
    if confidence >= 75 and any(token in source for token in ("gps", "map-url", "ocr", "landmark", "known", "coordinate")):
        return "lead"
    if confidence >= 55:
        return "lead"
    return "weak_signal"


def _score_to_label(score: int, *, candidates: Iterable[GeoCandidate] = (), clues: Iterable[CTFClue] = ()) -> str:
    candidates = list(candidates or [])
    clues = list(clues or [])
    if _is_visual_only_context(candidates, clues):
        return "Map context only — no stable location"
    if score >= 90:
        return "Exact/near-exact location anchor"
    if score >= 75:
        return "Strong POI or coordinate lead"
    if score >= 55:
        return "Likely city/area lead"
    if score >= 30:
        return "Weak regional clue"
    return "No useful geo clue"


def _parse_rank_label(label: str) -> tuple[str, int, str]:
    parts = [part.strip() for part in str(label or "").split("—")]
    if not parts:
        return "", 0, "candidate"
    place = parts[0]
    score = 0
    if len(parts) > 1:
        try:
            score = int(parts[1].replace("%", "").strip())
        except Exception:
            score = 0
    category = parts[2] if len(parts) > 2 else "candidate"
    return place, score, category


def build_ctf_geo_profile(record: Any, map_signals: Iterable[MapURLSignal] = ()) -> CTFGeoProfile:
    map_signals = list(map_signals)
    clues: list[CTFClue] = []
    candidates: list[GeoCandidate] = []

    has_gps = bool(_value(record, "has_gps", False))
    gps_display = str(_value(record, "gps_display", "Unavailable") or "Unavailable")
    gps_confidence = int(_value(record, "gps_confidence", 0) or 0)
    if has_gps and gps_display != "Unavailable":
        clues.append(
            CTFClue(
                clue_type="metadata",
                value=gps_display,
                source="native-gps",
                confidence=max(80, gps_confidence),
                evidence_strength="proof",
                why_it_matters="Native GPS is the strongest location anchor and outranks OCR, visual, and filename hints.",
            )
        )
        candidates.append(
            GeoCandidate(
                level="coordinates",
                name=gps_display,
                confidence=max(85, gps_confidence),
                evidence_strength="proof",
                basis=["native-gps", str(_value(record, "gps_source", "GPS metadata"))],
                limitations=["Still validate custody, parser output, and timestamp context."],
                next_actions=["Verify coordinates against device timeline and source acquisition notes."],
            )
        )

    derived_display = str(_value(record, "derived_geo_display", "Unavailable") or "Unavailable")
    derived_conf = int(_value(record, "derived_geo_confidence", 0) or 0)
    if derived_display != "Unavailable":
        clues.append(
            CTFClue(
                clue_type="map",
                value=derived_display,
                source="visible-coordinate",
                confidence=derived_conf,
                evidence_strength="lead",
                why_it_matters="A visible coordinate can solve a CTF image but proves displayed context, not device presence, unless corroborated.",
            )
        )
        candidates.append(
            GeoCandidate(
                level="coordinates",
                name=derived_display,
                confidence=max(70, min(92, derived_conf or 80)),
                evidence_strength="lead",
                basis=["derived-coordinate", str(_value(record, "derived_geo_source", "visible map/OCR"))],
                limitations=["Displayed/searched location only unless source-app history validates it."],
                next_actions=["Open the coordinate in a controlled map review and compare visible landmarks/labels."],
            )
        )

    for signal in map_signals:
        if signal.coordinates:
            name = f"{signal.coordinates[0]:.6f}, {signal.coordinates[1]:.6f}"
            clues.append(
                CTFClue("map", name, signal.provider, signal.confidence, "lead", "Parsed coordinate/map URL can be a direct CTF pivot.")
            )
            candidates.append(
                GeoCandidate(
                    level="coordinates",
                    name=name,
                    confidence=max(82, signal.confidence),
                    evidence_strength="lead",
                    basis=["map-url", signal.provider],
                    limitations=["Visible/share URL proves displayed context only until corroborated."],
                    next_actions=["Preserve the raw URL and verify the coordinates manually."],
                )
            )
        elif signal.place_name != "Unavailable":
            clues.append(CTFClue("map", signal.place_name, signal.provider, signal.confidence, "lead", "Map URL place names can identify a displayed POI."))
            candidates.append(
                GeoCandidate(
                    level="poi",
                    name=signal.place_name,
                    confidence=max(72, signal.confidence),
                    evidence_strength="lead",
                    basis=["map-url-place", signal.provider],
                    limitations=["Displayed location only unless tied to source history."],
                    next_actions=["Search/verify this exact place name on an authorised map source."],
                )
            )

    text_clues = _unique(
        [
            *_as_list(_value(record, "ocr_map_labels", [])),
            *_as_list(_value(record, "visible_location_strings", [])),
            *_as_list(_value(record, "ocr_location_entities", [])),
            *_as_list(_value(record, "visible_text_lines", []))[:6],
        ],
        limit=12,
    )
    for text in text_clues[:10]:
        clues.append(
            CTFClue(
                clue_type="text",
                value=text,
                source="ocr-visible-text",
                confidence=max(55, int(_value(record, "ocr_confidence", 0) or 0)),
                evidence_strength="lead",
                why_it_matters="Visible text/signage/map labels are strong CTF search pivots when manually verified.",
            )
        )

    stable_anchor_before_visual = bool(
        has_gps
        or derived_display != "Unavailable"
        or any(signal.coordinates or signal.place_name != "Unavailable" for signal in map_signals)
        or text_clues
        or _as_list(_value(record, "place_candidate_rankings", []))
    )
    visual_clues = _dedupe_visual_clues(
        [
            *_as_list(_value(record, "osint_visual_cues", [])),
            *_as_list(_value(record, "osint_content_tags", [])),
            *_as_list(_value(record, "map_intelligence_reasons", []))[:6],
        ],
        limit=8,
    )
    visual_cap = 58 if stable_anchor_before_visual else 38
    visual_confidence = max(28, min(visual_cap, int(_value(record, "osint_content_confidence", 0) or 0)))
    for clue in visual_clues[:8]:
        clues.append(
            CTFClue(
                clue_type="visual",
                value=clue,
                source="local-visual-heuristics",
                confidence=visual_confidence,
                evidence_strength="weak_signal",
                why_it_matters="Visual cues help narrow the search space but should not be treated as exact location proof.",
            )
        )
    if visual_clues:
        candidates.append(
            GeoCandidate(
                level="visual_context",
                name=visual_clues[0],
                confidence=visual_confidence,
                evidence_strength="weak_signal",
                basis=["local-visual-heuristics"],
                limitations=["Visual context alone does not identify an exact place."],
                next_actions=["Use OCR, map labels, GPS, or landmark matches to turn this into a place candidate."],
            )
        )

    filename_hints = _unique(_as_list(_value(record, "filename_location_hints", [])), limit=6)
    # Fallback for old records imported before the separated filename field existed.
    if not filename_hints:
        filename = str(_value(record, "file_name", "") or "")
        lower = filename.lower()
        if "cairo" in lower or "القاهرة" in lower or "القاهره" in lower:
            filename_hints.append("Cairo")
        if "giza" in lower or "الجيزة" in lower or "جيزة" in lower:
            filename_hints.append("Giza")
        if "alexandria" in lower or "اسكندرية" in lower or "الإسكندرية" in lower:
            filename_hints.append("Alexandria")
    for hint in filename_hints:
        clues.append(
            CTFClue(
                clue_type="filename",
                value=hint,
                source="filename-only",
                confidence=35,
                evidence_strength="weak_signal",
                why_it_matters="Filename hints can guide CTF triage but never outrank OCR, GPS, visual map, or URL evidence.",
            )
        )
        candidates.append(
            GeoCandidate(
                level="filename_hint",
                name=hint,
                confidence=35,
                evidence_strength="weak_signal",
                basis=["filename-only"],
                limitations=["Filename-only hint. Do not report as a location claim without corroboration."],
                next_actions=["Look for OCR/map/source evidence that supports or disproves this filename hint."],
            )
        )

    country_texts = [
        str(_value(record, "ocr_raw_text", "")),
        str(_value(record, "visible_text_excerpt", "")),
        *_as_list(_value(record, "visible_urls", [])),
        *_as_list(_value(record, "ocr_url_entities", [])),
        *_as_list(_value(record, "ocr_map_labels", [])),
    ]
    country, country_score, country_reasons = classify_country_region(country_texts)
    if country != "Unknown":
        clues.append(
            CTFClue(
                clue_type="country",
                value=country,
                source="country-region-classifier",
                confidence=country_score,
                evidence_strength="lead" if country_score >= 55 else "weak_signal",
                why_it_matters="Country/region classification narrows the CTF search area before exact place verification.",
            )
        )
        candidates.append(
            GeoCandidate(
                level="country",
                name=country,
                confidence=country_score,
                evidence_strength="lead" if country_score >= 55 else "weak_signal",
                basis=["country-region-classifier", *country_reasons[:3]],
                limitations=["Country/region classification is broad and needs exact-place corroboration."],
                next_actions=["Combine with OCR place labels, landmarks, and map URLs to narrow to city/area."],
            )
        )

    place_labels = _as_list(_value(record, "place_candidate_rankings", []))
    for label in place_labels[:8]:
        place, score, category = _parse_rank_label(label)
        if not place:
            continue
        candidates.append(
            GeoCandidate(
                level=_candidate_level(category),
                name=place,
                confidence=score,
                evidence_strength=_strength_for_candidate(source=category, confidence=score),
                basis=["place-ranking", category],
                limitations=["Ranked candidate from offline evidence only; manual validation required."],
                next_actions=["Verify/reject this candidate in the OSINT CTF workflow."],
            )
        )

    landmark_matches = match_local_landmarks(
        [
            str(_value(record, "ocr_raw_text", "")),
            str(_value(record, "visible_text_excerpt", "")),
            *_as_list(_value(record, "ocr_map_labels", [])),
            *_as_list(_value(record, "place_candidates", [])),
        ],
        visual_clues,
    )
    for match in landmark_matches:
        name = str(match.get("name", "Unknown landmark"))
        score = int(match.get("confidence", 0) or 0)
        candidates.append(
            GeoCandidate(
                level=str(match.get("level", "poi")),
                name=name,
                confidence=score,
                evidence_strength="lead" if score >= 60 else "weak_signal",
                basis=["local-landmark-dataset", *[str(x) for x in match.get("reasons", [])[:2]]],
                limitations=["Local landmark dataset match is offline and conservative; confirm visually/manually."],
                next_actions=["Compare the image against public photos/maps only after privacy approval."],
            )
        )

    candidates = _dedupe_candidates(candidates)
    candidates.sort(key=lambda row: _candidate_sort_key(row))
    candidates = candidates[:12]

    query_terms = [c.name for c in candidates if c.level != "filename_hint"]
    search_queries = generate_search_queries(
        ocr_phrases=text_clues,
        map_labels=_as_list(_value(record, "ocr_map_labels", [])),
        candidates=query_terms,
        region_profile=country,
        limit=12,
    )

    score = _solvability_score(record, candidates, clues)
    image_existence_profile = build_image_existence_profile(record, landmark_matches)
    online_privacy_review = build_online_search_privacy_gate(clues, candidates)
    writeup = _build_writeup(record, candidates, clues, search_queries, score, image_existence_profile, online_privacy_review)
    return CTFGeoProfile(
        clues=clues[:40],
        candidates=candidates,
        search_queries=search_queries,
        solvability_score=score,
        solvability_label=_score_to_label(score, candidates=candidates, clues=clues),
        country_region_profile=f"{country} ({country_score}%)" if country != "Unknown" else "Unknown",
        landmark_matches=landmark_matches,
        writeup=writeup,
        image_existence_profile=image_existence_profile,
        online_privacy_review=online_privacy_review,
    )


def _dedupe_candidates(candidates: Iterable[GeoCandidate]) -> list[GeoCandidate]:
    merged: dict[tuple[str, str], GeoCandidate] = {}
    for candidate in candidates:
        name = " ".join(str(candidate.name or "").split()).strip()
        if not name:
            continue
        key = (candidate.level, name.lower())
        existing = merged.get(key)
        if existing is None or candidate.confidence > existing.confidence:
            candidate.name = name
            candidate.confidence = max(0, min(100, int(candidate.confidence or 0)))
            merged[key] = candidate
            continue
        for basis in candidate.basis:
            if basis not in existing.basis:
                existing.basis.append(basis)
        for limitation in candidate.limitations:
            if limitation not in existing.limitations:
                existing.limitations.append(limitation)
        for action in candidate.next_actions:
            if action not in existing.next_actions:
                existing.next_actions.append(action)
    return list(merged.values())


def _candidate_sort_key(candidate: GeoCandidate) -> tuple[int, int, str]:
    strength_order = {"proof": 0, "lead": 1, "weak_signal": 2, "no_signal": 3}
    level_order = {"coordinates": 0, "poi": 1, "area": 2, "city": 3, "country": 4, "place": 5, "visual_context": 8, "filename_hint": 9}
    return (
        strength_order.get(candidate.evidence_strength, 5),
        level_order.get(candidate.level, 5) * 100 - int(candidate.confidence or 0),
        candidate.name.lower(),
    )


def _solvability_score(record: Any, candidates: list[GeoCandidate], clues: list[CTFClue]) -> int:
    active = _active_candidates(candidates)
    best = max([int(c.confidence or 0) for c in active], default=0)
    if any(c.evidence_strength == "proof" for c in active):
        best = max(best, 92)
    if any(c.level == "coordinates" and c.evidence_strength == "lead" for c in active):
        best = max(best, 82)
    if any(c.level in {"poi", "area"} and c.confidence >= 65 for c in active):
        best = max(best, 68)
    if any(c.clue_type == "text" and c.confidence >= 45 for c in clues):
        best = max(best, 50)
    if active and all(c.level == "filename_hint" for c in active):
        best = min(best, 35)
    if _is_visual_only_context(active, clues):
        # Visual map/color/route heuristics can detect that an image is a map, but they
        # do not identify a stable location. Keep CTF solvability deliberately low.
        best = min(best, 38)
    if not _has_stable_location_anchor(active, clues) and any(c.level == "visual_context" for c in active):
        best = min(best, 38)
    return max(0, min(100, best))


def _build_writeup(record: Any, candidates: list[GeoCandidate], clues: list[CTFClue], queries: list[str], score: int, image_existence: dict[str, Any] | None = None, privacy_gate: dict[str, Any] | None = None) -> str:
    title = f"CTF GeoLocator writeup for {_value(record, 'evidence_id', 'evidence')}"
    lines = [title, "=" * len(title), "", f"Location solvability: {_score_to_label(score, candidates=candidates, clues=clues)} ({score}%)", ""]
    lines.append("Top candidates:")
    if candidates:
        for candidate in candidates[:5]:
            lines.append(
                f"- {candidate.name} [{candidate.level}] — {candidate.confidence}% — {candidate.evidence_strength}; basis: {', '.join(candidate.basis[:4]) or 'n/a'}"
            )
    else:
        lines.append("- No stable candidate recovered.")
    lines.extend(["", "Key clues:"])
    if clues:
        for clue in clues[:8]:
            lines.append(f"- {clue.clue_type}: {clue.value} ({clue.source}, {clue.confidence}%)")
    else:
        lines.append("- No CTF clues recovered.")
    lines.extend(["", "Image existence intelligence:"])
    image_existence = image_existence or {}
    lines.append(f"- Exact duplicate in case: {image_existence.get('exact_duplicate_in_case', False)}")
    lines.append(f"- Near duplicate in case: {image_existence.get('near_duplicate_in_case', False)}")
    lines.append(f"- Known local landmark match: {image_existence.get('known_landmark_match', False)}")
    lines.append(f"- Reverse search status: {image_existence.get('reverse_search_status', 'Not performed. Manual/privacy-gated only.')}")
    lines.extend(["", "Manual search pivots:"])
    if queries:
        for query in queries[:8]:
            lines.append(f"- {query}")
    else:
        lines.append("- No search query generated yet.")
    lines.extend(
        [
            "",
            "Privacy note:",
            "- GeoTrace remains offline by default. Run reverse-image or web searches only when authorised and after privacy review.",
            f"- Online privacy gate required: {(privacy_gate or {}).get('required_before_online_search', True)}; blocked by default: {', '.join((privacy_gate or {}).get('blocked_by_default', [])) or 'automatic external lookups'}.",
        ]
    )
    return "\n".join(lines).strip()
