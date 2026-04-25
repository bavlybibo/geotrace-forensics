from __future__ import annotations

from types import SimpleNamespace

from app.core.osint import analyze_osint_signals, classify_known_places, parse_map_url_signals
from app.core.osint.entities import extract_osint_entities
from app.core.osint.hypothesis import build_location_hypotheses
from app.core.osint.models import OSINTEntity, OSINTHypothesis


def test_osint_dataclasses_are_serialisable() -> None:
    entity = OSINTEntity("@bibo_fox", "username", confidence=74)
    hypothesis = OSINTHypothesis(
        title="Visible place lead",
        claim="OCR suggests Cairo Tower.",
        strength="lead",
        confidence=82,
        basis=["ocr/text"],
    )
    assert entity.to_dict()["entity_type"] == "username"
    assert hypothesis.to_dict()["strength"] == "lead"


def test_map_url_parser_supports_google_at_geo_and_dms() -> None:
    signals = parse_map_url_signals(
        [
            "https://www.google.com/maps/@30.044420,31.235712,17z",
            "geo:30.050000,31.240000",
            "30°02'39\"N 31°14'08\"E",
        ]
    )
    coords = [signal.coordinates for signal in signals if signal.coordinates]
    assert (30.04442, 31.235712) in coords
    assert (30.05, 31.24) in coords
    assert any(abs(lat - 30.0441667) < 0.001 and abs(lon - 31.2355556) < 0.001 for lat, lon in coords)


def test_gazetteer_handles_arabic_aliases_and_false_positive_noise() -> None:
    result = classify_known_places("صورة من خرائط جوجل عند برج القاهرة بجوار النيل")
    assert result["city"] == "Cairo"
    assert "Cairo Tower" in result["landmarks"]


def test_entity_extractor_finds_common_osint_pivots() -> None:
    entities = extract_osint_entities(["Contact @bibo_fox via https://example.com/map?q=30.0,31.0 at 10:30 PM"])
    types = {entity.entity_type for entity in entities}
    assert {"username", "url", "time"}.issubset(types)


def test_structured_hypothesis_marks_map_screenshot_as_lead_not_proof() -> None:
    record = SimpleNamespace(
        has_gps=False,
        gps_display="Unavailable",
        gps_confidence=0,
        gps_source="Unavailable",
        derived_geo_display="Unavailable",
        derived_geo_confidence=0,
        derived_geo_source="Unavailable",
        map_intelligence_confidence=82,
        map_confidence=82,
        map_evidence_basis=["ocr/text", "known-place-dictionary"],
        candidate_city="Cairo",
        candidate_area="Unavailable",
        landmarks_detected=["Cairo Tower"],
        place_candidates=["Cairo Tower"],
        map_limitations=[],
        map_recommended_actions=[],
        ocr_raw_text="Google Maps Cairo Tower برج القاهرة",
        visible_text_excerpt="",
        visible_text_lines=[],
        file_name="map_cairo.png",
        visible_urls=[],
        copy_verified=True,
        integrity_status="Verified",
    )
    hypotheses = build_location_hypotheses(record)
    assert hypotheses
    assert any(item.strength == "lead" for item in hypotheses)
    assert not any(item.strength == "proof" for item in hypotheses)


def test_full_osint_pipeline_outputs_cards_entities_and_matrix() -> None:
    record = SimpleNamespace(
        evidence_id="EVID-001",
        file_name="Screenshot Map Cairo Tower.png",
        visible_text_excerpt="https://www.google.com/maps/place/Cairo+Tower/@30.0459,31.2243,17z @bibo_fox",
        ocr_raw_text="Google Maps Cairo Tower برج القاهرة",
        detected_map_context="Google Maps route context",
        map_intelligence_summary="Map intelligence v2: Google Maps; Road map.",
        osint_content_summary="OSINT map/location artifact",
        visible_text_lines=[],
        visible_urls=["https://www.google.com/maps/place/Cairo+Tower/@30.0459,31.2243,17z"],
        ocr_url_entities=[],
        visible_location_strings=[],
        ocr_location_entities=[],
        ocr_map_labels=["Cairo Tower"],
        place_candidates=["Cairo Tower"],
        landmarks_detected=["Cairo Tower"],
        has_gps=False,
        gps_display="Unavailable",
        gps_confidence=0,
        gps_source="Unavailable",
        derived_geo_display="Unavailable",
        derived_geo_confidence=0,
        derived_geo_source="Unavailable",
        map_intelligence_confidence=88,
        map_confidence=88,
        map_evidence_basis=["ocr/text", "map-url", "known-place-dictionary"],
        candidate_city="Cairo",
        candidate_area="Unavailable",
        map_limitations=[],
        map_recommended_actions=[],
        copy_verified=True,
        integrity_status="Verified",
    )
    profile = analyze_osint_signals(record)
    assert profile.entities
    assert profile.hypotheses
    assert profile.corroboration_matrix
    assert any(item.strength == "lead" for item in profile.hypotheses)
