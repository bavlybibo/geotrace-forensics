from __future__ import annotations

from pathlib import Path

import pytest

QtWidgets = pytest.importorskip("PyQt5.QtWidgets")

from app.ui.main_window import GeoTraceMainWindow


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_review_auto_select_and_empty_state(tmp_path: Path):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = GeoTraceMainWindow(tmp_path)
    window.case_manager.new_case("UI Test")
    window.records = []
    window.filtered_records = []
    window.clear_details(reason="This case has no evidence yet.")
    assert "no evidence yet" in window.image_preview.text().lower()
    window.case_manager.load_images([project_root() / "demo_evidence"])
    window.records = list(window.case_manager.records)
    window.filtered_records = list(window.records)
    window.populate_table(window.filtered_records)
    window._auto_select_visible_record()
    assert window.selected_record() is not None
    window.close()
    app.quit()
