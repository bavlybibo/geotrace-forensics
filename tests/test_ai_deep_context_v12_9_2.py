from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from app.core.ai.context_reasoner import attach_deep_context_reasoning
from app.core.ai.engine import run_ai_batch_assessment
from app.core.ai.visual_semantics import analyze_visual_semantics
from app.core.models import EvidenceRecord


def _image(path: Path, *, map_like: bool = False) -> Path:
    img = Image.new("RGB", (480, 320), "white")
    draw = ImageDraw.Draw(img)
    if map_like:
        for y in range(40, 300, 55):
            draw.rectangle((0, y, 480, y + 10), fill=(170, 190, 205))
        draw.rectangle((90, 150, 390, 170), fill=(40, 85, 230))
        draw.ellipse((370, 132, 398, 160), fill=(220, 40, 45))
        draw.rectangle((40, 55, 140, 120), fill=(120, 190, 120))
    img.save(path)
    return path


def _record(tmp_path: Path, evidence_id: str = "IMG001") -> EvidenceRecord:
    img = _image(tmp_path / f"{evidence_id}.png", map_like=True)
    return EvidenceRecord(
        case_id="CASE-AI",
        case_name="Deep AI",
        evidence_id=evidence_id,
        file_path=img,
        file_name=img.name,
        sha256="a" * 64,
        md5="b" * 32,
        perceptual_hash="0" * 16,
        file_size=img.stat().st_size,
        imported_at="2026-04-25T00:00:00Z",
    )


def test_visual_semantics_detects_map_like_layout(tmp_path: Path):
    profile = analyze_visual_semantics(_image(tmp_path / "map.png", map_like=True))

    assert profile.confidence > 0
    assert "visual" in profile.label.lower() or "map" in profile.label.lower()
    assert any("route" in cue.lower() or "map" in cue.lower() for cue in profile.cues)
    assert profile.limitations


def test_deep_context_reasoner_flags_displayed_location_without_gps(tmp_path: Path):
    record = _record(tmp_path)
    record.map_intelligence_confidence = 82
    record.map_evidence_basis = ["ocr/text", "known-place-dictionary", "route-visual"]
    record.route_overlay_detected = True
    record.candidate_city = "Cairo"
    record.candidate_area = "Zamalek"
    record.timestamp_confidence = 0
    record.visible_urls = ["https://maps.google.com/?q=Cairo+Tower"]

    findings = run_ai_batch_assessment([record])
    finding = findings[record.evidence_id]

    assert "displayed_location_not_device_proof" in finding.flags
    assert "location_without_time_anchor" in finding.flags
    assert any(line.startswith("AI reasoning: Location posture") for line in finding.corroboration_matrix)
    assert any("Privacy posture" in line for line in finding.confidence_basis)
    assert any("displayed" in action.lower() or "corroborate" in action.lower() for action in finding.action_plan)


def test_deep_context_reasoner_detects_duplicate_location_context_mismatch(tmp_path: Path):
    left = _record(tmp_path, "IMG101")
    right = _record(tmp_path, "IMG102")
    left.duplicate_group = right.duplicate_group = "DUP-7"
    left.gps_latitude = 30.0444
    left.gps_longitude = 31.2357
    left.gps_display = "30.0444, 31.2357"
    left.gps_confidence = 90
    right.candidate_city = "Alexandria"
    right.map_intelligence_confidence = 78
    right.map_evidence_basis = ["ocr/text", "known-place-dictionary"]

    findings = {left.evidence_id: run_ai_batch_assessment([left]).get(left.evidence_id), right.evidence_id: run_ai_batch_assessment([right]).get(right.evidence_id)}
    # Re-run only the cross-case reasoning on shared findings to isolate the duplicate mismatch behaviour.
    attach_deep_context_reasoning([left, right], findings)  # type: ignore[arg-type]

    assert "duplicate_location_context_mismatch" in findings[left.evidence_id].flags
    assert "duplicate_location_context_mismatch" in findings[right.evidence_id].flags
