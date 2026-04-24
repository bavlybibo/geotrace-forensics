from __future__ import annotations

import json
import os
import re
import shutil
import logging
from dataclasses import fields
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
from typing import Callable, List, Optional

from .anomalies import assign_duplicate_groups, assign_scene_groups, detect_anomalies, dominant_device, parse_timestamp
from .case_db import CaseDatabase
from .ai_engine import run_ai_batch_assessment
from .exif_service import (
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
from .visual_clues import extract_visible_text_clues, infer_source_profile, parse_derived_geo, profile_source_details
from .hashing import compute_hashes
from .models import CaseInfo, CaseStats, EvidenceRecord
from .explainability import apply_explainability
from .validation_service import build_validation_metrics


ProgressCallback = Callable[[int, str], None]
CancelCallback = Callable[[], bool]


class AnalysisCancelled(Exception):
    pass


class CaseManager:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.case_root = project_root / "case_data"
        self.case_root.mkdir(parents=True, exist_ok=True)
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
            self.records = []
            self._write_case_snapshot()
            return []

        existing = list(self.records)
        collected: List[EvidenceRecord] = []
        self.db.log_action(self.active_case_id, None, "IMPORT_BATCH", f"Queued {total} evidence item(s)")
        start_index = len(existing) + 1
        for index, file_path in enumerate(files, start=start_index):
            if cancel_callback and cancel_callback():
                raise AnalysisCancelled()
            if progress_callback:
                batch_pos = index - start_index + 1
                progress_callback(max(5, int(batch_pos / max(total, 1) * 55)), f"Importing {file_path.name} ({batch_pos}/{total})")
            collected.append(self._build_record(file_path, index))

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
        carved_files = self._carve_hidden_payloads(evidence_id, list(embedded_scan.get("recoverable_segments", [])))
        visible = extract_visible_text_clues(
            staged_path,
            int(basic["width"]),
            int(basic["height"]),
            source_hint=initial_source_type,
            force=(initial_source_type in {"Screenshot", "Screenshot / Export", "Messaging Export"} or (not normalized_exif and file_path.suffix.lower() == ".png")),
            cache_dir=self.case_root / self.active_case_id / "ocr_cache",
        )
        derived_geo = parse_derived_geo(
            list(visible.get("lines", [])) + list(embedded_scan.get("context_strings", [])),
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
            app_detected=str(visible.get("app_detected", "Unknown")),
            visible_lines=list(visible.get("lines", [])),
            map_labels=list(visible.get("ocr_map_labels", [])),
        )
        source_type = str(source_profile.get("type", initial_source_type))
        source_subtype = str(source_profile.get("subtype", source_type))
        source_profile_confidence = int(source_profile.get("confidence", 0))
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
            perceptual_hash=compute_perceptual_hash(file_path),
            file_size=file_path.stat().st_size,
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
            app_detected=str(visible.get("app_detected", "Unknown")),
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
            ocr_confidence=int(visible.get("ocr_confidence", 0)),
            ocr_analyst_relevance=str(visible.get("ocr_analyst_relevance", "OCR not attempted.")),
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
            urls_found=list(embedded_scan.get("urls", [])),
            time_candidates=list(time_assessment.get("candidates", [])),
            time_conflicts=list(time_assessment.get("conflicts", [])),
        )
        record.integrity_status, record.integrity_note = self._derive_integrity_status(record)
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
        if record.visible_urls:
            record.osint_leads.append(f"Visible URL clue(s): {', '.join(record.visible_urls[:2])}.")
        if record.visible_text_excerpt:
            record.osint_leads.append("On-screen text was recovered through OCR. Preserve the screenshot origin and any matching browser/application logs.")
        if record.possible_geo_clues:
            record.osint_leads.append("Possible geo leads from OCR/map labels: " + ", ".join(record.possible_geo_clues[:3]) + ".")
        if record.source_profile_reasons:
            record.osint_leads.append("Source-profile reasons: " + "; ".join(record.source_profile_reasons[:2]) + ".")
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
        if record.ai_flags:
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

    def _record_snapshot_warning(self, message: str) -> None:
        stamped = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} | {message}"
        self.snapshot_warnings.append(stamped)
        self.logger.warning(stamped)
        try:
            with (self.logs_dir / "snapshot_recovery.log").open("a", encoding="utf-8") as handle:
                handle.write(stamped + "\n")
        except Exception:
            pass

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
                loaded.append(EvidenceRecord(**prepared))
            except Exception:
                continue
        return loaded

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

    def validation_summary(self) -> str:
        if not self.records:
            return "Validation pending — no evidence analyzed yet."
        gps_ok = sum(1 for record in self.records if record.has_gps and record.gps_confidence >= 80)
        parser_ok = sum(1 for record in self.records if record.parser_status == "Valid")
        hidden = sum(1 for record in self.records if record.hidden_code_indicators or record.hidden_suspicious_embeds)
        integrity_ok = sum(1 for record in self.records if record.integrity_status in {"Verified", "Partial"})
        chain_ok, chain_note = self.db.verify_log_chain(self.active_case_id)
        chain_state = "verified" if chain_ok else "needs review"
        ocr_entities = sum(1 for record in self.records if (record.ocr_location_entities or record.ocr_time_entities or record.ocr_url_entities or record.ocr_username_entities))
        derived_geo = sum(1 for record in self.records if record.derived_geo_display != "Unavailable" or record.possible_geo_clues)
        validation = build_validation_metrics(self.records)
        validation_line = validation.get("summary", "No linked validation dataset was found.")
        ai_review = sum(1 for record in self.records if record.ai_flags)
        return (
            f"GPS strong anchors {gps_ok}/{len(self.records)} • Parser clean {parser_ok}/{len(self.records)} • "
            f"OCR/entity-rich items {ocr_entities}/{len(self.records)} • Derived geo leads {derived_geo}/{len(self.records)} • "
            f"AI-reviewed flags {ai_review}/{len(self.records)} • Hidden/code hits {hidden} • Integrity checked {integrity_ok}/{len(self.records)} • Custody chain {chain_state} • "
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
            except Exception:
                pass
        os.replace(tmp_path, snapshot_path)
