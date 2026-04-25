from __future__ import annotations

from pathlib import Path

from app.core.ai_engine import run_ai_batch_assessment
from app.core.models import EvidenceRecord


def _record(evidence_id: str, lat: float, lon: float, timestamp: str) -> EvidenceRecord:
    return EvidenceRecord(
        case_id="CASE-AI",
        case_name="AI Case",
        evidence_id=evidence_id,
        file_path=Path(f"{evidence_id}.jpg"),
        file_name=f"{evidence_id}.jpg",
        sha256=evidence_id * 8,
        md5=evidence_id * 4,
        perceptual_hash="abcd000000000000",
        file_size=100,
        imported_at="now",
        gps_latitude=lat,
        gps_longitude=lon,
        gps_confidence=90,
        gps_display=f"{lat}, {lon}",
        timestamp=timestamp,
    )


def test_ai_engine_flags_impossible_travel_and_geo_outlier():
    records = [
        _record("IMG001", 30.0444, 31.2357, "2026:04:24 10:00:00"),
        _record("IMG002", 30.0500, 31.2400, "2026:04:24 10:10:00"),
        _record("IMG003", 31.2001, 29.9187, "2026:04:24 10:20:00"),
    ]
    findings = run_ai_batch_assessment(records)
    assert findings["IMG003"].score_delta > 0
    assert any(flag in findings["IMG003"].flags for flag in {"geo_outlier", "impossible_travel", "rapid_travel"})
    assert findings["IMG003"].breakdown


def test_ai_engine_adds_corroboration_plan_without_positive_flags():
    records = [
        _record("IMG010", 30.0444, 31.2357, "2026:04:24 10:00:00"),
        _record("IMG011", 30.0445, 31.2358, "2026:04:24 10:05:00"),
    ]
    findings = run_ai_batch_assessment(records)
    assert findings["IMG010"].breakdown
    assert findings["IMG010"].action_plan
    assert findings["IMG010"].corroboration_matrix
    assert any(item.startswith("AI plan") for item in findings["IMG010"].breakdown)
    assert "Suggested first step" in findings["IMG010"].summary


def test_ai_engine_flags_duplicate_context_conflict():
    left = _record("IMG020", 30.0444, 31.2357, "2026:04:24 10:00:00")
    right = _record("IMG021", 31.2001, 29.9187, "2026:04:25 12:00:00")
    left.duplicate_group = right.duplicate_group = "DUP-1"
    findings = run_ai_batch_assessment([left, right])
    assert "duplicate_context_conflict" in findings["IMG020"].flags
    assert "duplicate_context_conflict" in findings["IMG021"].flags


def test_ai_engine_assigns_priority_and_action_plan():
    records = [
        _record("IMG030", 30.0444, 31.2357, "2026:04:24 10:00:00"),
        _record("IMG031", 30.0445, 31.2358, "2026:04:24 10:05:00"),
        _record("IMG032", 40.7128, -74.0060, "2026:04:24 10:20:00"),
    ]
    findings = run_ai_batch_assessment(records)
    assert all(finding.priority_rank > 0 for finding in findings.values())
    assert findings["IMG032"].executive_note
    assert findings["IMG032"].action_plan
