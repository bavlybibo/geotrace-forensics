from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.anomalies import detect_anomalies
from app.core.case_db import CaseDatabase
from app.core.case_manager import CaseManager
from app.core.models import EvidenceRecord
from app.core.report_service import ReportService


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def minimal_record(case_id: str = "CASE-1", case_name: str = "Case 1") -> EvidenceRecord:
    return EvidenceRecord(
        case_id=case_id,
        case_name=case_name,
        evidence_id="IMG-001",
        file_path=Path("/private/source/private-image.png"),
        original_file_path=Path("/private/source/private-image.png"),
        working_copy_path=Path("case_data/CASE-1/evidence/IMG-001_private-image.png"),
        file_name="private-image.png",
        sha256="a" * 64,
        md5="b" * 32,
        perceptual_hash="0" * 16,
        file_size=42,
        imported_at="2026-04-24T10:00:00+00:00",
    )


def test_ai_assistant_uses_active_case_properties() -> None:
    source = (project_root() / "app" / "ui" / "mixins" / "review_selection.py").read_text(encoding="utf-8")
    assert "case_manager.active_case_id" in source
    assert "case_manager.active_case_name" in source
    assert "case_manager.case_id" not in source
    assert "case_manager.case_name" not in source


def test_case_ids_are_unique_and_duplicate_inserts_do_not_replace(tmp_path: Path) -> None:
    manager = CaseManager(tmp_path)
    generated = {manager.active_case_id}
    for _ in range(12):
        generated.add(manager.new_case("Repeated Case Name").case_id)
    assert len(generated) == 13

    db = CaseDatabase(tmp_path / "manual" / "cases.db")
    db.create_case("CASE-DUPLICATE", "Original Case")
    with pytest.raises(ValueError):
        db.create_case("CASE-DUPLICATE", "Replacement Attempt")
    cases = {case.case_id: case.case_name for case in db.list_cases()}
    assert cases["CASE-DUPLICATE"] == "Original Case"


def test_snapshot_backup_recovers_when_primary_snapshot_is_corrupt(tmp_path: Path) -> None:
    manager = CaseManager(tmp_path)
    record = minimal_record(manager.active_case_id, manager.active_case_name)
    manager.records = [record]
    manager._write_case_snapshot()
    manager._write_case_snapshot()

    snapshot_path = manager.case_snapshot_path()
    backup_path = snapshot_path.with_suffix(".json.bak")
    assert backup_path.exists()

    snapshot_path.write_text("{ this is not valid json", encoding="utf-8")
    recovered = manager.load_case_snapshot(manager.active_case_id)
    assert len(recovered) == 1
    assert recovered[0].evidence_id == "IMG-001"
    assert manager.snapshot_warnings
    assert (tmp_path / "logs" / "snapshot_recovery.log").exists()


def test_privacy_export_redacts_ocr_visible_text_and_urls(tmp_path: Path) -> None:
    record = minimal_record()
    record.visible_text_excerpt = "Meet @bibo_fox at Private Villa. Open https://secret.example/reset?token=abc"
    record.visible_text_lines = [record.visible_text_excerpt]
    record.visible_urls = ["https://secret.example/reset?token=abc"]
    record.visible_location_strings = ["Private Villa"]
    record.ocr_raw_text = "Contact bavly@example.com and @bibo_fox near 30.123456, 31.654321"
    record.ocr_url_entities = ["https://secret.example/reset?token=abc"]
    record.ocr_username_entities = ["@bibo_fox"]
    record.ocr_location_entities = ["Private Villa"]
    record.urls_found = ["https://secret.example/embed"]
    record.extracted_strings = ["api=https://secret.example/embed user=@bibo_fox"]

    output = ReportService(tmp_path).export_json([record], privacy_level="redacted_text")
    raw = output.read_text(encoding="utf-8")
    assert "secret.example" not in raw
    assert "bavly@example.com" not in raw
    assert "@bibo_fox" not in raw
    assert "Private Villa" not in raw

    data = json.loads(raw)[0]
    assert data["privacy_level"] == "redacted_text"
    assert data["visible_text"]["urls"] == ["[REDACTED_URL]"]
    assert data["ocr"]["entities"]["usernames"] == ["[REDACTED_USERNAME]"]
    assert data["ocr"]["raw_text"] == "[REDACTED_TEXT]"


def test_low_risk_clean_record_has_no_positive_issue_reason(tmp_path: Path) -> None:
    record = minimal_record()
    score, confidence, level, reasons, *_ = detect_anomalies(record, baseline_device="Unknown", file_path=tmp_path / "missing.png")
    assert "No major metadata anomalies were detected." not in reasons


