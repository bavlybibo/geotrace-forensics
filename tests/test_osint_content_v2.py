from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.core.ai.osint_content import analyze_image_content
from app.core.models import EvidenceRecord


def _record(tmp_path: Path, name: str = "Screenshot_Map_Cairo.png") -> EvidenceRecord:
    img = tmp_path / name
    Image.new("RGB", (1200, 800), "white").save(img)
    return EvidenceRecord(
        case_id="CASE-1",
        case_name="Demo",
        evidence_id="EVD-1",
        file_path=img,
        file_name=name,
        sha256="a" * 64,
        md5="b" * 32,
        perceptual_hash="0" * 16,
        file_size=img.stat().st_size,
        imported_at="2026-04-24T00:00:00Z",
    )


def test_osint_content_map_location_hypothesis(tmp_path: Path):
    record = _record(tmp_path)
    record.map_intelligence_confidence = 82
    record.route_overlay_detected = True
    record.candidate_city = "Cairo"
    record.candidate_area = "Zamalek"
    record.ocr_map_labels = ["Cairo Tower", "Zamalek"]
    record.place_candidates = ["Cairo Tower"]
    record.visible_text_excerpt = "Google Maps directions Cairo Tower Zamalek"

    profile = analyze_image_content(record)

    assert profile.label == "OSINT map/location artifact"
    assert profile.confidence >= 82
    assert any("Candidate city: Cairo" in item for item in profile.location_hypotheses)
    assert any("Do not claim device location" in action for action in profile.next_actions)


def test_osint_content_low_context_has_limitations(tmp_path: Path):
    record = _record(tmp_path, "no_exif.png")
    profile = analyze_image_content(record)

    assert profile.confidence > 0
    assert profile.limitations
    assert profile.next_actions
