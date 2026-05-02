from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from app.core.image_risk_ai import assess_image_threat
from app.core.map.evidence import anchor_kind_from_source, claim_policy_for_anchor
from app.core.map.intelligence import analyze_map_intelligence
from app.core.map.provider_bridge import build_map_provider_bridge
from app.core.models import EvidenceRecord


def _record(**kwargs):
    base = dict(
        case_id="case",
        case_name="case",
        evidence_id="IMG-001",
        file_path=Path("evidence.png"),
        file_name="evidence.png",
        sha256="x" * 64,
        md5="y" * 32,
        perceptual_hash="z",
        file_size=10,
        imported_at="now",
    )
    base.update(kwargs)
    return EvidenceRecord(**base)


def _pixel(score=0):
    return SimpleNamespace(score=score, lsb_strings=[], alpha_findings=[], indicators=[], metrics={})


def test_offline_geocoder_coordinate_is_review_required_not_exact_gps():
    r = _record(
        map_interactive_payload={
            "available": True,
            "latitude": 30.0444,
            "longitude": 31.2357,
            "label": "Cairo",
            "source": "offline-geocoder city centroid",
        }
    )
    bridge = build_map_provider_bridge(r)
    assert bridge.status == "approximate_place_bridge_review_required"
    assert bridge.provider_links[0].kind == "approximate_coordinate"
    assert any("do not report" in warning.lower() for warning in bridge.warnings)


def test_claim_policy_keeps_native_derived_and_approximate_separate():
    native = claim_policy_for_anchor(anchor_kind_from_source("Native EXIF GPS", has_native_gps=True, has_coordinates=True), confidence=95, source="Native EXIF GPS")
    derived = claim_policy_for_anchor(anchor_kind_from_source("visible coordinate text", has_coordinates=True), confidence=86, source="visible coordinate text")
    approx = claim_policy_for_anchor(anchor_kind_from_source("offline geocoder city centroid", has_coordinates=True), confidence=72, source="offline geocoder city centroid")
    assert native.claim_label == "Native GPS"
    assert derived.claim_label == "Derived Geo Anchor"
    assert approx.claim_label == "Map Search Lead"
    assert native.radius_m < derived.radius_m < approx.radius_m
    assert approx.radius_m >= 15000


def test_filename_map_hint_alone_does_not_become_map_screenshot(tmp_path: Path):
    path = tmp_path / "map.png"
    Image.new("RGB", (420, 260), "white").save(path)
    result = analyze_map_intelligence(path, {"lines": [], "ocr_map_labels": [], "visible_location_strings": [], "visible_urls": [], "raw_text": "", "excerpt": "", "app_names": []})
    assert result.detected is False
    assert result.confidence <= 20
    assert result.answer_readiness_label == "Not answer-ready"


def test_map_context_privacy_ai_is_not_dangerous_payload():
    map_intel = SimpleNamespace(detected=True, confidence=82, route_overlay_detected=True)
    verdict = assess_image_threat(
        embedded_scan={},
        pixel_profile=_pixel(),
        visible={"lines": ["Google Maps directions to Cairo Tower"], "raw_text": "Google Maps directions to Cairo Tower"},
        basic={"parser_status": "Valid", "signature_status": "Matched", "format_trust": "Verified"},
        digital_verdict={"final_call": "CLEAR", "risk_score": 0, "confidence_score": 80},
        map_intel=map_intel,
    )
    assert verdict.is_dangerous is False
    assert verdict.technical_threat == "Low"
    assert verdict.geo_sensitivity == "Medium"
    assert any(card["dimension"] == "Geo sensitivity" for card in verdict.risk_split_cards)
