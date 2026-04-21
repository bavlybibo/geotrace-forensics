from __future__ import annotations

from pathlib import Path

from app.core.case_manager import CaseManager
from app.core.exif_service import evaluate_timestamp_confidence
from app.core.gps_utils import gps_confidence_summary


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_validation_summary_mentions_core_metrics(tmp_path: Path):
    root = project_root()
    manager = CaseManager(tmp_path)
    manager.new_case("Validation")
    manager.load_images([root / "demo_evidence"])
    summary = manager.validation_summary()
    assert "GPS strong anchors" in summary
    assert "Parser clean" in summary
    assert "Custody chain" in summary
    assert "Integrity checked" in summary


def test_timestamp_confidence_prefers_native_exif():
    confidence, note = evaluate_timestamp_confidence("2026:04:10 10:30:00", "Native EXIF Original")
    assert confidence > 80
    assert "strongest native time anchor" in note


def test_gps_confidence_summary_for_missing_export_like_media():
    confidence, note = gps_confidence_summary(None, None, source_type="Screenshot / Export")
    assert confidence == 0
    assert "normal for screenshots" in note.lower()
