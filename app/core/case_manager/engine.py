"""Case management engine implementation.

Moved from app.core.case_manager.service during v12.10.2 organization-only refactor.
The public import path remains app.core.case_manager.service and app.core.case_manager.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import zipfile
import logging
from dataclasses import fields
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
from typing import Callable, List, Optional

from ..anomalies import assign_duplicate_groups, assign_scene_groups, detect_anomalies, dominant_device, parse_timestamp
from ..backup_utils import safe_extract_zip
from ..case_db import CaseDatabase
from ..ai import run_ai_batch_assessment
from ..ai.osint_scene import predict_osint_scene
from ..ai.osint_content import analyze_image_content
from ..osint.pipeline import analyze_osint_signals
from ..osint.analyst_decisions import attach_decisions, default_decisions_for_hypotheses
from ..osint.cache import load_osint_cache, save_osint_cache
from ..osint.privacy_review import build_osint_privacy_review
from ..osint.location_estimator import estimate_location
from ..exif_service import (
    build_metadata_summary,
    build_osint_leads,
    build_time_assessment,
    classify_source,
    compute_perceptual_hash,
    extract_basic_image_info,
    extract_device_model,
    extract_embedded_text_hints,
    extract_exif,
    extract_file_times,
    extract_gps,
    extract_software,
    evaluate_gps_details,
    is_supported_image,
)
from ..visual_clues import extract_visible_text_clues, infer_source_profile, parse_derived_geo, profile_source_details
from ..vision.image_intelligence import analyze_image_details
from ..vision.pixel_stego import analyze_pixel_forensics
from ..hashing import compute_hashes
from ..map_intelligence import analyze_map_intelligence
from ..models import CaseInfo, CaseStats, EvidenceRecord
from ..explainability import apply_explainability
from ..validation_service import build_validation_metrics
from ..migrations import run_migrations


ProgressCallback = Callable[[int, str], None]
CancelCallback = Callable[[], bool]


class AnalysisCancelled(Exception):
    pass


class CaseManager:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.case_root = project_root / "case_data"
        self.case_root.mkdir(parents=True, exist_ok=True)
        self.migration_ledger = run_migrations(project_root, self.case_root)
        self.logs_dir = project_root / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("geotrace.case_manager")
        self.snapshot_warnings: List[str] = []
        self.db = CaseDatabase(self.case_root / "geotrace_case.db")
        self.records: List[EvidenceRecord] = []
        active = self.db.get_active_case()
        if active is None:
            active = self.new_case("Launch Candidate Case")
        self.active_case = active
        self.records = self.load_case_snapshot(self.active_case_id)

    @property
    def active_case_id(self) -> str:
        return self.active_case.case_id

    @property
    def active_case_name(self) -> str:
        return self.active_case.case_name

    def list_cases(self) -> List[CaseInfo]:
        return self.db.list_cases()

    def new_case(self, case_name: Optional[str] = None) -> CaseInfo:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        case_name = (case_name or f"Case {timestamp}").strip() or f"Case {timestamp}"
        slug = re.sub(r"[^A-Z0-9]+", "-", case_name.upper()).strip("-")[:26] or "CASE"
        case_id = f"GT-{timestamp}-{slug}-{uuid4().hex[:6].upper()}"
        self.db.create_case(case_id, case_name, set_active=True)
        self.active_case = self.db.get_active_case() or CaseInfo(
            case_id,
            case_name,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            0,
        )
        self.records = []
        self._write_case_snapshot()
        self.db.log_action(self.active_case_id, None, "CASE_OPEN", f"Opened case {self.active_case_name}")
        return self.active_case

    def switch_case(self, case_id: str) -> Optional[CaseInfo]:
        cases = {item.case_id: item for item in self.db.list_cases()}
        case = cases.get(case_id)
        if case is None:
            return None
        self.db.set_active_case(case_id)
        self.active_case = case
        self.records = self.load_case_snapshot(case_id)
        return self.active_case

    def load_images(
        self,
        paths: List[Path],
        progress_callback: Optional[ProgressCallback] = None,
        cancel_callback: Optional[CancelCallback] = None,
    ) -> List[EvidenceRecord]:
        files = self._collect_files(paths)
        if cancel_callback and cancel_callback():
            raise AnalysisCancelled()
        total = len(files)
        if total == 0:
            if progress_callback:
                progress_callback(100, "No supported evidence images found; active case was not changed.")
            self.db.log_action(
                self.active_case_id,
                None,
                "IMPORT_EMPTY",
                "No supported image files were found; existing case evidence was preserved.",
            )
            return list(self.records)

        existing = list(self.records)
        collected: List[EvidenceRecord] = []
        imported_ids: List[str] = []
        self.db.log_action(self.active_case_id, None, "IMPORT_BATCH", f"Queued {total} evidence item(s)")
        try:
            start_index = len(existing) + 1
            for index, file_path in enumerate(files, start=start_index):
                if cancel_callback and cancel_callback():
                    raise AnalysisCancelled()
                if progress_callback:
                    batch_pos = index - start_index + 1
                    progress_callback(max(5, int(batch_pos / max(total, 1) * 55)), f"Importing {file_path.name} ({batch_pos}/{total})")
                record = self._build_record(file_path, index)
                collected.append(record)
                imported_ids.append(record.evidence_id)

            if progress_callback:
                progress_callback(62, "Correlating duplicates and baseline devices…")
            combined = existing + collected
            assign_duplicate_groups(combined)
            assign_scene_groups(combined)
            self._propagate_duplicate_context(combined)
            if progress_callback:
                progress_callback(66, "Running AI-assisted batch risk review…")
            ai_findings = run_ai_batch_assessment(combined)
            baseline_device = dominant_device(combined)

            for index, record in enumerate(combined, start=1):
                if cancel_callback and cancel_callback():
                    raise AnalysisCancelled()
                if progress_callback:
                    progress_callback(70 + int(index / max(len(combined), 1) * 24), f"Scoring {record.evidence_id} ({index}/{len(combined)})")
                score, confidence, level, reasons, authenticity, metadata, technical, breakdown, contributors = detect_anomalies(
                    record,
                    baseline_device,
                    record.file_path,
                )
                ai_result = ai_findings.get(record.evidence_id)
                if ai_result is not None:
                    record.ai_provider = ai_result.provider
                    record.ai_score_delta = int(ai_result.score_delta)
                    record.ai_confidence = int(ai_result.confidence_delta)
                    record.ai_risk_label = ai_result.label
                    record.ai_summary = ai_result.summary
                    record.ai_flags = list(ai_result.flags)
                    record.ai_reasons = list(ai_result.reasons)
                    record.ai_breakdown = list(ai_result.breakdown)
                    record.ai_action_plan = list(ai_result.action_plan)
                    record.ai_corroboration_matrix = list(ai_result.corroboration_matrix)
                    record.ai_case_links = list(ai_result.case_links)
                    record.ai_evidence_graph = list(ai_result.evidence_graph)
                    record.ai_contradiction_explainer = list(ai_result.contradiction_explainer)
                    record.ai_courtroom_readiness = ai_result.courtroom_readiness
                    record.ai_next_best_action = ai_result.next_best_action
                    record.ai_privacy_audit = ai_result.privacy_audit
                    record.ai_executive_note = ai_result.executive_note
                    record.ai_priority_rank = int(ai_result.priority_rank)
                    record.evidence_strength_label = ai_result.evidence_strength
                    record.evidence_strength_score = int(ai_result.evidence_strength_score)
                    record.evidence_strength_reasons = list(ai_result.evidence_strength_reasons)
                    record.evidence_strength_limitations = list(ai_result.evidence_strength_limitations)
                    if ai_result.score_delta:
                        score = min(100, score + int(ai_result.score_delta))
                        confidence = min(98, confidence + int(ai_result.confidence_delta))
                        reasons = list(dict.fromkeys(reasons + ai_result.reasons))
                        breakdown = breakdown + ai_result.breakdown
                        contributors = list(dict.fromkeys(contributors + ai_result.contributors))
                        recalculated_level = "High" if score >= 70 else "Medium" if score >= 35 else "Low"
                        rank = {"Low": 0, "Medium": 1, "High": 2}
                        level = recalculated_level if rank[recalculated_level] > rank.get(level, 0) else level

                record.suspicion_score = score
                record.confidence_score = confidence
                record.risk_level = level
                record.anomaly_reasons = reasons
                record.authenticity_score = authenticity
                record.metadata_score = metadata
                record.technical_score = technical
                record.score_breakdown = breakdown
                record.anomaly_contributors = contributors
                record.integrity_status, record.integrity_note = self._derive_integrity_status(record)
                scene_prediction = predict_osint_scene(record)
                record.osint_scene_label = scene_prediction.label
                record.osint_scene_confidence = scene_prediction.confidence
                record.osint_scene_summary = scene_prediction.summary
                record.osint_scene_reasons = list(scene_prediction.reasons)
                record.detected_map_context = scene_prediction.detected_map_context
                record.possible_place = scene_prediction.possible_place
                record.map_confidence = max(scene_prediction.map_confidence, record.map_intelligence_confidence)
                content_profile = analyze_image_content(record)
                record.osint_content_label = content_profile.label
                record.osint_content_confidence = content_profile.confidence
                record.osint_content_summary = content_profile.summary
                record.osint_content_tags = list(content_profile.content_tags)
                record.osint_visual_cues = list(content_profile.visual_cues)
                record.osint_text_cues = list(content_profile.text_cues)
                record.osint_location_hypotheses = list(content_profile.location_hypotheses)
                record.osint_source_context = content_profile.source_context
                record.osint_content_limitations = list(content_profile.limitations)
                record.osint_next_actions = list(content_profile.next_actions)
                self._apply_osint_signal_profile(record)
                self._apply_location_estimate(record)
                apply_explainability(record)
                record.analyst_verdict = self._derive_analyst_verdict(record)
                record.courtroom_notes = self._derive_courtroom_notes(record)
                if not record.osint_leads:
                    record.osint_leads = build_osint_leads(
                        record.file_path,
                        record.source_type,
                        record.timestamp,
                        record.timestamp_source,
                        record.device_model,
                        record.software,
                        record.gps_display,
                        record.width,
                        record.height,
                    )
                if record.osint_scene_summary and record.osint_scene_summary not in record.osint_leads:
                    record.osint_leads.append(record.osint_scene_summary)
                record.osint_leads = record.osint_leads[:8]
                self.db.upsert_evidence(record)
                self.db.log_action(
                    record.case_id,
                    record.evidence_id,
                    "ANALYZE",
                    f"Risk={level}, Score={score}, Confidence={confidence}, AI_delta={record.ai_score_delta}, Integrity={record.integrity_status}",
                )
                record.custody_event_summary = self.db.summarize_evidence_events(record.case_id, record.evidence_id)

            self.records = combined
            build_validation_metrics(self.records)
            self._write_case_snapshot()
            self.db.log_action(self.active_case_id, None, "BATCH_COMPLETE", f"Analysis finished for {len(self.records)} item(s)")
            if progress_callback:
                progress_callback(100, f"Analysis finished — {len(self.records)} evidence item(s)")
            return self.records
        except AnalysisCancelled:
            self._rollback_import(collected, imported_ids, "cancelled")
            self.db.log_action(self.active_case_id, None, "IMPORT_CANCELLED", f"Import cancelled; rolled back {len(collected)} staged item(s). Existing case evidence preserved.")
            raise
        except Exception:
            self.logger.exception("Import/analyze batch failed; rolling back staged evidence")
            self._rollback_import(collected, imported_ids, "failed")
            self.db.log_action(self.active_case_id, None, "IMPORT_FAILED", f"Import failed; rolled back {len(collected)} staged item(s). Existing case evidence preserved.")
            raise

    def _rollback_import(self, collected: List[EvidenceRecord], imported_ids: List[str], reason: str) -> None:
        """Best-effort rollback for cancelled/failed imports.

        Evidence already committed before the batch is preserved. Only records staged in the current batch are
        removed from the working evidence folder and database index; custody events remain as an audit trail.
        """
        if imported_ids:
            try:
                self.db.delete_evidence(self.active_case_id, imported_ids)
            except Exception:
                self.logger.exception("Failed to rollback database rows for %s import", reason)
        for record in collected:
            for path in [record.working_copy_path, record.file_path]:
                try:
                    if path and Path(path).exists() and (self.case_root / self.active_case_id) in Path(path).parents:
                        Path(path).unlink(missing_ok=True)
                except Exception:
                    self.logger.exception("Failed to remove staged evidence during %s rollback: %s", reason, path)
            try:
                carved_dir = self.case_root / self.active_case_id / "carved_payloads" / record.evidence_id
                if carved_dir.exists():
                    shutil.rmtree(carved_dir, ignore_errors=True)
            except Exception:
                self.logger.exception("Failed to remove carved payloads during %s rollback", reason)
        self.records = list(self.records)
        self._write_case_snapshot()

    def _collect_files(self, paths: List[Path]) -> List[Path]:
        collected: List[Path] = []
        for file_path in paths:
            if file_path.is_dir():
                for child in sorted(file_path.rglob("*")):
                    if child.is_file() and is_supported_image(child):
                        collected.append(child)
            elif file_path.is_file() and is_supported_image(file_path):
                collected.append(file_path)
        return collected

    def _stage_evidence_file(self, source_path: Path, evidence_id: str) -> Path:
        vault = self.case_root / self.active_case_id / "evidence"
        vault.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", source_path.name).strip("._") or f"{evidence_id}{source_path.suffix.lower()}"
        target = vault / f"{evidence_id}__{safe_name}"
        if source_path.resolve() == target.resolve():
            return target
        shutil.copy2(source_path, target)
        return target

    def _carve_hidden_payloads(self, evidence_id: str, recoveries: List[dict]) -> List[str]:
        """Recover suspicious appended payloads using inert file names.

        The original detector may identify HTML, SVG, ZIP, PDF, or JSON-like payloads.
        For analyst safety, recovered bytes are always written as .payload.bin and
        the detected type/offset is stored in a JSON sidecar instead of giving the
        payload an executable or auto-openable extension.
        """
        if not recoveries:
            return []
        carved_root = self.case_root / self.active_case_id / "carved_payloads" / evidence_id
        carved_root.mkdir(parents=True, exist_ok=True)
        carved_files: List[str] = []
        for index, segment in enumerate(recoveries[:4], start=1):
            blob = segment.get("bytes")
            if not isinstance(blob, (bytes, bytearray)) or not blob:
                continue
            kind = re.sub(r"[^A-Za-z0-9_-]+", "_", str(segment.get("kind", "payload"))).strip("_") or "payload"
            output = carved_root / f"{evidence_id}_segment_{index:02d}_{kind}.payload.bin"
            output.write_bytes(bytes(blob))
            metadata = {
                "evidence_id": evidence_id,
                "segment_index": index,
                "detected_type": str(segment.get("kind", "payload")),
                "original_extension_suggestion": str(segment.get("extension", ".bin")),
                "offset": segment.get("offset"),
                "length": segment.get("length"),
                "label": str(segment.get("label", "Recovered payload segment")),
                "safety_note": "Payload bytes are intentionally stored as .payload.bin to prevent accidental execution or unsafe browser rendering.",
            }
            output.with_suffix(output.suffix + ".metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            carved_files.append(str(output))
        return carved_files

    def _build_record(self, file_path: Path, index: int) -> EvidenceRecord:
        original_path = file_path
        evidence_id = f"IMG-{index:03d}"
        source_hashes = compute_hashes(original_path)
        staged_path = self._stage_evidence_file(original_path, evidence_id)
        working_hashes = compute_hashes(staged_path)
        hashes = working_hashes
        copy_verified = source_hashes.get("sha256") == working_hashes.get("sha256")
        acquisition_note = (
            "Source and working-copy SHA-256 hashes match; staged evidence copy verified."
            if copy_verified
            else "WARNING: source and working-copy SHA-256 hashes differ; re-acquire this evidence before relying on it."
        )
        exif = extract_exif(staged_path)
        exif_warning = str(exif.get("__warning__", "")).strip()
        basic = extract_basic_image_info(staged_path)
        device_model, camera_make = extract_device_model(exif)
        software = extract_software(exif)
        lat, lon, altitude, gps_display = extract_gps(exif)
        imported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        created_time, modified_time, created_time_note = extract_file_times(original_path)
        metadata = build_metadata_summary(exif)
        normalized_exif = {k: v for k, v in exif.items() if k not in {"__raw_tags__", "__warning__"}}
        container_metadata = {
            k: v for k, v in normalized_exif.items()
            if k.startswith("ImageInfo ") or k.startswith("PNG ")
        }
        native_exif = {
            k: v for k, v in normalized_exif.items()
            if k not in container_metadata
        }
        initial_source_type = classify_source(
            original_path,
            normalized_exif,
            software,
            int(basic["width"]),
            int(basic["height"]),
            str(basic["parser_status"]),
        )
        embedded_scan = extract_embedded_text_hints(staged_path, str(basic["format_name"]))
        pixel_profile = analyze_pixel_forensics(staged_path)
        image_profile = analyze_image_details(staged_path)
        carved_files = self._carve_hidden_payloads(evidence_id, list(embedded_scan.get("recoverable_segments", [])))
        lower_name = original_path.name.lower()
        is_map_candidate = any(token in lower_name for token in ("map", "maps", "route", "directions", "geo", "location", "cairo", "giza", "القاهرة", "الجيزة"))
        ocr_mode = "map_deep" if is_map_candidate else None
        visible = extract_visible_text_clues(
            staged_path,
            int(basic["width"]),
            int(basic["height"]),
            source_hint=initial_source_type,
            force=(initial_source_type in {"Screenshot", "Screenshot / Export", "Messaging Export"} or (not normalized_exif and file_path.suffix.lower() == ".png") or is_map_candidate),
            mode=ocr_mode,
            cache_dir=self.case_root / self.active_case_id / "ocr_cache",
        )
        map_intel = analyze_map_intelligence(staged_path, visible)
        visible_app = str(visible.get("app_detected", "Unknown"))
        app_detected_runtime = map_intel.app_detected if visible_app in {"", "Unknown"} and map_intel.app_detected != "Unknown" else visible_app
        map_text_candidates = [
            *list(visible.get("lines", [])),
            *list(visible.get("ocr_map_labels", [])),
            *map_intel.place_candidates,
            *map_intel.landmarks_detected,
            map_intel.candidate_city,
            map_intel.candidate_area,
            original_path.stem,
            *list(embedded_scan.get("context_strings", [])),
        ]
        derived_geo = parse_derived_geo(
            map_text_candidates,
            list(visible.get("visible_urls", [])) + list(embedded_scan.get("urls", [])),
            source_type=initial_source_type,
        )
        source_profile = infer_source_profile(
            staged_path,
            source_type=initial_source_type,
            width=int(basic["width"]),
            height=int(basic["height"]),
            has_exif=bool(normalized_exif),
            software=software,
            visible_urls=list(visible.get("visible_urls", [])),
            app_detected=app_detected_runtime,
            visible_lines=list(visible.get("lines", [])),
            map_labels=list(visible.get("ocr_map_labels", [])) + map_intel.place_candidates + map_intel.landmarks_detected,
        )
        source_type = str(source_profile.get("type", initial_source_type))
        source_subtype = str(source_profile.get("subtype", source_type))
        if map_intel.detected and source_type in {"Screenshot", "Screenshot / Export"}:
            source_subtype = "Map Screenshot" if not map_intel.route_overlay_detected else "Navigation / Route Screenshot"
        source_profile_confidence = max(int(source_profile.get("confidence", 0)), map_intel.confidence if map_intel.detected else 0)
        source_profile_reasons = list(source_profile.get("reasons", []))
        time_assessment = build_time_assessment(normalized_exif, original_path, list(visible.get("visible_time_strings", [])))
        timestamp = str(time_assessment.get("timestamp", "Unknown"))
        timestamp_source = str(time_assessment.get("source", "Unavailable"))
        timestamp_confidence = int(time_assessment.get("confidence", 0))
        timestamp_verdict = str(time_assessment.get("verdict", "No trusted time anchor recovered yet."))
        gps_source, gps_confidence, gps_verification = evaluate_gps_details(normalized_exif, lat, lon, altitude, source_type)
        if lat is not None and lon is not None:
            geo_status = f"Native GPS recovered from {gps_source}."
        elif derived_geo.get("latitude") is not None and derived_geo.get("longitude") is not None:
            geo_status = "No native GPS recovered, but screenshot-derived location clues were parsed from visible content."
        elif str(visible.get("ocr_map_context", "")).startswith("Map/place context"):
            labels = list(visible.get("ocr_map_labels", []))
            label_note = f" Possible place clue: {labels[0]}." if labels else ""
            geo_status = "No native GPS recovered, but map/place context was detected in the visible content." + label_note
        elif map_intel.detected:
            route_note = " Route overlay detected." if map_intel.route_overlay_detected else ""
            city_note = f" Candidate city: {map_intel.candidate_city}." if map_intel.candidate_city != "Unavailable" else ""
            geo_status = "No native GPS recovered, but map intelligence detected a map/navigation screenshot." + route_note + city_note
        else:
            geo_status = "No native GPS recovered."
        record = EvidenceRecord(
            case_id=self.active_case_id,
            case_name=self.active_case_name,
            evidence_id=evidence_id,
            file_path=staged_path,
            original_file_path=original_path,
            working_copy_path=staged_path,
            source_sha256=source_hashes.get("sha256", ""),
            source_md5=source_hashes.get("md5", ""),
            working_sha256=working_hashes.get("sha256", ""),
            working_md5=working_hashes.get("md5", ""),
            copy_verified=copy_verified,
            acquisition_note=acquisition_note,
            file_name=original_path.name,
            sha256=hashes["sha256"],
            md5=hashes["md5"],
            perceptual_hash=compute_perceptual_hash(staged_path),
            file_size=staged_path.stat().st_size,
            imported_at=imported_at,
            exif=native_exif,
            raw_exif=normalized_exif,
            container_metadata=container_metadata,
            exif_warning=exif_warning,
            timestamp=timestamp,
            timestamp_source=timestamp_source,
            timestamp_confidence=timestamp_confidence,
            timestamp_verdict=timestamp_verdict,
            created_time=created_time,
            created_time_note=created_time_note,
            modified_time=modified_time,
            device_model=device_model,
            camera_make=camera_make,
            software=software,
            source_type=source_type,
            source_subtype=source_subtype,
            source_profile_confidence=source_profile_confidence,
            source_profile_reasons=source_profile_reasons,
            environment_profile=str(visible.get("environment_profile", "Unknown")),
            app_detected=app_detected_runtime,
            format_name=str(basic["format_name"]),
            color_mode=str(basic["color_mode"]),
            has_alpha=bool(basic["has_alpha"]),
            dpi=str(basic["dpi"]),
            orientation=metadata["orientation"],
            lens_model=metadata["lens_model"],
            iso=metadata["iso"],
            exposure_time=metadata["exposure_time"],
            f_number=metadata["f_number"],
            focal_length=metadata["focal_length"],
            artist=metadata["artist"],
            copyright_notice=metadata["copyright_notice"],
            gps_latitude=lat,
            gps_longitude=lon,
            gps_altitude=altitude,
            gps_display=gps_display,
            gps_source=gps_source,
            gps_confidence=gps_confidence,
            gps_verification=gps_verification,
            derived_latitude=derived_geo.get("latitude"),
            derived_longitude=derived_geo.get("longitude"),
            derived_geo_display=str(derived_geo.get("display", "Unavailable")),
            derived_geo_source=str(derived_geo.get("source", "Unavailable")),
            derived_geo_confidence=int(derived_geo.get("confidence", 0)),
            derived_geo_note=str(derived_geo.get("note", "No screenshot-derived geolocation clue recovered.")),
            geo_status=geo_status,
            width=int(basic["width"]),
            height=int(basic["height"]),
            megapixels=float(basic["megapixels"]),
            aspect_ratio=str(basic["aspect_ratio"]),
            brightness_mean=float(basic["brightness_mean"]),
            parser_status=str(basic["parser_status"]),
            preview_status=str(basic["preview_status"]),
            structure_status=str(basic["structure_status"]),
            format_signature=str(basic["format_signature"]),
            format_trust=str(basic["format_trust"]),
            signature_status=str(basic["signature_status"]),
            parse_error=str(basic["parse_error"]),
            frame_count=int(basic["frame_count"]),
            is_animated=bool(basic["is_animated"]),
            animation_duration_ms=int(basic["animation_duration_ms"]),
            extracted_strings=list(embedded_scan.get("strings", [])),
            visible_text_lines=list(visible.get("lines", [])),
            ocr_raw_text=str(visible.get("raw_text", "")),
            ocr_note=str(visible.get("ocr_note", "OCR not attempted.")),
            ocr_confidence=int(visible.get("ocr_confidence", 0)),
            ocr_analyst_relevance=str(visible.get("ocr_analyst_relevance", "OCR not attempted.")),
            ocr_region_signals=list(visible.get("ocr_region_signals", [])),
            ocr_app_names=list(visible.get("app_names", [])),
            ocr_username_entities=list(visible.get("ocr_username_entities", [])),
            ocr_map_labels=list(visible.get("ocr_map_labels", [])),
            visible_urls=list(visible.get("visible_urls", [])),
            ocr_url_entities=list(visible.get("visible_urls", [])),
            visible_time_strings=list(visible.get("visible_time_strings", [])),
            ocr_time_entities=list(visible.get("visible_time_strings", [])),
            visible_location_strings=list(visible.get("visible_location_strings", [])),
            ocr_location_entities=list(visible.get("visible_location_strings", [])),
            possible_geo_clues=list(derived_geo.get("possible_geo_clues", [])),
            visible_text_excerpt=str(visible.get("excerpt", "")),
            hidden_code_indicators=list(embedded_scan.get("code_indicators", [])),
            hidden_finding_types=list(embedded_scan.get("finding_types", [])),
            hidden_code_summary=str(embedded_scan.get("summary", "No embedded code-like content detected.")),
            hidden_content_overview=str(embedded_scan.get("overview", "No embedded text payloads or code-like markers detected.")),
            hidden_context_summary=str(embedded_scan.get("context_summary", "No visible or embedded text context was retained.")),
            hidden_suspicious_embeds=list(embedded_scan.get("suspicious_embeds", [])),
            hidden_payload_markers=list(embedded_scan.get("payload_markers", [])),
            hidden_container_findings=list(embedded_scan.get("container_findings", [])),
            hidden_carved_files=carved_files,
            hidden_carved_summary=str(embedded_scan.get("carved_summary", "No carved payload segments were recovered.")),
            stego_suspicion=str(embedded_scan.get("stego_suspicion", "No strong steganography or appended-payload indicator was detected.")),
            pixel_hidden_score=int(pixel_profile.score),
            pixel_hidden_verdict=pixel_profile.verdict,
            pixel_hidden_summary=pixel_profile.summary,
            pixel_hidden_indicators=list(pixel_profile.indicators),
            pixel_lsb_strings=list(pixel_profile.lsb_strings),
            pixel_alpha_findings=list(pixel_profile.alpha_findings),
            pixel_channel_notes=list(pixel_profile.channel_notes),
            pixel_hidden_metrics=dict(pixel_profile.metrics),
            pixel_hidden_limitations=list(pixel_profile.limitations),
            pixel_hidden_next_actions=list(pixel_profile.next_actions),
            image_detail_label=image_profile.label,
            image_detail_confidence=int(image_profile.confidence),
            image_detail_summary=image_profile.summary,
            image_detail_cues=list(image_profile.cues),
            image_layout_hints=list(image_profile.layout_hints),
            image_object_hints=list(image_profile.object_hints),
            image_quality_flags=list(image_profile.quality_flags),
            image_detail_metrics=dict(image_profile.metrics),
            image_detail_limitations=list(image_profile.limitations),
            image_detail_next_actions=list(image_profile.next_actions),
            image_attention_regions=list(getattr(image_profile, "attention_regions", [])),
            image_scene_descriptors=list(getattr(image_profile, "scene_descriptors", [])),
            image_analysis_methodology=list(getattr(image_profile, "methodology_steps", [])),
            image_performance_notes=list(getattr(image_profile, "performance_notes", [])),
            urls_found=list(embedded_scan.get("urls", [])),
            time_candidates=list(time_assessment.get("candidates", [])),
            time_conflicts=list(time_assessment.get("conflicts", [])),
        )
        record.integrity_status, record.integrity_note = self._derive_integrity_status(record)
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
        record.place_candidate_rankings = list(map_intel.place_candidate_rankings)
        record.filename_location_hints = list(getattr(map_intel, "filename_location_hints", []))
        scene_prediction = predict_osint_scene(record)
        record.osint_scene_label = scene_prediction.label
        record.osint_scene_confidence = scene_prediction.confidence
        record.osint_scene_summary = scene_prediction.summary
        record.osint_scene_reasons = list(scene_prediction.reasons)
        record.detected_map_context = scene_prediction.detected_map_context
        record.possible_place = scene_prediction.possible_place
        record.map_confidence = max(scene_prediction.map_confidence, record.map_intelligence_confidence)
        content_profile = analyze_image_content(record)
        record.osint_content_label = content_profile.label
        record.osint_content_confidence = content_profile.confidence
        record.osint_content_summary = content_profile.summary
        record.osint_content_tags = list(content_profile.content_tags)
        record.osint_visual_cues = list(content_profile.visual_cues)
        record.osint_text_cues = list(content_profile.text_cues)
        record.osint_location_hypotheses = list(content_profile.location_hypotheses)
        record.osint_source_context = content_profile.source_context
        record.osint_content_limitations = list(content_profile.limitations)
        record.osint_next_actions = list(content_profile.next_actions)
        self._apply_osint_signal_profile(record)
        self._apply_location_estimate(record)
        if record.map_intelligence_summary and record.detected_map_context.startswith("No clear"):
            record.detected_map_context = record.map_intelligence_summary
        record.osint_leads = build_osint_leads(
            original_path,
            source_type,
            timestamp,
            timestamp_source,
            record.device_model,
            software,
            gps_display,
            record.width,
            record.height,
        )
        if record.derived_geo_display != "Unavailable":
            record.osint_leads.append(
                f"Visible map/location clue recovered at {record.derived_geo_display}. Preserve any browser history, shared URLs, or chat context that can validate this screenshot-derived location."
            )
        if str(visible.get("ocr_map_context", "")).startswith("Map/place") and record.derived_geo_display == "Unavailable":
            record.osint_leads.append(
                "Map/place UI context was detected, but no stable coordinate or venue label was recovered. Use deep OCR, source app history, or the original map/share link for confirmation."
            )
        if record.visible_urls:
            record.osint_leads.append(f"Visible URL clue(s): {', '.join(record.visible_urls[:2])}.")
        if record.visible_text_excerpt:
            record.osint_leads.append("On-screen text was recovered through OCR. Preserve the screenshot origin and any matching browser/application logs.")
        if record.possible_geo_clues:
            record.osint_leads.append("Possible geo leads from OCR/map labels: " + ", ".join(record.possible_geo_clues[:3]) + ".")
        if record.source_profile_reasons:
            record.osint_leads.append("Source-profile reasons: " + "; ".join(record.source_profile_reasons[:2]) + ".")
        if record.osint_scene_summary:
            record.osint_leads.append(record.osint_scene_summary)
        record.osint_leads = record.osint_leads[:8]
        self.db.log_action(record.case_id, record.evidence_id, "IMPORT", f"Imported {record.file_name} | source_sha256={record.source_sha256} | working_sha256={record.working_sha256} | copy_verified={record.copy_verified}")
        return record

    def _propagate_duplicate_context(self, records: List[EvidenceRecord]) -> None:
        """Carry high-confidence contextual anchors across confirmed duplicate groups."""
        groups: dict[str, list[EvidenceRecord]] = {}
        for record in records:
            if record.duplicate_group:
                groups.setdefault(record.duplicate_group, []).append(record)
        for group_records in groups.values():
            geo_anchor = next(
                (
                    record for record in group_records
                    if record.derived_geo_display != "Unavailable"
                    and record.derived_latitude is not None
                    and record.derived_longitude is not None
                ),
                None,
            )
            if geo_anchor is None:
                continue
            for record in group_records:
                if record is geo_anchor or record.derived_geo_display != "Unavailable":
                    continue
                record.derived_latitude = geo_anchor.derived_latitude
                record.derived_longitude = geo_anchor.derived_longitude
                record.derived_geo_display = geo_anchor.derived_geo_display
                record.derived_geo_source = f"Duplicate peer {geo_anchor.evidence_id}"
                record.derived_geo_confidence = max(0, min(geo_anchor.derived_geo_confidence - 8, 70))
                record.derived_geo_note = (
                    f"Derived location context inherited from duplicate/near-duplicate peer {geo_anchor.evidence_id}; "
                    "treat as contextual until manually corroborated."
                )
                record.possible_geo_clues = list(dict.fromkeys(record.possible_geo_clues + [geo_anchor.derived_geo_display]))
                if record.geo_status == "No native GPS recovered.":
                    record.geo_status = "No native GPS recovered, but duplicate-peer derived geo context is available."

    def _derive_integrity_status(self, record: EvidenceRecord) -> tuple[str, str]:
        if record.source_sha256 and record.working_sha256 and not record.copy_verified:
            return "Review Required", "Source/working-copy hashes do not match. Re-acquire the evidence before relying on this item."
        if record.parser_status != "Valid":
            return "Review Required", "Decoder could not fully parse the media. Treat structure validation as incomplete until a second parser confirms it."
        if record.signature_status == "Mismatch":
            return "Review Required", "File extension and detected binary signature disagree. Structural integrity needs analyst review."
        if record.format_trust in {"Verified"} and not record.exif_warning:
            return "Verified", "Parser, signature, and hashing checks completed successfully for this container."
        if record.format_trust in {"Verified", "Header-only", "Weak"}:
            note_bits = ["The file rendered successfully, but validation is only partial."]
            if record.exif_warning:
                note_bits.append(record.exif_warning)
            if record.format_trust in {"Header-only", "Weak"}:
                note_bits.append("Container trust is limited because only partial header confidence is available.")
            return "Partial", " ".join(note_bits)
        return "Pending Review", "Structural verification has not been finalized yet."


    def _apply_osint_signal_profile(self, record: EvidenceRecord) -> None:
        """Attach structured OSINT entities, hypothesis cards, and corroboration rows.

        The older string lists are kept for backwards compatibility. This structured layer
        powers AI Guardian cards and the future OSINT Workbench without rewriting import logic.
        """
        profile = analyze_osint_signals(record)
        record.osint_entities = [entity.to_dict() for entity in profile.entities]
        hypothesis_cards = [hypothesis.to_dict() for hypothesis in profile.hypotheses]
        for index, card in enumerate(hypothesis_cards):
            card["evidence_id"] = record.evidence_id
            card.setdefault("hypothesis_id", f"{record.evidence_id}:hypothesis:{index:02d}")
        decisions = default_decisions_for_hypotheses(record.evidence_id, hypothesis_cards)
        record.osint_analyst_decisions = [decision.to_dict() for decision in decisions]
        record.osint_hypothesis_cards = attach_decisions(hypothesis_cards, decisions)
        record.osint_corroboration_matrix = [item.to_dict() for item in profile.corroboration_matrix]
        record.ctf_clues = [item.to_dict() for item in profile.ctf_profile.clues]
        record.geo_candidates = [item.to_dict() for item in profile.ctf_profile.candidates]
        record.ctf_search_queries = list(profile.ctf_profile.search_queries)
        record.location_solvability_score = int(profile.ctf_profile.solvability_score or 0)
        record.location_solvability_label = profile.ctf_profile.solvability_label
        record.ctf_country_region_profile = profile.ctf_profile.country_region_profile
        record.ctf_landmark_matches = list(profile.ctf_profile.landmark_matches)
        record.ctf_writeup = profile.ctf_profile.writeup
        record.ctf_online_mode_status = profile.ctf_profile.online_mode_status
        record.ctf_image_existence_profile = dict(profile.ctf_profile.image_existence_profile)
        record.ctf_online_privacy_review = dict(profile.ctf_profile.online_privacy_review)
        record.osint_privacy_review = build_osint_privacy_review([record])
        cache_path = save_osint_cache(self.case_root / self.active_case_id / "osint_cache", record)
        record.osint_cache_status = f"Structured OSINT cache written: {cache_path.name}" if cache_path else "Structured OSINT cache was not written."
        if profile.hypotheses:
            readable = [f"{item.title}: {item.claim} ({item.strength}, {item.confidence}%)" for item in profile.hypotheses[:6]]
            merged = list(record.osint_location_hypotheses) + readable
            # Preserve legacy text output while surfacing the richer cards.
            seen = set()
            record.osint_location_hypotheses = []
            for item in merged:
                key = item.lower()
                if key not in seen:
                    seen.add(key)
                    record.osint_location_hypotheses.append(item)
                if len(record.osint_location_hypotheses) >= 10:
                    break

    def _apply_location_estimate(self, record: EvidenceRecord) -> None:
        estimate = estimate_location(record)
        record.location_estimate_label = estimate.best_location
        record.location_estimate_confidence = int(estimate.confidence or 0)
        record.location_estimate_scope = estimate.scope
        record.location_estimate_source_tier = estimate.source_tier
        record.location_estimate_summary = estimate.summary
        record.location_estimate_supporting_signals = list(estimate.supporting_signals)
        record.location_estimate_limitations = list(estimate.limitations)
        record.location_estimate_next_actions = list(estimate.next_actions)
        record.location_estimate_candidates = list(estimate.alternate_candidates)

        if estimate.best_location != "Unavailable":
            if record.possible_place in {"Unavailable", "Unknown", "N/A", ""}:
                record.possible_place = estimate.best_location
            if estimate.confidence > int(getattr(record, "map_confidence", 0) or 0):
                record.map_confidence = int(estimate.confidence or 0)

        additions: list[str] = []
        if estimate.summary and estimate.summary not in record.osint_location_hypotheses:
            additions.append(estimate.summary)
        for signal in estimate.supporting_signals[:3]:
            line = f"Support: {signal}"
            if line not in record.osint_location_hypotheses:
                additions.append(line)
        if additions:
            merged = list(record.osint_location_hypotheses) + additions
            deduped: list[str] = []
            seen: set[str] = set()
            for item in merged:
                key = str(item).lower()
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(item)
                if len(deduped) >= 12:
                    break
            record.osint_location_hypotheses = deduped

    def _derive_analyst_verdict(self, record: EvidenceRecord) -> str:
        evidence_bits: list[str] = []
        if record.metadata_issues:
            evidence_bits.append(record.metadata_issues[0])
        if record.hidden_container_findings:
            evidence_bits.append(record.hidden_container_findings[0])
        elif record.hidden_code_indicators:
            evidence_bits.append(record.hidden_code_indicators[0])
        if record.duplicate_group:
            evidence_bits.append(record.similarity_note)
        if record.gps_ladder:
            evidence_bits.append(record.gps_ladder[min(1, len(record.gps_ladder) - 1)])
        if record.time_conflicts:
            evidence_bits.append(record.time_conflicts[0])
        if record.ai_executive_note and record.ai_executive_note != "No AI priority note generated yet.":
            evidence_bits.append(record.ai_executive_note)
        elif record.ai_flags:
            evidence_bits.append(record.ai_summary)
        evidence_bits = evidence_bits[:4]
        recommendation = record.metadata_recommendations[0] if record.metadata_recommendations else record.score_next_step
        return (
            f"Primary issue: {record.score_primary_issue}. "
            f"Why it matters: {record.score_reason} "
            f"Evidence: {' | '.join(evidence_bits) if evidence_bits else record.metadata_issue_summary}. "
            f"Recommended next step: {recommendation}"
        )

    def _derive_courtroom_notes(self, record: EvidenceRecord) -> str:
        strengths: list[str] = []
        limitations: list[str] = []
        if record.timestamp_confidence >= 80:
            strengths.append(f"Time anchor available via {record.timestamp_source} ({record.timestamp_confidence}%).")
        elif record.timestamp_confidence > 0:
            limitations.append(f"Time anchor is {record.timestamp_source.lower()} and should be corroborated externally.")
        else:
            limitations.append("No trustworthy native time anchor was recovered.")
        if record.has_gps:
            strengths.append(f"Native GPS recovered: {record.gps_display}.")
        elif record.derived_geo_display != "Unavailable":
            limitations.append("Location clue is screenshot/browser-derived rather than native EXIF GPS.")
        else:
            limitations.append("No native GPS available; location claims require external corroboration.")
        if record.time_conflicts:
            limitations.append("Time candidates conflict materially across filename, visible, or filesystem anchors.")
        if record.ai_flags:
            limitations.append(f"AI-assisted batch review flagged: {', '.join(record.ai_flags[:3])}. Treat this as triage guidance until manually corroborated.")
        elif record.ai_action_plan:
            strengths.append("AI corroboration plan generated for structured follow-up.")
        if record.parser_status != "Valid" or record.signature_status == "Mismatch":
            limitations.append("Structure/parser issues reduce courtroom confidence until a second parser confirms the file.")
        if record.hidden_code_indicators:
            limitations.append("Container includes code-like or credential-like strings that must be explained before courtroom use.")
        elif record.hidden_suspicious_embeds:
            limitations.append("Container includes structural hidden-content warnings that still need analyst explanation.")
        if record.duplicate_group:
            strengths.append(f"Duplicate relation available: {record.duplicate_relation or record.duplicate_group}.")
        if record.visible_text_excerpt:
            strengths.append("Visible OCR clues were preserved for later corroboration.")
        if record.integrity_status:
            strengths.append(f"Integrity status: {record.integrity_status}.")
        if not strengths:
            strengths.append("Hashes and case-scoped custody logging remain available.")
        return "Strengths: " + " ".join(strengths) + " Limitations: " + " ".join(limitations)

    def build_stats(self) -> CaseStats:
        stats = CaseStats()
        stats.total_images = len(self.records)
        stats.gps_enabled = sum(1 for record in self.records if record.has_gps)
        stats.anomaly_count = sum(1 for record in self.records if record.risk_level != "Low")
        stats.device_count = len({record.device_model for record in self.records if record.device_model not in {"", "Unknown"}})
        stats.timeline_span = self._timeline_span()
        checked = sum(1 for record in self.records if record.integrity_status != "Pending Review")
        stats.integrity_summary = f"{checked}/{len(self.records)} Checked" if self.records else "0/0 Checked"
        stats.screenshots_count = sum(1 for record in self.records if "Screenshot" in record.source_type or "Messaging" in record.source_type)
        stats.duplicates_count = len({record.duplicate_group for record in self.records if record.duplicate_group})
        stats.avg_score = round(sum(r.suspicion_score for r in self.records) / len(self.records)) if self.records else 0
        stats.parser_issue_count = sum(1 for record in self.records if record.parser_status != "Valid" or record.signature_status == "Mismatch")
        stats.hidden_content_count = sum(1 for record in self.records if record.hidden_code_indicators or record.hidden_suspicious_embeds or record.hidden_carved_files)
        stats.bookmarked_count = sum(1 for record in self.records if record.bookmarked)
        stats.validation_summary = self.validation_summary()
        return stats

    def update_note(self, evidence_id: str, note: str) -> None:
        record = self.get_record(evidence_id)
        if record is None:
            return
        record.note = note
        self.db.upsert_evidence(record)
        self.db.log_action(self.active_case_id, evidence_id, "NOTE", note or "Note cleared")
        self._write_case_snapshot()

    def update_tags(self, evidence_id: str, tags: str, bookmarked: bool) -> None:
        record = self.get_record(evidence_id)
        if record is None:
            return
        record.tags = tags
        record.bookmarked = bookmarked
        self.db.upsert_evidence(record)
        self.db.log_action(self.active_case_id, evidence_id, "TAG", f"Tags={tags or 'None'} | Bookmarked={bookmarked}")
        self._write_case_snapshot()

    def get_record(self, evidence_id: str) -> Optional[EvidenceRecord]:
        for record in self.records:
            if record.evidence_id == evidence_id:
                return record
        return None


    def rescan_record_osint(self, evidence_id: str, *, mode: str = "map_deep", force: bool = True) -> Optional[EvidenceRecord]:
        """Re-run OCR/map/OSINT extraction for a selected record without re-importing it."""
        from .rescan import rescan_record_osint

        return rescan_record_osint(self, evidence_id, mode=mode, force=force)

    def manual_crop_ocr(self, evidence_id: str, crop_box: tuple[float, float, float, float] | None = None, *, label: str = "manual_crop") -> Optional[EvidenceRecord]:
        """Run OCR on a selected crop and merge recovered labels/entities into the record."""
        from .rescan import manual_crop_ocr

        return manual_crop_ocr(self, evidence_id, crop_box=crop_box, label=label)


    def _record_snapshot_warning(self, message: str) -> None:
        stamped = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} | {message}"
        self.snapshot_warnings.append(stamped)
        self.logger.warning(stamped)
        try:
            with (self.logs_dir / "snapshot_recovery.log").open("a", encoding="utf-8") as handle:
                handle.write(stamped + "\n")
        except Exception as exc:
            self.logger.debug("Could not append snapshot recovery log: %s", exc)

    def load_case_snapshot(self, case_id: str) -> List[EvidenceRecord]:
        snapshot_path = self.case_root / case_id / "case_snapshot.json"
        backup_path = snapshot_path.with_suffix(".json.bak")
        payload = None
        primary_error: Exception | None = None
        for candidate in (snapshot_path, backup_path):
            if not candidate.exists():
                continue
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
                if candidate == backup_path and primary_error is not None:
                    self._record_snapshot_warning(
                        f"Primary snapshot for {case_id} was unreadable; recovered records from backup {backup_path.name}. Error: {primary_error}"
                    )
                break
            except Exception as exc:
                if candidate == snapshot_path:
                    primary_error = exc
                    self._record_snapshot_warning(
                        f"Primary snapshot for {case_id} is unreadable; attempting backup recovery. Error: {exc}"
                    )
                else:
                    self._record_snapshot_warning(
                        f"Backup snapshot for {case_id} is also unreadable. Error: {exc}"
                    )
        if payload is None:
            if primary_error is not None:
                self._record_snapshot_warning(f"No valid snapshot could be loaded for {case_id}; case opened with empty evidence list.")
            return []
        loaded: List[EvidenceRecord] = []
        valid_fields = {field.name for field in fields(EvidenceRecord)}
        path_fields = {"file_path", "original_file_path", "working_copy_path"}
        for raw in payload.get("records", []):
            prepared = {}
            for key, value in raw.items():
                if key not in valid_fields:
                    continue
                if key in path_fields:
                    prepared[key] = Path(value) if value else Path(".")
                else:
                    prepared[key] = value
            prepared.setdefault("case_id", case_id)
            prepared.setdefault("case_name", payload.get("case_name", self.active_case_name))
            prepared.setdefault("file_path", Path(prepared.get("file_name", "unknown")))
            prepared.setdefault("original_file_path", prepared.get("file_path", Path(".")))
            prepared.setdefault("working_copy_path", prepared.get("file_path", Path(".")))
            if not prepared.get("working_sha256") and prepared.get("sha256"):
                prepared["working_sha256"] = prepared.get("sha256", "")
            if not prepared.get("working_md5") and prepared.get("md5"):
                prepared["working_md5"] = prepared.get("md5", "")
            try:
                record = EvidenceRecord(**prepared)
                self._hydrate_record_from_osint_cache(record, case_id)
                loaded.append(record)
            except Exception as exc:
                self._record_snapshot_warning(f"Skipped invalid evidence record while loading {case_id}: {exc}")
                continue
        return loaded

    def _hydrate_record_from_osint_cache(self, record: EvidenceRecord, case_id: str) -> None:
        """Restore deterministic structured OSINT fields saved outside the main snapshot.

        Cache loading is intentionally conservative: the SHA-256 must match when it is
        available, and non-empty snapshot values always win over cached values. This
        gives analysts stable reload behavior without letting stale cache override a
        manually edited or newer snapshot.
        """
        cached = load_osint_cache(self.case_root / case_id / "osint_cache", record.evidence_id, sha256=record.sha256)
        if not cached:
            return
        fields_to_restore = [
            "osint_entities",
            "osint_hypothesis_cards",
            "osint_corroboration_matrix",
            "osint_analyst_decisions",
            "osint_privacy_review",
            "filename_location_hints",
            "map_evidence_ladder",
            "ctf_clues",
            "geo_candidates",
            "ctf_search_queries",
            "location_solvability_score",
            "location_solvability_label",
            "location_estimate_label",
            "location_estimate_confidence",
            "location_estimate_scope",
            "location_estimate_source_tier",
            "location_estimate_summary",
            "location_estimate_supporting_signals",
            "location_estimate_limitations",
            "location_estimate_next_actions",
            "location_estimate_candidates",
            "ctf_country_region_profile",
            "ctf_landmark_matches",
            "ctf_writeup",
            "ctf_online_mode_status",
            "ctf_image_existence_profile",
            "ctf_online_privacy_review",
            "place_candidate_rankings",
        ]
        restored = []
        for field_name in fields_to_restore:
            current = getattr(record, field_name, None)
            value = cached.get(field_name)
            if value and not current:
                setattr(record, field_name, value)
                restored.append(field_name)
        if restored:
            record.osint_cache_status = "Structured OSINT cache loaded: " + ", ".join(restored)


    def case_snapshot_path(self, case_id: Optional[str] = None) -> Path:
        case_id = case_id or self.active_case_id
        return self.case_root / case_id / "case_snapshot.json"

    def compare_candidates(self, evidence_id: str) -> List[EvidenceRecord]:
        base = self.get_record(evidence_id)
        if base is None:
            return []
        peers = [record for record in self.records if record.evidence_id != evidence_id]
        return sorted(
            peers,
            key=lambda record: (
                record.duplicate_group != base.duplicate_group if base.duplicate_group else True,
                abs(record.suspicion_score - base.suspicion_score),
                record.evidence_id,
            ),
        )


    def create_case_backup(self) -> Path:
        backup_root = self.case_root / "backups"
        backup_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        archive_base = backup_root / f"{self.active_case_id}_{stamp}_backup"
        case_dir = self.case_root / self.active_case_id
        if not case_dir.exists():
            raise FileNotFoundError(f"Active case folder is missing: {case_dir}")
        zip_path = Path(shutil.make_archive(str(archive_base), "zip", root_dir=self.case_root, base_dir=self.active_case_id))
        self.db.log_action(self.active_case_id, None, "BACKUP_CREATE", f"Created backup package {zip_path.name}")
        return zip_path

    def restore_case_backup(self, backup_zip: Path) -> str:
        backup_zip = Path(backup_zip)
        if not backup_zip.exists() or backup_zip.suffix.lower() != ".zip":
            raise FileNotFoundError("Select a valid GeoTrace case backup .zip file.")

        restore_root = self.case_root / "restore_preview"
        if restore_root.exists():
            shutil.rmtree(restore_root, ignore_errors=True)
        restore_root.mkdir(parents=True, exist_ok=True)

        target_case_dir: Path | None = None
        pre_restore_snapshot: Path | None = None
        restore_committed = False
        try:
            with zipfile.ZipFile(backup_zip, "r") as archive:
                safe_extract_zip(archive, restore_root)
            candidates = [path for path in restore_root.iterdir() if path.is_dir() and (path / "case_snapshot.json").exists()]
            if not candidates:
                raise ValueError("Backup does not contain a case_snapshot.json at its top-level case folder.")

            source_case_dir = candidates[0]
            target_case_dir = self.case_root / source_case_dir.name
            if target_case_dir.exists():
                stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                pre_restore_snapshot = target_case_dir.with_name(f"{target_case_dir.name}_pre_restore_{stamp}")
                shutil.move(str(target_case_dir), str(pre_restore_snapshot))

            shutil.copytree(source_case_dir, target_case_dir)
            case_name = target_case_dir.name
            try:
                snapshot_data = json.loads((target_case_dir / "case_snapshot.json").read_text(encoding="utf-8"))
                case_name = str(snapshot_data.get("case_name") or case_name)
            except Exception as exc:
                self.logger.warning("Restored backup snapshot metadata could not be read: %s", exc)

            try:
                self.db.create_case(target_case_dir.name, case_name, set_active=True)
            except ValueError:
                self.db.set_active_case(target_case_dir.name)
            self.active_case = self.db.get_active_case() or self.active_case
            self.records = self.load_case_snapshot(target_case_dir.name)
            self.db.log_action(target_case_dir.name, None, "BACKUP_RESTORE", f"Restored backup {backup_zip.name} into {target_case_dir.name}")
            restore_committed = True
            return target_case_dir.name
        except Exception:
            self.logger.exception("Backup restore failed; attempting transactional rollback")
            if not restore_committed:
                if target_case_dir is not None and target_case_dir.exists():
                    shutil.rmtree(target_case_dir, ignore_errors=True)
                if pre_restore_snapshot is not None and pre_restore_snapshot.exists() and target_case_dir is not None:
                    shutil.move(str(pre_restore_snapshot), str(target_case_dir))
            raise
        finally:
            shutil.rmtree(restore_root, ignore_errors=True)
            if restore_committed and pre_restore_snapshot is not None and pre_restore_snapshot.exists():
                self.logger.info("Previous case folder preserved after restore: %s", pre_restore_snapshot)

    def validation_summary(self) -> str:
        if not self.records:
            return "Validation pending — no evidence analyzed yet."
        gps_ok = sum(1 for record in self.records if record.has_gps and record.gps_confidence >= 80)
        parser_ok = sum(1 for record in self.records if record.parser_status == "Valid")
        hidden = sum(1 for record in self.records if record.hidden_code_indicators or record.hidden_suspicious_embeds)
        integrity_ok = sum(1 for record in self.records if record.integrity_status in {"Verified", "Partial"})
        chain_ok, chain_note = self.db.verify_log_chain(self.active_case_id)
        chain_state = "verified" if chain_ok else "needs review"
        ocr_entities = sum(1 for record in self.records if (record.ocr_location_entities or record.ocr_time_entities or record.ocr_url_entities or record.ocr_username_entities or record.ocr_map_labels))
        derived_geo = sum(1 for record in self.records if record.derived_geo_display != "Unavailable" or record.possible_geo_clues)
        validation = build_validation_metrics(self.records)
        validation_line = validation.get("summary", "No linked validation dataset was found.")
        ai_review = sum(1 for record in self.records if record.ai_flags)
        ai_planned = sum(1 for record in self.records if record.ai_action_plan)
        top_ai = sorted([record for record in self.records if record.ai_priority_rank], key=lambda item: item.ai_priority_rank)[:3]
        top_ai_line = ", ".join(f"#{record.ai_priority_rank} {record.evidence_id}" for record in top_ai) or "none"
        return (
            f"GPS strong anchors {gps_ok}/{len(self.records)} • Parser clean {parser_ok}/{len(self.records)} • "
            f"OCR/entity-rich items {ocr_entities}/{len(self.records)} • Derived geo leads {derived_geo}/{len(self.records)} • "
            f"AI flags {ai_review}/{len(self.records)} • AI plans {ai_planned}/{len(self.records)} • Top AI priorities {top_ai_line} • "
            f"Hidden/code hits {hidden} • Integrity checked {integrity_ok}/{len(self.records)} • Custody chain {chain_state} • "
            f"Validation: {validation_line}"
        )

    def export_chain_of_custody(self) -> str:
        logs = self.db.fetch_logs(self.active_case_id)
        if not logs:
            return "No chain-of-custody activity logged yet."
        chain_ok, chain_note = self.db.verify_log_chain(self.active_case_id)
        lines = [f"Chain verification: {'OK' if chain_ok else 'REVIEW'} — {chain_note}"]
        for row in logs:
            evidence_id = row["evidence_id"] or "CASE"
            lines.append(
                f"[{row['action_time']}] {evidence_id} | {row['action']} | {row['details']} | prev={str(row['prev_hash'] or 'legacy')[:10]} | hash={str(row['event_hash'] or 'legacy')[:10]}"
            )
        return "\n".join(lines)

    def _timeline_span(self) -> str:
        timestamps = [parse_timestamp(record.timestamp) for record in self.records if record.timestamp != "Unknown"]
        timestamps = [item for item in timestamps if item is not None]
        if len(timestamps) < 2:
            return "Single point / insufficient time data"
        start = min(timestamps)
        end = max(timestamps)
        delta = end - start
        hours = round(delta.total_seconds() / 3600, 1)
        return f"{start.strftime('%Y-%m-%d %H:%M')} → {end.strftime('%Y-%m-%d %H:%M')} ({hours}h span)"

    def _write_case_snapshot(self) -> None:
        case_dir = self.case_root / self.active_case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = case_dir / "case_snapshot.json"
        payload = {
            "case_id": self.active_case_id,
            "case_name": self.active_case_name,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "records": [],
        }
        for record in self.records:
            row = {}
            for field in fields(EvidenceRecord):
                value = getattr(record, field.name)
                if isinstance(value, Path):
                    row[field.name] = str(value)
                else:
                    row[field.name] = value
            payload["records"].append(row)
        backup_path = snapshot_path.with_suffix(".json.bak")
        tmp_path = snapshot_path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if snapshot_path.exists():
            try:
                shutil.copy2(snapshot_path, backup_path)
            except Exception as exc:
                self.logger.warning("Could not write case snapshot backup %s: %s", backup_path, exc)
        os.replace(tmp_path, snapshot_path)
