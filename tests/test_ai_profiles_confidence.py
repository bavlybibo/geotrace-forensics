from pathlib import Path

from app.core.ai import assess_map_strength, assess_record_strength, record_confidence_profile
from app.core.ai.evidence_strength import EvidenceStrength
from app.core.models import EvidenceRecord
from app.core.ocr_modes import OCRCacheKey, normalize_ocr_mode


def make_record(**kwargs):
    base = dict(
        case_id="CASE-1",
        case_name="Case 1",
        evidence_id="EVD-001",
        file_path=Path("sample.png"),
        file_name="sample.png",
        sha256="a" * 64,
        md5="b" * 32,
        perceptual_hash="0" * 16,
        file_size=1,
        imported_at="now",
    )
    base.update(kwargs)
    return EvidenceRecord(**base)


def test_profiles_are_available_without_breaking_legacy_fields():
    record = make_record(ocr_raw_text="Cairo", ocr_confidence=80, map_intelligence_confidence=75)
    assert record.ocr_profile.raw_text == "Cairo"
    assert record.geo_profile.map_confidence == 75
    assert record.ai_profile.risk_label == "Not evaluated"


def test_native_gps_integrity_is_strong_indicator_or_better():
    record = make_record(
        integrity_status="Verified",
        parser_status="Valid",
        signature_status="Matched",
        timestamp_confidence=90,
        gps_latitude=30.0444,
        gps_longitude=31.2357,
        gps_confidence=90,
    )
    strength = assess_record_strength(record)
    assert strength.label in {EvidenceStrength.PROOF, EvidenceStrength.STRONG_INDICATOR}
    assert strength.score >= 70


def test_map_ocr_is_lead_not_proof():
    record = make_record(ocr_map_labels=["Cairo"], map_intelligence_confidence=76, map_evidence_basis=["ocr/text"])
    strength = assess_map_strength(record)
    assert strength.label == EvidenceStrength.LEAD
    assert any("lead" in item.lower() or "corroboration" in item.lower() for item in strength.limitations)


def test_confidence_profile_includes_explainable_basis():
    record = make_record(integrity_status="Verified", parser_status="Valid", signature_status="Matched", timestamp_confidence=85)
    score, basis = record_confidence_profile(record)
    assert score > 40
    assert any("integrity" in item for item in basis)


def test_ocr_mode_and_cache_key_are_stable():
    assert normalize_ocr_mode("maps") == "map_deep"
    key = OCRCacheKey(file_sha256="abc", mode="quick", force=False, language="eng+ara")
    assert key.filename().endswith(".ocr.json")
