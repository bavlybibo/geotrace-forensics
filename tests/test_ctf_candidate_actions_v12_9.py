from __future__ import annotations

from types import SimpleNamespace

from app.ui.pages.ctf_geolocator_page import _candidate_key, _update_candidate_status_by_key


class _CaseManager:
    def __init__(self, records):
        self.records = records
        self.write_count = 0

    def _write_case_snapshot(self):
        self.write_count += 1


def _window(records):
    return SimpleNamespace(case_manager=_CaseManager(records), ctf_selected_candidate_key="")


def test_candidate_verify_updates_selected_candidate_only():
    record = SimpleNamespace(
        evidence_id="EV-1",
        location_solvability_score=80,
        geo_candidates=[
            {"name": "Cairo", "level": "city", "basis": ["ocr"], "status": "needs_review", "confidence": 70},
            {"name": "Giza", "level": "city", "basis": ["filename-only"], "status": "needs_review", "confidence": 35},
        ],
    )
    key = _candidate_key(record, record.geo_candidates[1])
    window = _window([record])

    assert _update_candidate_status_by_key(window, key, "verified")

    assert record.geo_candidates[0]["status"] == "needs_review"
    assert record.geo_candidates[1]["status"] == "verified"
    assert "selected candidate" in record.geo_candidates[1]["analyst_note"]
    assert window.case_manager.write_count == 1


def test_candidate_reject_falls_back_to_first_needs_review_when_no_selection():
    record = SimpleNamespace(
        evidence_id="EV-1",
        location_solvability_score=80,
        geo_candidates=[
            {"name": "Cairo", "level": "city", "basis": ["ocr"], "status": "needs_review", "confidence": 70},
            {"name": "Giza", "level": "city", "basis": ["filename-only"], "status": "needs_review", "confidence": 35},
        ],
    )
    window = _window([record])

    assert _update_candidate_status_by_key(window, "", "rejected")

    assert record.geo_candidates[0]["status"] == "rejected"
    assert record.geo_candidates[1]["status"] == "needs_review"
    assert window.case_manager.write_count == 1
