from types import SimpleNamespace

from app.core.image_risk_ai import assess_image_threat


def _pixel(score=0, lsb=None, alpha=None):
    return SimpleNamespace(score=score, lsb_strings=lsb or [], alpha_findings=alpha or [], indicators=[], metrics={})


def test_single_sensor_isolate_does_not_become_critical_100():
    verdict = assess_image_threat(
        embedded_scan={"code_indicators": ["powershell -enc AAAA"]},
        pixel_profile=_pixel(),
        visible={"lines": [], "raw_text": ""},
        basic={"parser_status": "Valid", "signature_status": "Matched", "format_trust": "Verified"},
        digital_verdict={"final_call": "ISOLATE", "risk_score": 99, "confidence_score": 100, "danger_zones": ["engine signal"]},
    )
    assert verdict.label != "CRITICAL"
    assert verdict.confidence <= 92
    assert any("critical cap" in item.lower() for item in verdict.calibration_notes)
    assert verdict.technical_threat in {"Medium", "High"}


def test_privacy_location_dimensions_are_separate_from_technical_danger():
    verdict = assess_image_threat(
        embedded_scan={},
        pixel_profile=_pixel(),
        visible={"lines": ["30.0444, 31.2357 phone +201001234567"], "raw_text": "30.0444, 31.2357 phone +201001234567"},
        basic={"parser_status": "Valid", "signature_status": "Matched", "format_trust": "Verified"},
        digital_verdict={"final_call": "CLEAR", "risk_score": 0, "confidence_score": 85},
        context={"has_gps": True, "gps_display": "30.0444, 31.2357"},
    )
    assert verdict.is_dangerous is False
    assert verdict.technical_threat == "Low"
    assert verdict.privacy_exposure == "High"
    assert verdict.geo_sensitivity == "High"