def test_shareable_report_outputs_redact_sensitive_text_entities_and_map_chart(tmp_path: Path) -> None:
    pytest.importorskip("reportlab")
    record = minimal_record()
    record.gps_display = "30.123456, 31.654321"
    record.gps_latitude = 30.123456
    record.gps_longitude = 31.654321
    record.gps_confidence = 95
    record.derived_geo_display = "Private Villa"
    record.derived_geo_note = "OCR indicates Private Villa near Cairo."
    record.visible_text_excerpt = "Meet @bibo_fox at Private Villa. Open https://secret.example/reset?token=abc"
    record.visible_text_lines = [record.visible_text_excerpt]
    record.ocr_raw_text = "Private Villa contact bavly@example.com @bibo_fox https://secret.example/reset"
    record.ocr_location_entities = ["Private Villa"]
    record.ocr_url_entities = ["https://secret.example/reset"]
    record.ocr_username_entities = ["@bibo_fox"]
    record.ocr_analyst_relevance = "OCR recovered Private Villa and @bibo_fox"
    record.hidden_code_summary = "Embedded URL https://secret.example/embed"
    record.ai_summary = "Possible private URL https://secret.example/reset and username @bibo_fox"
    record.score_reason = "Visible private URL https://secret.example/reset should be corroborated."
    record.score_next_step = "Check @bibo_fox context without sharing raw OCR."
    record.courtroom_notes = "Private Villa should be validated with independent evidence."

    service = ReportService(tmp_path)
    html_path = service.export_html([record], "CASE-1", "Case 1", privacy_level="redacted_text")
    courtroom_path = service.export_courtroom_summary([record], "CASE-1", "Case 1", privacy_level="redacted_text")
    executive_path = service.export_executive_summary([record], "CASE-1", "Case 1", privacy_level="redacted_text")
    pdf_path = service.export_pdf([record], "CASE-1", "Case 1", privacy_level="redacted_text")

    html_raw = html_path.read_text(encoding="utf-8")
    courtroom_raw = courtroom_path.read_text(encoding="utf-8")
    executive_raw = executive_path.read_text(encoding="utf-8")

    for raw in (html_raw, courtroom_raw, executive_raw):
        assert "secret.example" not in raw
        assert "@bibo_fox" not in raw
        assert "bavly@example.com" not in raw
        assert "30.123456" not in raw
        assert "31.654321" not in raw

    assert "Private Villa" not in html_raw
    assert "[REDACTED_LOCATION]" in html_raw
    assert "[REDACTED_URL]" in html_raw
    assert "[REDACTED_USERNAME]" in html_raw
    assert "[REDACTED_TEXT]" in html_raw
    assert "chart_map.png" not in html_raw
    assert pdf_path.exists()


def test_redacted_exports_hide_filenames_devices_gps_ai_and_manifest_assets(tmp_path: Path) -> None:
    record = minimal_record()
    record.file_name = "bavly_home_private_villa_cairo.jpg"
    record.device_model = "iPhone 15 Pro Bavly"
    record.software = "Private Editor 1.0"
    record.gps_display = "30.123456, 31.654321"
    record.gps_latitude = 30.123456
    record.gps_longitude = 31.654321
    record.derived_geo_display = "Private Villa Cairo"
    record.gps_ladder = ["Verify 30.123456, 31.654321 near Private Villa"]
    record.gps_primary_issue = "Private Villa GPS needs review"
    record.time_candidates = ["Private chat at 2026-04-24 15:30"]
    record.time_conflicts = ["Private upload conflict"]
    record.ai_flags = ["private_url_seen"]
    record.ai_breakdown = ["AI +8 — Private Villa / secret.example / @bibo_fox"]

    service = ReportService(tmp_path)
    html_path = service.export_html([record], "CASE-1", "Case 1", privacy_level="courtroom_redacted")
    json_path = service.export_json([record], privacy_level="courtroom_redacted")
    csv_path = service.export_csv([record], privacy_level="courtroom_redacted")
    manifest_path = service.export_package_manifest({"html": str(html_path), "json": str(json_path), "csv": str(csv_path)}, privacy_level="courtroom_redacted")

    combined = "\n".join(path.read_text(encoding="utf-8") for path in (html_path, json_path, csv_path, manifest_path))
    assert "bavly_home_private_villa_cairo" not in combined
    assert "iPhone 15 Pro Bavly" not in combined
    assert "Private Editor" not in combined
    assert "30.123456" not in combined
    assert "31.654321" not in combined
    assert "Private Villa" not in combined
    assert "secret.example" not in combined
    assert "@bibo_fox" not in combined
    assert "report_assets" in manifest_path.read_text(encoding="utf-8")
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["report_assets"] == {}

    data = json.loads(json_path.read_text(encoding="utf-8"))[0]
    assert data["privacy_level"] == "courtroom_redacted"
    assert data["file_name"] == "IMG-001.jpg"
    assert data["device_model"] == "[REDACTED_DEVICE]"
    assert data["software"] == "[REDACTED_SOFTWARE]"
    assert data["gps"]["latitude"] is None
    assert data["ai_assessment"]["breakdown"] == ["[REDACTED_AI_BREAKDOWN]"]
