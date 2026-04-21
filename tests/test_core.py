from __future__ import annotations

from pathlib import Path

from app.core.anomalies import assign_duplicate_groups, parse_timestamp
from app.core.case_manager import CaseManager
from app.core.exif_service import extract_basic_image_info, extract_embedded_text_hints, infer_timestamp_from_filename
from app.core.gps_utils import dms_to_decimal, format_coordinates
from app.core.models import EvidenceRecord
from app.core.report_service import ReportService


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_gps_conversion_north_east():
    latitude = dms_to_decimal([30, 2, 39.84], "N")
    longitude = dms_to_decimal([31, 14, 8.52], "E")
    assert round(latitude, 4) == 30.0444
    assert round(longitude, 4) == 31.2357
    assert format_coordinates(latitude, longitude).startswith("30.0444")


def test_timestamp_parsing_from_filename():
    value = infer_timestamp_from_filename("IMG_20260306_203406.png")
    assert value == "2026:03:06 20:34:06"
    assert parse_timestamp(value) is not None


def test_parser_failure_handling_for_broken_gif():
    broken = project_root() / "demo_evidence" / "broken_animation.gif"
    info = extract_basic_image_info(broken)
    assert info["parser_status"] == "Failed"
    assert info["preview_status"] == "Decoder Failed"
    assert info["signature_status"] in {"Matched", "Compatible", "Unknown", "Mismatch"}
    assert info["format_trust"] in {"Header-only", "Weak", "Conflict", "Verified"}




def test_hidden_content_scan_detects_code_marker(tmp_path: Path):
    sample = tmp_path / "payload.png"
    sample.write_bytes(b"\x89PNG\r\n\x1a\n" + b"dummy-image-data<script>alert(1)</script> token=ABC123 https://example.com/test")
    result = extract_embedded_text_hints(sample, "PNG")
    assert result["code_indicators"]
    assert any("script" in item.lower() or "token" in item.lower() for item in result["code_indicators"])
    assert result["urls"]

def test_duplicate_grouping():
    base = EvidenceRecord(case_id="CASE-1", case_name="Case 1", evidence_id="IMG-001", file_path=Path("a.jpg"), file_name="a.jpg", sha256="a", md5="a", perceptual_hash="abcd", file_size=1, imported_at="now")
    peer = EvidenceRecord(case_id="CASE-1", case_name="Case 1", evidence_id="IMG-002", file_path=Path("b.jpg"), file_name="b.jpg", sha256="b", md5="b", perceptual_hash="abcd", file_size=1, imported_at="now")
    assign_duplicate_groups([base, peer])
    assert base.duplicate_group.startswith("Cluster-")
    assert base.duplicate_group == peer.duplicate_group


def test_custody_isolation_between_cases(tmp_path: Path):
    root = project_root()
    manager = CaseManager(tmp_path)
    case_one = manager.new_case("Case One")
    manager.load_images([root / "demo_evidence" / "broken_animation.gif"])
    log_one = manager.export_chain_of_custody()
    assert case_one.case_id in manager.active_case_id
    assert "broken_animation.gif" in log_one

    case_two = manager.new_case("Case Two")
    manager.load_images([root / "demo_evidence" / "no_exif.png"])
    log_two = manager.export_chain_of_custody()
    assert "no_exif.png" in log_two
    assert "broken_animation.gif" not in log_two
    assert case_one.case_id != case_two.case_id


def test_report_generation_outputs(tmp_path: Path):
    root = project_root()
    manager = CaseManager(tmp_path)
    manager.new_case("Report Case")
    records = manager.load_images([root / "demo_evidence" / "broken_animation.gif"])
    report_service = ReportService(tmp_path / "exports")
    html_path = report_service.export_html(records, manager.active_case_id, manager.active_case_name, manager.export_chain_of_custody())
    pdf_path = report_service.export_pdf(records, manager.active_case_id, manager.active_case_name)
    json_path = report_service.export_json(records)
    courtroom_path = report_service.export_courtroom_summary(records, manager.active_case_id, manager.active_case_name)
    assert html_path.exists()
    assert pdf_path.exists()
    assert json_path.exists()
    assert courtroom_path.exists()


def test_case_manager_smoke_run(tmp_path: Path):
    root = project_root()
    manager = CaseManager(tmp_path)
    manager.new_case("Smoke")
    records = manager.load_images([root / "demo_evidence"])
    assert len(records) >= 1
    assert manager.build_stats().total_images == len(records)
