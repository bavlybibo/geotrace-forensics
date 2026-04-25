from __future__ import annotations

from app.core.osint.analyst_decisions import default_decisions_for_hypotheses
from app.core.osint.place_ranking import rank_places
from app.core.osint.privacy_review import build_osint_privacy_review
from app.core.osint.region_ocr import classify_ocr_regions


def test_place_ranking_promotes_landmark_area_city_context():
    ranks = rank_places(
        texts=["Google Maps directions Cairo Tower Zamalek Nile"],
        explicit_candidates=["Cairo Tower", "Zamalek"],
        candidate_city="Cairo",
        candidate_area="Zamalek",
        landmarks=["Cairo Tower"],
        basis=["ocr/text", "known-place-dictionary", "route-visual"],
        ocr_confidence=82,
    )
    assert ranks
    assert ranks[0].score >= 70
    assert any(item.place == "Cairo Tower" for item in ranks)


def test_region_ocr_weights_map_search_bar_above_full_text():
    signals = classify_ocr_regions({"full": "Cairo", "map_search_bar": "Cairo Tower directions"})
    assert signals[0].region == "map_search_bar"
    assert "known-place" in signals[0].basis


def test_default_decisions_keep_leads_as_needs_review():
    decisions = default_decisions_for_hypotheses("IMG-001", [{"title": "Visible place", "strength": "lead", "confidence": 86}])
    assert decisions[0].decision == "needs_review"
    assert "corroboration" in decisions[0].analyst_note.lower()


def test_osint_privacy_review_counts_sensitive_location_pivots():
    class Record:
        osint_entities = [{"entity_type": "map_signal", "sensitivity": "location_pivot", "value": "geo:30.0,31.0"}]
        osint_hypothesis_cards = [{"strength": "lead", "confidence": 80}]
        derived_geo_display = "Unavailable"
        map_intelligence_confidence = 0

    review = build_osint_privacy_review([Record()])
    assert review["records_with_sensitive_osint"] == 1
    assert review["recommended_export_mode"] == "redacted_text"
