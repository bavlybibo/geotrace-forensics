from __future__ import annotations

from types import SimpleNamespace

from app.core.osint.country_region import classify_country_region
from app.core.osint.image_existence import build_image_existence_profile
from app.core.osint.ocr_search import generate_search_queries


def test_ocr_query_builder_v2_handles_arabic_phone_coordinates_and_domain():
    queries = generate_search_queries(
        ocr_phrases=["شارع التحرير 01012345678", "30.0444,31.2357", "example.eg"],
        map_labels=["Stanley Bridge"],
        candidates=["Alexandria Corniche"],
        region_profile="Egypt / Arabic-speaking region",
        limit=16,
    )

    joined = "\n".join(queries)
    assert '"شارع التحرير 01012345678" "خرائط"' in joined
    assert '"01012345678"' in joined
    assert "30.0444,31.2357" in joined
    assert '"example.eg"' in joined
    assert '"Stanley Bridge" "Egypt"' in joined


def test_country_region_classifier_prefers_egypt_for_arabic_egypt_clues():
    region, score, reasons = classify_country_region(["شارع التحرير القاهرة", "+201012345678", "example.eg"])

    assert region.startswith("Egypt")
    assert score >= 70
    assert reasons


def test_image_existence_profile_is_local_and_privacy_safe():
    record = SimpleNamespace(
        working_copy_path="missing.png",
        file_path="missing.png",
        duplicate_group="grp-1",
        similarity_note="near duplicate detected",
        perceptual_hash="abcdef",
        sha256="1234567890abcdef1234",
    )

    profile = build_image_existence_profile(record, [{"name": "Cairo Tower", "confidence": 72}])

    assert profile["exact_duplicate_in_case"] is True
    assert profile["near_duplicate_in_case"] is True
    assert profile["known_landmark_match"] is True
    assert profile["reverse_search_status"].startswith("Not performed")
