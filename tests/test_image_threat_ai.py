from types import SimpleNamespace

from app.core.image_risk_ai import assess_image_threat
from app.core.ai.engine import run_ai_batch_assessment
from app.core.models import EvidenceRecord


def _pixel(score=0, lsb=None, alpha=None):
    return SimpleNamespace(
        score=score,
        lsb_strings=lsb or [],
        alpha_findings=alpha or [],
        indicators=[],
        metrics={},
    )


def test_clean_image_is_safe_not_dangerous():
    verdict = assess_image_threat(
        embedded_scan={},
        pixel_profile=_pixel(),
        visible={"lines": ["No EXIF metadata available"], "raw_text": "No EXIF metadata available"},
        basic={"parser_status": "Valid", "signature_status": "Matched", "format_trust": "Verified"},
        digital_verdict={"final_call": "CLEAR", "risk_score": 0, "confidence_score": 75},
    )
    assert verdict.label == "SAFE"
    assert verdict.is_dangerous is False
    assert verdict.score < 15
    assert verdict.threat_family == "clean"
    assert verdict.decision_lane == "benign_or_normal_preservation"


def test_visible_code_only_is_not_marked_dangerous():
    verdict = assess_image_threat(
        embedded_scan={},
        pixel_profile=_pixel(),
        visible={"lines": ["<script>alert(1)</script>"], "raw_text": "<script>alert(1)</script>"},
        basic={"parser_status": "Valid", "signature_status": "Matched", "format_trust": "Verified"},
        digital_verdict={"final_call": "CLEAR", "risk_score": 0, "confidence_score": 70},
    )
    assert verdict.is_dangerous is False
    assert verdict.label in {"SAFE", "LOW"}
    assert verdict.technical_signal_count == 0
    assert any("Visible code" in item or "screenshot" in item for item in verdict.false_positive_guards)


def test_hidden_payload_is_dangerous():
    verdict = assess_image_threat(
        embedded_scan={
            "code_indicators": ["<script>fetch('/token')</script>"],
            "suspicious_embeds": ["extra bytes after image end"],
            "payload_markers": ["appended payload"],
            "recoverable_segments": [{"offset": 1024, "kind": "payload"}],
        },
        pixel_profile=_pixel(score=72, lsb=["api_key=abc123"]),
        visible={"lines": [], "raw_text": ""},
        basic={"parser_status": "Valid", "signature_status": "Matched", "format_trust": "Verified"},
        digital_verdict={
            "final_call": "ISOLATE",
            "risk_score": 78,
            "confidence_score": 80,
            "danger_zones": ["container / appended payload area"],
            "artifact_status": "carved_or_decoded_artifact_present",
        },
    )
    assert verdict.label in {"HIGH", "CRITICAL"}
    assert verdict.is_dangerous is True
    assert "DANGEROUS" in verdict.badge
    assert verdict.technical_signal_count >= 3
    assert verdict.decision_lane == "isolate_and_validate"
    assert verdict.contributor_matrix


def test_image_threat_ai_promotes_batch_finding():
    record = EvidenceRecord(
        case_id="case",
        case_name="case",
        evidence_id="EV-1",
        file_path="sample.png",
        file_name="sample.png",
        sha256="x",
        md5="y",
        perceptual_hash="z",
        file_size=10,
        imported_at="now",
    )
    record.image_risk_label = "HIGH"
    record.image_risk_score = 78
    record.image_risk_is_dangerous = True
    record.image_risk_primary_reason = "Recovered payload segment exists."
    record.image_risk_danger_zones = ["container / appended payload area"]
    findings = run_ai_batch_assessment([record])
    assert "image_threat_dangerous" in findings["EV-1"].flags


def test_privacy_only_location_image_is_not_dangerous():
    verdict = assess_image_threat(
        embedded_scan={},
        pixel_profile=_pixel(),
        visible={
            "lines": ["Meet me at 30.0444, 31.2357", "Phone +201001234567"],
            "ocr_map_labels": ["Cairo", "Tahrir Square"],
            "raw_text": "Cairo map screenshot with phone +201001234567",
        },
        basic={"parser_status": "Valid", "signature_status": "Matched", "format_trust": "Verified"},
        digital_verdict={"final_call": "CLEAR", "risk_score": 0, "confidence_score": 80},
        context={"has_gps": True, "gps_display": "30.0444, 31.2357"},
    )
    assert verdict.is_dangerous is False
    assert verdict.label in {"LOW", "MEDIUM"}
    assert verdict.threat_family in {"privacy_or_location_exposure", "privacy_or_weak_context_signal"}
    assert verdict.technical_signal_count == 0
    assert any("privacy" in item.lower() or "visible" in item.lower() for item in verdict.contributor_matrix)


def test_calibrated_triage_fields_for_hidden_payload():
    verdict = assess_image_threat(
        embedded_scan={
            "code_indicators": ["powershell -enc AAAA"],
            "suspicious_embeds": ["trailing bytes after image end"],
            "recoverable_segments": [{"offset": 4096, "kind": "payload"}],
            "urls": ["http://192.0.2.10/payload?cmd=run"],
        },
        pixel_profile=_pixel(score=82, lsb=["token=hidden-secret"]),
        visible={"lines": [], "raw_text": ""},
        basic={"parser_status": "Invalid", "signature_status": "Mismatch", "format_trust": "Weak"},
        digital_verdict={"final_call": "ISOLATE", "risk_score": 92, "confidence_score": 88, "danger_zones": ["appended payload"]},
    )
    assert verdict.is_dangerous is True
    assert verdict.evidence_grade in {"A", "B"}
    assert verdict.review_priority == "P0"
    assert verdict.risk_temperature == "HOT"
    assert verdict.safe_handling_profile == "isolated_lab_only"
    assert "Do not" in verdict.export_policy or "Quarantine" in verdict.export_policy
    assert any("sensor_count" in item for item in verdict.calibration_notes)


def test_sensitive_document_text_is_privacy_not_malware():
    verdict = assess_image_threat(
        embedded_scan={},
        pixel_profile=_pixel(),
        visible={"lines": ["passport QR code recovery code"], "raw_text": "passport QR code recovery code"},
        basic={"parser_status": "Valid", "signature_status": "Matched", "format_trust": "Verified"},
        digital_verdict={"final_call": "CLEAR", "risk_score": 0, "confidence_score": 75},
    )
    assert verdict.is_dangerous is False
    assert verdict.evidence_grade == "P"
    assert verdict.review_priority == "P2"
    assert verdict.safe_handling_profile == "normal_preservation_with_privacy_redaction"
    assert any("sensitive" in item.lower() or "document" in item.lower() for item in verdict.privacy_findings)
