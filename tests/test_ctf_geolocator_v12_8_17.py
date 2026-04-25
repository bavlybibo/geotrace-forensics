from __future__ import annotations

from types import SimpleNamespace

from app.core.osint.ctf_geolocator import build_ctf_geo_profile
from app.core.osint.map_url_parser import parse_map_url_signals


def _record(**overrides):
    defaults = dict(
        evidence_id="EV-CTF-001",
        file_name="unknown.png",
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
        osint_visual_cues=[],
        osint_content_tags=[],
        osint_content_confidence=0,
        map_intelligence_reasons=[],
        filename_location_hints=[],
        place_candidate_rankings=[],
        place_candidates=[],
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_google_maps_url_with_coordinates_does_not_emit_redundant_provider_signal():
    url = "https://www.google.com/maps/@30.0444,31.2357,15z"
    signals = parse_map_url_signals([url], source="test")

    assert len(signals) == 1
    assert signals[0].provider == "Google Maps"
    assert signals[0].coordinates == (30.0444, 31.2357)


def test_filename_only_hint_stays_weak_and_never_becomes_strong_candidate():
    profile = build_ctf_geo_profile(
        _record(file_name="cairo_scene.jpg", filename_location_hints=["Cairo"]),
        map_signals=[],
    )

    assert profile.candidates
    top = profile.candidates[0]
    assert top.level == "filename_hint"
    assert top.evidence_strength == "weak_signal"
    assert top.confidence <= 35
    assert profile.solvability_score <= 35


def test_ocr_place_candidate_outranks_filename_hint():
    profile = build_ctf_geo_profile(
        _record(
            file_name="cairo_scene.jpg",
            filename_location_hints=["Cairo"],
            ocr_map_labels=["Stanley Bridge"],
            visible_location_strings=["Alexandria Corniche"],
            place_candidate_rankings=["Stanley Bridge — 82% — landmark:known-landmark+ocr/text"],
            ocr_confidence=87,
        ),
        map_signals=[],
    )

    assert profile.candidates[0].name == "Stanley Bridge"
    assert profile.candidates[0].evidence_strength == "lead"
    assert any(c.level == "filename_hint" and c.name == "Cairo" for c in profile.candidates)


def test_geo_candidate_priority_is_gps_then_ocr_then_visual_then_filename():
    profile = build_ctf_geo_profile(
        _record(
            has_gps=True,
            gps_display="30.044400, 31.235700",
            gps_confidence=92,
            ocr_map_labels=["Cairo Tower"],
            place_candidate_rankings=["Cairo Tower — 78% — landmark:known-landmark+ocr/text"],
            osint_visual_cues=["tower skyline visual cue"],
            osint_content_confidence=56,
            filename_location_hints=["Giza"],
        ),
        map_signals=[],
    )

    ordered_levels = [candidate.level for candidate in profile.candidates]
    assert ordered_levels[0] == "coordinates"
    assert profile.candidates[0].evidence_strength == "proof"
    assert ordered_levels.index("poi") < ordered_levels.index("visual_context")
    assert ordered_levels.index("visual_context") < ordered_levels.index("filename_hint")
    assert profile.solvability_score >= 90
