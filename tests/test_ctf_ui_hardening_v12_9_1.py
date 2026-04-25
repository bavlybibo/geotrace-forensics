from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PyQt5")

from app.ui.pages.ctf_geolocator_page import _iter_candidates, _render_writeup


def test_rejected_candidate_is_sorted_after_active_candidates():
    record = SimpleNamespace(
        evidence_id="EV-1",
        location_solvability_score=70,
        geo_candidates=[
            {"name": "Rejected Place", "level": "visual_context", "basis": ["visual"], "status": "rejected", "confidence": 80},
            {"name": "Active Place", "level": "poi", "basis": ["ocr"], "status": "needs_review", "confidence": 60},
        ],
    )

    rows = _iter_candidates([record])

    assert rows[0][1]["name"] == "Active Place"
    assert rows[-1][1]["status"] == "rejected"


def test_live_writeup_does_not_use_rejected_candidate_as_top_candidate():
    record = SimpleNamespace(
        evidence_id="EV-1",
        location_solvability_score=38,
        location_solvability_label="Map context only — no stable location",
        geo_candidates=[{"name": "Noisy Route", "level": "visual_context", "status": "rejected", "confidence": 38, "evidence_strength": "weak_signal", "analyst_note": "Visual-only route rejected."}],
        ctf_clues=[],
        ctf_search_queries=[],
        map_evidence_ladder=["Visual map context: present", "Final posture: weak visual context only unless corroborated."],
    )

    text = _render_writeup([record])

    assert "No active candidate remains" in text
    assert "Rejected candidates" in text
    assert "Noisy Route" in text
