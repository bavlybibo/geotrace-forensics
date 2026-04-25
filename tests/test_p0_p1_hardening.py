from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from app.core.backup_utils import safe_extract_zip
from app.core.map_intelligence import analyze_map_intelligence
from app.core.models import EvidenceRecord
from app.core.reports import verify_export_package
from app.core.reports.package_assets import copy_package_assets
from app.core.case_manager import CaseManager


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_redacted_package_asset_copy_excludes_chart_map_and_geolocation_html(tmp_path: Path) -> None:
    source = tmp_path / "source"
    package = tmp_path / "package"
    source.mkdir()
    package.mkdir()
    (source / "chart_map.png").write_bytes(b"map-bytes")
    (source / "chart_timeline.png").write_bytes(b"timeline-bytes")
    (source / "geolocation_map.html").write_text("<html>coords</html>", encoding="utf-8")

    copied = copy_package_assets(source, package, "redacted_text")

    assert {p.name for p in copied} == {"chart_timeline.png"}
    assert not (package / "chart_map.png").exists()
    assert not (package / "geolocation_map.html").exists()


def test_verifier_fails_if_strict_package_contains_chart_map(tmp_path: Path) -> None:
    report = tmp_path / "report.txt"
    report.write_text("Redacted report", encoding="utf-8")
    chart = tmp_path / "chart_map.png"
    chart.write_bytes(b"coordinate-image")
    (tmp_path / "export_manifest.json").write_text(
        json.dumps(
            {
                "privacy_level": "courtroom_redacted",
                "artifacts": {"report": {"file_name": "report.txt", "sha256": _digest(report)}},
                "report_assets": {},
            }
        ),
        encoding="utf-8",
    )

    result = verify_export_package(tmp_path, privacy_level="courtroom_redacted")

    assert not result.passed
    assert any("chart_map.png" in failure for failure in result.failures)


def test_safe_extract_zip_blocks_zip_slip(tmp_path: Path) -> None:
    archive_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../../evil.txt", "owned")
    with zipfile.ZipFile(archive_path, "r") as archive:
        with pytest.raises(ValueError, match="Unsafe path"):
            safe_extract_zip(archive, tmp_path / "restore")


def test_ocr_note_survives_case_snapshot_roundtrip(tmp_path: Path) -> None:
    manager = CaseManager(tmp_path)
    record = EvidenceRecord(
        case_id=manager.active_case_id,
        case_name=manager.active_case_name,
        evidence_id="IMG-001",
        file_path=Path("evidence.png"),
        file_name="evidence.png",
        sha256="a" * 64,
        md5="b" * 32,
        perceptual_hash="0" * 16,
        file_size=10,
        imported_at="2026-04-24T10:00:00+00:00",
        ocr_note="OCR zones recovered from: full/gray. Mode=map_deep. Lang=eng+ara",
    )
    manager.records = [record]
    manager._write_case_snapshot()

    loaded = manager.load_case_snapshot(manager.active_case_id)

    assert loaded[0].ocr_note.startswith("OCR zones recovered")
    assert loaded[0].ocr_note.endswith("eng+ara")


def test_map_confidence_is_capped_when_signal_is_filename_only(tmp_path: Path) -> None:
    image = tmp_path / "Screenshot_Map_Cairo.png"
    from PIL import Image

    Image.new("RGB", (320, 240), "white").save(image)

    intel = analyze_map_intelligence(image, {"lines": [], "ocr_map_labels": [], "visible_location_strings": [], "visible_urls": [], "app_names": [], "raw_text": "", "excerpt": ""})

    assert intel.detected
    assert intel.candidate_city == "Cairo"
    assert intel.confidence <= 52
    assert "filename" in intel.evidence_basis
    assert any("filename-only" in reason for reason in intel.reasons)
