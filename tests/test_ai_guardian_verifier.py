from pathlib import Path
import hashlib
import json

import pytest

from app.core.models import EvidenceRecord
from app.core.ai import build_evidence_graph, case_readiness_scores, explain_contradictions, guardian_narrative
from app.core.reports import verify_export_package


def _record(eid: str, lat: float, lon: float, ts: str, sha: str) -> EvidenceRecord:
    return EvidenceRecord(
        case_id="CASE-TEST",
        case_name="Guardian Test",
        evidence_id=eid,
        file_path=Path(f"case/{eid}.jpg"),
        file_name=f"{eid}.jpg",
        sha256=sha * 64,
        md5=sha * 32,
        perceptual_hash="0" * 16,
        file_size=100,
        imported_at="2026-04-24T10:00:00",
        gps_latitude=lat,
        gps_longitude=lon,
        timestamp=ts,
        timestamp_confidence=82,
        gps_confidence=90,
        integrity_status="Verified",
        signature_status="Matched",
        device_model="Demo Camera",
    )


@pytest.mark.ai
@pytest.mark.unit
def test_ai_guardian_graph_and_readiness():
    records = [
        _record("IMG001", 30.0444, 31.2357, "2026-04-24 10:00:00", "a"),
        _record("IMG002", 31.2001, 29.9187, "2026-04-24 10:10:00", "b"),
    ]
    graph = build_evidence_graph(records)
    readiness = case_readiness_scores(records)
    contradictions = explain_contradictions(records)
    narrative = guardian_narrative(records)

    assert readiness["case_readiness"] > 0
    assert graph
    assert contradictions
    assert "Case Readiness" in narrative


@pytest.mark.privacy
@pytest.mark.integration
def test_courtroom_package_verifier_detects_manifest_and_hashes(tmp_path):
    report = tmp_path / "report.txt"
    report.write_text("Redacted safe report", encoding="utf-8")
    digest = hashlib.sha256(report.read_bytes()).hexdigest()
    (tmp_path / "export_manifest.json").write_text(
        json.dumps({
            "privacy_level": "redacted_text",
            "artifacts": {"report": {"file_name": "report.txt", "sha256": digest}},
            "report_assets": {},
        }),
        encoding="utf-8",
    )
    result = verify_export_package(tmp_path, privacy_level="redacted_text")
    assert result.passed
