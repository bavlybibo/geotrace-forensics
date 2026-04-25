from __future__ import annotations

from types import SimpleNamespace

from app.core.osint.ctf_geolocator import build_ctf_geo_profile
from app.core.osint.image_existence import build_image_existence_profile


def _record(**overrides):
    defaults = dict(
        evidence_id="IMG-001",
        file_name="map_screenshot.png",
        has_gps=False,
        gps_display="Unavailable",
        gps_confidence=0,
        gps_source="Unavailable",
        derived_geo_display="Unavailable",
        derived_geo_confidence=0,
        derived_geo_source="Unavailable",
        ocr_raw_text="",
        visible_text_excerpt="",
        visible_text_lines=[],
        visible_urls=[],
        ocr_url_entities=[],
        ocr_map_labels=[],
        visible_location_strings=[],
        ocr_location_entities=[],
        osint_visual_cues=["green outdoor/map-region visual signal", "park/green map regions detected"],
        osint_content_tags=["English/Latin visible text"],
        osint_content_confidence=82,
        map_intelligence_reasons=["light tiled-map canvas detected", "blue/purple route-overlay pixels detected", "route overlay appears visually prominent"],
        filename_location_hints=[],
        place_candidate_rankings=[],
        place_candidates=[],
        working_copy_path="missing.png",
        file_path="missing.png",
        similarity_note="No near-duplicate peer was identified.",
        duplicate_group="",
        perceptual_hash="",
        sha256="",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_visual_only_map_context_score_below_40_and_label_is_not_city_area():
    profile = build_ctf_geo_profile(_record(), map_signals=[])

    assert profile.solvability_score <= 38
    assert profile.solvability_label == "Map context only — no stable location"
    assert all(c.level in {"visual_context", "filename_hint"} for c in profile.candidates)


def test_visual_clues_are_semantically_deduplicated():
    profile = build_ctf_geo_profile(_record(), map_signals=[])
    values = [clue.value for clue in profile.clues]

    assert values.count("Green/park map regions detected") == 1
    assert values.count("Route overlay / blue path detected") == 1
    assert len(values) < 8


def test_near_duplicate_negative_language_stays_false():
    record = _record(similarity_note="No near-duplicate peer was identified.", duplicate_group="")
    profile = build_image_existence_profile(record, [])

    assert profile["exact_duplicate_in_case"] is False
    assert profile["near_duplicate_in_case"] is False


def test_ocr_candidate_lifts_visual_only_score():
    profile = build_ctf_geo_profile(
        _record(
            ocr_map_labels=["Stanley Bridge"],
            place_candidate_rankings=["Stanley Bridge — 82% — landmark:known-landmark+ocr/text"],
            ocr_confidence=84,
        ),
        map_signals=[],
    )

    assert profile.solvability_score >= 68
    assert profile.solvability_label in {"Likely city/area lead", "Strong POI or coordinate lead"}
    assert profile.candidates[0].name == "Stanley Bridge"
