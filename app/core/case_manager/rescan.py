from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ..ai.osint_content import analyze_image_content
from ..ai.osint_scene import predict_osint_scene
from ..exif_service import extract_basic_image_info
from ..explainability import apply_explainability
from ..map_intelligence import analyze_map_intelligence
from ..models import EvidenceRecord
from ..ocr_diagnostics import run_ocr_diagnostic
from ..osint.visual_clue_engine import extract_ctf_visual_clues
from ..osint.offline_geocoder import build_source_comparison
from ..validation_service import build_validation_metrics
from ..vision.image_intelligence import analyze_image_details
from ..visual_clues import extract_visible_text_clues, parse_derived_geo

if TYPE_CHECKING:  # pragma: no cover
    from .service import CaseManager


def _record_path(record: EvidenceRecord) -> Path:
    for value in (record.file_path, record.working_copy_path, record.original_file_path):
        path = Path(value)
        if path.exists():
            return path
    return Path(record.file_path)


def _merge_unique(first: list[str], second: list[str], limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in [*first, *second]:
        key = str(item).strip()
        if not key or key.lower() in seen:
            continue
        seen.add(key.lower())
        out.append(key)
        if len(out) >= limit:
            break
    return out


def refresh_record_from_visible_signals(manager: "CaseManager", record: EvidenceRecord, visible: dict, *, mode: str = "map_deep") -> EvidenceRecord:
    path = _record_path(record)
    visual_profile = extract_ctf_visual_clues(path)
    record.ctf_visual_clue_profile = visual_profile.to_dict()
    try:
        record.ocr_diagnostics = run_ocr_diagnostic().to_dict()
    except Exception as exc:
        manager.logger.warning("OCR diagnostic refresh failed for %s: %s", record.evidence_id, exc)
        record.ocr_diagnostics = {"status": "diagnostic failed", "recommendation": str(exc)}
    map_intel = analyze_map_intelligence(path, visible)
    visible_app = str(visible.get("app_detected", "Unknown"))
    record.app_detected = map_intel.app_detected if visible_app in {"", "Unknown"} and map_intel.app_detected != "Unknown" else visible_app

    map_text_candidates = [
        *list(visible.get("lines", [])),
        *list(visible.get("ocr_map_labels", [])),
        *map_intel.place_candidates,
        *map_intel.landmarks_detected,
        map_intel.candidate_city,
        map_intel.candidate_area,
        Path(record.file_name or path.name).stem,
    ]
    derived_geo = parse_derived_geo(
        map_text_candidates,
        list(visible.get("visible_urls", [])) + list(getattr(record, "urls_found", []) or []),
        source_type=record.source_type,
    )

    record.visible_text_lines = list(visible.get("lines", []))
    record.visible_text_excerpt = str(visible.get("excerpt", ""))
    record.ocr_raw_text = str(visible.get("raw_text", ""))
    record.ocr_note = str(visible.get("ocr_note", "OCR not attempted."))
    record.ocr_confidence = int(visible.get("ocr_confidence", 0) or 0)
    record.ocr_analyst_relevance = str(visible.get("ocr_analyst_relevance", "OCR not attempted."))
    record.ocr_region_signals = list(visible.get("ocr_region_signals", []))
    record.ocr_app_names = list(visible.get("app_names", []))
    record.ocr_username_entities = list(visible.get("ocr_username_entities", []))
    record.ocr_map_labels = list(visible.get("ocr_map_labels", []))
    record.visible_urls = list(visible.get("visible_urls", []))
    record.ocr_url_entities = list(visible.get("visible_urls", []))
    record.visible_time_strings = list(visible.get("visible_time_strings", []))
    record.ocr_time_entities = list(visible.get("visible_time_strings", []))
    record.visible_location_strings = list(visible.get("visible_location_strings", []))
    record.ocr_location_entities = list(visible.get("visible_location_strings", []))
    record.possible_geo_clues = list(derived_geo.get("possible_geo_clues", []))
    record.environment_profile = str(visible.get("environment_profile", record.environment_profile or "Unknown"))

    if derived_geo.get("latitude") is not None and derived_geo.get("longitude") is not None:
        record.derived_latitude = derived_geo.get("latitude")
        record.derived_longitude = derived_geo.get("longitude")
        record.derived_geo_display = str(derived_geo.get("display", "Unavailable"))
        record.derived_geo_source = str(derived_geo.get("source", "Unavailable"))
        record.derived_geo_confidence = int(derived_geo.get("confidence", 0) or 0)
        record.derived_geo_note = str(derived_geo.get("note", "No screenshot-derived geolocation clue recovered."))
    elif int(derived_geo.get("confidence", 0) or 0) > int(getattr(record, "derived_geo_confidence", 0) or 0):
        record.derived_geo_display = str(derived_geo.get("display", "Unavailable"))
        record.derived_geo_source = str(derived_geo.get("source", "Unavailable"))
        record.derived_geo_confidence = int(derived_geo.get("confidence", 0) or 0)
        record.derived_geo_note = str(derived_geo.get("note", "No screenshot-derived geolocation clue recovered."))

    record.map_app_detected = map_intel.app_detected
    record.map_type = map_intel.map_type
    record.route_overlay_detected = map_intel.route_overlay_detected
    record.route_confidence = map_intel.route_confidence
    record.candidate_city = map_intel.candidate_city
    record.candidate_area = map_intel.candidate_area
    record.landmarks_detected = list(map_intel.landmarks_detected)
    record.place_candidates = list(map_intel.place_candidates)
    record.map_intelligence_confidence = map_intel.confidence
    record.map_ocr_language_hint = map_intel.ocr_language_hint
    record.map_intelligence_summary = map_intel.summary
    record.map_intelligence_reasons = list(map_intel.reasons)
    record.map_evidence_basis = list(map_intel.evidence_basis)
    record.map_evidence_strength = map_intel.evidence_strength
    record.map_limitations = list(map_intel.limitations)
    record.map_recommended_actions = list(map_intel.recommended_actions)
    record.map_evidence_ladder = list(getattr(map_intel, "evidence_ladder", []))
    record.map_visual_profile = dict(getattr(map_intel, "visual_profile", {}) or {})
    record.map_anchor_status = str(getattr(map_intel, "anchor_status", "No stable map/location anchor recovered."))
    record.map_answer_readiness_score = int(getattr(map_intel, "answer_readiness_score", 0) or 0)
    record.map_answer_readiness_label = str(getattr(map_intel, "answer_readiness_label", "Not answer-ready"))
    record.map_extraction_plan = list(getattr(map_intel, "extraction_plan", []) or [])
    record.map_route_start_label = str(getattr(map_intel, "route_start_label", "") or "")
    record.map_route_end_label = str(getattr(map_intel, "route_end_label", "") or "")
    record.map_label_clusters = list(getattr(map_intel, "label_clusters", []) or [])
    record.map_confidence_radius_m = int(getattr(map_intel, "confidence_radius_m", 0) or 0)
    record.map_offline_geocoder_hits = list(getattr(map_intel, "offline_geocoder_hits", []) or [])
    record.map_interactive_payload = dict(getattr(map_intel, "interactive_map_payload", {}) or {})
    record.map_source_comparison = build_source_comparison(
        native_gps=record.gps_display if record.has_gps else "",
        derived_geo=record.derived_geo_display if record.derived_geo_display != "Unavailable" else "",
        map_url="; ".join(str(x) for x in record.visible_urls[:2]),
        ocr_places=list(record.ocr_map_labels or record.visible_location_strings or []),
        landmarks=record.landmarks_detected,
        offline_hits=record.map_offline_geocoder_hits,
    )
    record.place_candidate_rankings = list(map_intel.place_candidate_rankings)
    record.filename_location_hints = list(getattr(map_intel, "filename_location_hints", []))

    if record.has_gps:
        record.geo_status = f"Native GPS recovered from {record.gps_source}."
    elif record.derived_geo_display != "Unavailable":
        record.geo_status = "No native GPS recovered, but screenshot-derived location clues were parsed from visible content."
    elif str(visible.get("ocr_map_context", "")).startswith("Map/place"):
        labels = list(visible.get("ocr_map_labels", []))
        label_note = f" Possible place clue: {labels[0]}." if labels else ""
        record.geo_status = "No native GPS recovered, but map/place context was detected in the visible content." + label_note
    elif map_intel.detected:
        route_note = " Route overlay detected." if map_intel.route_overlay_detected else ""
        city_note = f" Candidate city: {map_intel.candidate_city}." if map_intel.candidate_city != "Unavailable" else ""
        record.geo_status = "No native GPS recovered, but map intelligence detected a map/navigation screenshot." + route_note + city_note
    else:
        record.geo_status = "No native GPS recovered."

    image_profile = analyze_image_details(path)
    record.image_detail_label = image_profile.label
    record.image_detail_confidence = int(image_profile.confidence)
    record.image_detail_summary = image_profile.summary
    record.image_detail_cues = list(image_profile.cues)
    record.image_layout_hints = list(image_profile.layout_hints)
    record.image_object_hints = list(image_profile.object_hints)
    record.image_quality_flags = list(image_profile.quality_flags)
    record.image_detail_metrics = dict(image_profile.metrics)
    record.image_detail_limitations = list(image_profile.limitations)
    record.image_detail_next_actions = list(image_profile.next_actions)
    record.image_attention_regions = list(getattr(image_profile, "attention_regions", []))
    record.image_scene_descriptors = list(getattr(image_profile, "scene_descriptors", []))
    record.image_analysis_methodology = list(getattr(image_profile, "methodology_steps", []))
    record.image_performance_notes = list(getattr(image_profile, "performance_notes", []))

    scene = predict_osint_scene(record)
    record.osint_scene_label = scene.label
    record.osint_scene_confidence = scene.confidence
    record.osint_scene_summary = scene.summary
    record.osint_scene_reasons = list(scene.reasons)
    record.detected_map_context = scene.detected_map_context
    record.possible_place = scene.possible_place
    record.map_confidence = max(scene.map_confidence, record.map_intelligence_confidence)

    content = analyze_image_content(record)
    record.osint_content_label = content.label
    record.osint_content_confidence = content.confidence
    record.osint_content_summary = content.summary
    record.osint_content_tags = list(content.content_tags)
    record.osint_visual_cues = list(content.visual_cues)
    record.osint_text_cues = list(content.text_cues)
    record.osint_location_hypotheses = list(content.location_hypotheses)
    record.osint_source_context = content.source_context
    record.osint_content_limitations = list(content.limitations)
    record.osint_next_actions = list(content.next_actions)
    visual_tags = list((getattr(record, "ctf_visual_clue_profile", {}) or {}).get("visual_tags", []) or [])
    record.osint_visual_cues = _merge_unique(record.osint_visual_cues, visual_tags, 16)
    record.osint_content_tags = _merge_unique(record.osint_content_tags, [str((getattr(record, "ctf_visual_clue_profile", {}) or {}).get("scene_type", ""))], 12)

    manager._apply_osint_signal_profile(record)
    manager._apply_location_estimate(record)
    apply_explainability(record)
    record.analyst_verdict = manager._derive_analyst_verdict(record)
    record.courtroom_notes = manager._derive_courtroom_notes(record)
    return record


def rescan_record_osint(manager: "CaseManager", evidence_id: str, *, mode: str = "map_deep", force: bool = True) -> Optional[EvidenceRecord]:
    record = manager.get_record(evidence_id)
    if record is None:
        return None
    path = _record_path(record)
    if not path.exists():
        manager.logger.warning("Cannot rescan %s because the staged file is missing: %s", evidence_id, path)
        return None
    width = int(getattr(record, "width", 0) or 0)
    height = int(getattr(record, "height", 0) or 0)
    if width <= 0 or height <= 0:
        basic = extract_basic_image_info(path)
        width = int(basic.get("width", 0) or 0)
        height = int(basic.get("height", 0) or 0)
    visible = extract_visible_text_clues(
        path,
        width,
        height,
        source_hint=record.source_type,
        force=force,
        mode=mode,
        cache_dir=manager.case_root / manager.active_case_id / "ocr_cache",
    )
    refresh_record_from_visible_signals(manager, record, visible, mode=mode)
    build_validation_metrics(manager.records)
    manager.db.upsert_evidence(record)
    manager.db.log_action(manager.active_case_id, evidence_id, "RESCAN_OSINT", f"Rescanned OCR/map/OSINT signals with mode={mode}, force={force}.")
    manager._write_case_snapshot()
    return record


def manual_crop_ocr(manager: "CaseManager", evidence_id: str, crop_box: tuple[float, float, float, float] | None = None, *, label: str = "manual_crop") -> Optional[EvidenceRecord]:
    """Run privacy-safe local OCR over manual/CTF crop zones and merge the result.

    When crop_box is omitted, v12.9.4 runs a multi-zone map plan instead of only a
    center crop: top/search header, center canvas, bottom labels, and side panels when
    the image aspect ratio suggests they exist. The original image never leaves disk.
    """
    record = manager.get_record(evidence_id)
    if record is None:
        return None
    path = _record_path(record)
    if not path.exists():
        manager.logger.warning("Manual crop OCR skipped; staged file missing for %s", evidence_id)
        return None
    crop_dir = manager.case_root / manager.active_case_id / "ocr_cache" / "manual_crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image
        with Image.open(path) as image:
            image.load()
            w, h = image.size
            if crop_box is not None:
                zones = [{"name": label, "box": crop_box, "why": "analyst-supplied crop box"}]
            else:
                profile = extract_ctf_visual_clues(path)
                zones = list((profile.to_dict().get("recommended_crops") or []))
                if not zones:
                    zones = [{"name": label, "box": (0.18, 0.14, 0.86, 0.86), "why": "fallback center crop"}]
            merged_visible: dict[str, object] = {
                "lines": list(getattr(record, "visible_text_lines", []) or []),
                "ocr_map_labels": list(getattr(record, "ocr_map_labels", []) or []),
                "visible_urls": list(getattr(record, "visible_urls", []) or []),
                "visible_time_strings": list(getattr(record, "visible_time_strings", []) or []),
                "visible_location_strings": list(getattr(record, "visible_location_strings", []) or []),
                "app_names": list(getattr(record, "ocr_app_names", []) or []),
                "ocr_region_signals": list(getattr(record, "ocr_region_signals", []) or []),
                "raw_text": str(getattr(record, "ocr_raw_text", "") or ""),
                "excerpt": str(getattr(record, "visible_text_excerpt", "") or ""),
                "ocr_confidence": int(getattr(record, "ocr_confidence", 0) or 0),
                "environment_profile": getattr(record, "environment_profile", "Unknown"),
            }
            crop_assets: list[str] = []
            zone_notes: list[str] = []
            for idx, zone in enumerate(zones[:6], start=1):
                box = zone.get("box", (0.18, 0.14, 0.86, 0.86)) if isinstance(zone, dict) else (0.18, 0.14, 0.86, 0.86)
                left = max(0, min(w - 1, int(w * float(box[0]))))
                top = max(0, min(h - 1, int(h * float(box[1]))))
                right = max(left + 1, min(w, int(w * float(box[2]))))
                bottom = max(top + 1, min(h, int(h * float(box[3]))))
                crop = image.crop((left, top, right, bottom))
                safe_label = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in str(zone.get("name", f"zone_{idx}") if isinstance(zone, dict) else f"zone_{idx}"))[:40]
                crop_path = crop_dir / f"{record.evidence_id}_{idx:02d}_{safe_label}.png"
                crop.save(crop_path)
                crop_assets.append(str(crop_path))
                crop_visible = extract_visible_text_clues(
                    crop_path,
                    crop.size[0],
                    crop.size[1],
                    source_hint=record.source_type,
                    force=True,
                    mode="map_deep",
                    cache_dir=manager.case_root / manager.active_case_id / "ocr_cache",
                )
                merged_visible["lines"] = _merge_unique(list(merged_visible.get("lines", [])), list(crop_visible.get("lines", [])), 60)
                merged_visible["ocr_map_labels"] = _merge_unique(list(merged_visible.get("ocr_map_labels", [])), list(crop_visible.get("ocr_map_labels", [])), 24)
                merged_visible["visible_urls"] = _merge_unique(list(merged_visible.get("visible_urls", [])), list(crop_visible.get("visible_urls", [])), 20)
                merged_visible["visible_time_strings"] = _merge_unique(list(merged_visible.get("visible_time_strings", [])), list(crop_visible.get("visible_time_strings", [])), 20)
                merged_visible["visible_location_strings"] = _merge_unique(list(merged_visible.get("visible_location_strings", [])), list(crop_visible.get("visible_location_strings", [])), 24)
                merged_visible["app_names"] = _merge_unique(list(merged_visible.get("app_names", [])), list(crop_visible.get("app_names", [])), 12)
                merged_visible["ocr_region_signals"] = list(merged_visible.get("ocr_region_signals", [])) + list(crop_visible.get("ocr_region_signals", []) or [])
                merged_visible["raw_text"] = (str(merged_visible.get("raw_text", "")) + "\n" + str(crop_visible.get("raw_text", ""))).strip()
                merged_visible["excerpt"] = (str(merged_visible.get("excerpt", "")) + "\n" + str(crop_visible.get("excerpt", ""))).strip()[:800]
                merged_visible["ocr_confidence"] = max(int(merged_visible.get("ocr_confidence", 0) or 0), int(crop_visible.get("ocr_confidence", 0) or 0))
                if crop_visible.get("ocr_note"):
                    zone_notes.append(f"{safe_label}: {crop_visible.get('ocr_note')}")
    except Exception as exc:
        manager.logger.exception("Manual crop OCR failed for %s", evidence_id)
        manager.db.log_action(manager.active_case_id, evidence_id, "OCR_CROP_FAILED", f"Manual crop OCR failed: {exc.__class__.__name__}")
        return None

    merged_visible["ocr_note"] = "Manual multi-zone crop OCR merged. " + " | ".join(zone_notes[:4])
    record.manual_crop_assets = crop_assets
    refresh_record_from_visible_signals(manager, record, merged_visible, mode="map_deep")
    build_validation_metrics(manager.records)
    manager.db.upsert_evidence(record)
    manager.db.log_action(manager.active_case_id, evidence_id, "OCR_CROP", f"Manual multi-zone crop OCR merged from {len(crop_assets)} crop(s).")
    manager._write_case_snapshot()
    return record

