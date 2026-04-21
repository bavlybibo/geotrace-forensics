from __future__ import annotations

import json
import re
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

from .anomalies import assign_duplicate_groups, assign_scene_groups, detect_anomalies, dominant_device, parse_timestamp
from .case_db import CaseDatabase
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
from .visual_clues import extract_visible_text_clues, parse_derived_geo, profile_source_details
from .hashing import compute_hashes
from .models import CaseInfo, CaseStats, EvidenceRecord


ProgressCallback = Callable[[int, str], None]
CancelCallback = Callable[[], bool]


class AnalysisCancelled(Exception):
    pass


class CaseManager:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.case_root = project_root / "case_data"
        self.case_root.mkdir(parents=True, exist_ok=True)
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
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        case_name = (case_name or f"Case {timestamp}").strip() or f"Case {timestamp}"
        slug = re.sub(r"[^A-Z0-9]+", "-", case_name.upper()).strip("-")[:26] or "CASE"
        case_id = f"GT-{datetime.now(timezone.utc).strftime('%Y')}-{slug}-{timestamp[-4:]}"
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
                progress_callback(max(5, int((index - 1) / max(total, 1) * 55)), f"Importing {file_path.name} ({index}/{total})")
            collected.append(self._build_record(file_path, index))

        if progress_callback:
            progress_callback(62, "Correlating duplicates and baseline devices…")
        combined = existing + collected
        assign_duplicate_groups(combined)
        assign_scene_groups(combined)
        baseline_device = dominant_device(combined)

        for index, record in enumerate(combined, start=1):
            if cancel_callback and cancel_callback():
                raise AnalysisCancelled()
            if progress_callback:
                progress_callback(62 + int(index / max(total, 1) * 28), f"Scoring {record.evidence_id} ({index}/{total})")
            score, confidence, level, reasons, authenticity, metadata, technical, breakdown, contributors = detect_anomalies(
                record,
                baseline_device,
                record.file_path,
            )
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
                f"Risk={level}, Score={score}, Confidence={confidence}, Integrity={record.integrity_status}",
            )
            record.custody_event_summary = self.db.summarize_evidence_events(record.case_id, record.evidence_id)

        self.records = combined
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

    def _build_record(self, file_path: Path, index: int) -> EvidenceRecord:
        hashes = compute_hashes(file_path)
        exif = extract_exif(file_path)
        exif_warning = str(exif.get("__warning__", "")).strip()
        basic = extract_basic_image_info(file_path)
        device_model, camera_make = extract_device_model(exif)
        software = extract_software(exif)
        lat, lon, altitude, gps_display = extract_gps(exif)
        evidence_id = f"IMG-{index:03d}"
        imported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        created_time, modified_time, created_time_note = extract_file_times(file_path)
        metadata = build_metadata_summary(exif)
        normalized_exif = {k: v for k, v in exif.items() if k not in {"__raw_tags__", "__warning__"}}
        initial_source_type = classify_source(
            file_path,
            normalized_exif,
            software,
            int(basic["width"]),
            int(basic["height"]),
            str(basic["parser_status"]),
        )
        embedded_scan = extract_embedded_text_hints(file_path, str(basic["format_name"]))
        visible = extract_visible_text_clues(
            file_path,
            int(basic["width"]),
            int(basic["height"]),
            source_hint=initial_source_type,
            force=(initial_source_type in {"Screenshot", "Screenshot / Export", "Messaging Export"} or (not normalized_exif and file_path.suffix.lower() == ".png")),
        )
        derived_geo = parse_derived_geo(
            list(visible.get("lines", [])) + list(embedded_scan.get("context_strings", [])),
            list(visible.get("visible_urls", [])) + list(embedded_scan.get("urls", [])),
            source_type=initial_source_type,
        )
        source_type, source_profile_confidence = profile_source_details(
            file_path,
            source_type=initial_source_type,
            width=int(basic["width"]),
            height=int(basic["height"]),
            has_exif=bool(normalized_exif),
            software=software,
            visible_urls=list(visible.get("visible_urls", [])),
            app_detected=str(visible.get("app_detected", "Unknown")),
        )
        time_assessment = build_time_assessment(normalized_exif, file_path, list(visible.get("visible_time_strings", [])))
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
            file_path=file_path,
            file_name=file_path.name,
            sha256=hashes["sha256"],
            md5=hashes["md5"],
            perceptual_hash=compute_perceptual_hash(file_path),
            file_size=file_path.stat().st_size,
            imported_at=imported_at,
            exif=normalized_exif,
            raw_exif=normalized_exif,
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
            source_profile_confidence=source_profile_confidence,
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
            visible_urls=list(visible.get("visible_urls", [])),
            visible_time_strings=list(visible.get("visible_time_strings", [])),
            visible_location_strings=list(visible.get("visible_location_strings", [])),
            visible_text_excerpt=str(visible.get("excerpt", "")),
            hidden_code_indicators=list(embedded_scan.get("code_indicators", [])),
            hidden_finding_types=list(embedded_scan.get("finding_types", [])),
            hidden_code_summary=str(embedded_scan.get("summary", "No embedded code-like content detected.")),
            hidden_content_overview=str(embedded_scan.get("overview", "No embedded text payloads or code-like markers detected.")),
            hidden_context_summary=str(embedded_scan.get("context_summary", "No visible or embedded text context was retained.")),
            hidden_suspicious_embeds=list(embedded_scan.get("suspicious_embeds", [])),
            hidden_payload_markers=list(embedded_scan.get("payload_markers", [])),
            stego_suspicion=str(embedded_scan.get("stego_suspicion", "No strong steganography or appended-payload indicator was detected.")),
            urls_found=list(embedded_scan.get("urls", [])),
            time_candidates=list(time_assessment.get("candidates", [])),
            time_conflicts=list(time_assessment.get("conflicts", [])),
        )
        record.integrity_status, record.integrity_note = self._derive_integrity_status(record)
        record.osint_leads = build_osint_leads(
            file_path,
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
        record.osint_leads = record.osint_leads[:8]
        self.db.log_action(record.case_id, record.evidence_id, "IMPORT", f"Imported {record.file_name}")
        return record

    def _derive_integrity_status(self, record: EvidenceRecord) -> tuple[str, str]:
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
        verdict_bits: list[str] = []
        if record.source_type in {"Screenshot", "Messaging Export", "Screenshot / Export", "Map Screenshot", "Browser Screenshot"}:
            verdict_bits.append("The file profile is consistent with a screenshot, browser capture, or exported chat artifact rather than a camera-original photo.")
        elif record.source_type == "Camera Photo":
            verdict_bits.append("The file retains characteristics of a camera-origin image with richer acquisition metadata.")
        elif record.source_type == "Edited / Exported":
            verdict_bits.append("The metadata profile suggests the media likely passed through an editing or export workflow.")
        elif record.source_type == "Malformed / Unsupported Asset":
            verdict_bits.append("The file could not be cleanly decoded, so it should be treated as malformed or unsupported until a second parser confirms its structure.")
        else:
            verdict_bits.append("The source profile is mixed, so the file should be treated as a derivative image until corroborated.")

        if record.exif_warning:
            verdict_bits.append(record.exif_warning)

        if record.timestamp_source.startswith("Native EXIF") or record.timestamp_source == "Embedded EXIF":
            verdict_bits.append("Timestamp confidence is stronger because the selected anchor came from embedded EXIF tags.")
        elif record.timestamp_source == "Filename Pattern":
            verdict_bits.append("Timestamp was recovered from filename structure, so it is useful for triage but should be corroborated externally.")
        elif record.timestamp_source == "Visible On-Screen Time":
            verdict_bits.append("A visible on-screen time clue contributed to the time model, but it remains weaker than native EXIF and still needs corroboration.")
        elif record.timestamp_source.startswith("Filesystem"):
            verdict_bits.append("Time values rely on filesystem metadata, which can drift after copying or export operations.")
        else:
            verdict_bits.append("No reliable native timestamp was recovered.")
        if record.time_conflicts:
            verdict_bits.append("Multiple time candidates disagree materially, so chronology claims should remain conservative until cross-checked externally.")

        if record.has_gps:
            verdict_bits.append("Native GPS intelligence is available and should be correlated with maps, venues, and surrounding evidence.")
        elif record.derived_geo_display != "Unavailable":
            verdict_bits.append("No native GPS was present, but screenshot-derived location clues were parsed from visible content and should be treated as medium-confidence contextual leads.")
        else:
            verdict_bits.append("No native GPS coordinates were present, so timeline and source correlation become the primary investigative anchors.")

        if record.duplicate_group:
            verdict_bits.append(f"Visual fingerprinting links this file to {record.duplicate_group}, which may indicate reposting, versioning, or duplicate capture.")
        if record.parser_status != "Valid":
            verdict_bits.append("Decoder health is degraded, so the visible preview and structural assumptions should be corroborated with a second parser before courtroom use.")
        elif record.signature_status == "Mismatch":
            verdict_bits.append("Header signature and file extension disagree, which is a strong structure-integrity concern even if a parser can still render the file.")
        elif record.is_animated:
            verdict_bits.append("The media is animated, so frame-level review is important because the visible first frame may not represent the full sequence.")

        if record.hidden_code_indicators:
            verdict_bits.append("Tiered hidden-content scanning recovered code-like, credential-like, or script-capable markers inside the container, so the file should be treated as content-bearing rather than image-only until confirmed.")
        elif record.hidden_suspicious_embeds:
            verdict_bits.append("Structural hidden-content scanning found appended-data or encoded-content warnings even though no direct code payload was confirmed.")
        elif record.extracted_strings:
            verdict_bits.append("Readable embedded strings were retained for analyst context, but they do not by themselves prove hidden code or exploitability.")
        if record.visible_text_excerpt:
            verdict_bits.append("On-screen OCR recovered visible text clues that can support app, map, browser, or screenshot-context reasoning.")

        verdict_bits.append(f"Current structural integrity state: {record.integrity_status}. {record.integrity_note}")

        if record.risk_level == "High":
            verdict_bits.append("Priority review is recommended because metadata anomalies materially affect source confidence.")
        elif record.risk_level == "Medium":
            verdict_bits.append("Moderate review is recommended to verify whether the observed gaps are benign or workflow-driven.")
        else:
            verdict_bits.append("Current metadata signals do not point to aggressive manipulation, but provenance still requires case context.")
        return " ".join(verdict_bits)

    def _derive_courtroom_notes(self, record: EvidenceRecord) -> str:
        strengths: list[str] = []
        limitations: list[str] = []
        if record.timestamp_confidence >= 80:
            strengths.append("Strong native or embedded time anchor available.")
        elif record.timestamp_confidence > 0:
            limitations.append(f"Selected time anchor is {record.timestamp_source.lower()} and should be corroborated.")
        else:
            limitations.append("No trustworthy native time anchor was recovered.")
        if record.gps_confidence >= 80:
            strengths.append("Native GPS coordinates recovered.")
        elif record.has_gps:
            limitations.append("GPS exists but needs manual validation against the workflow context.")
        elif record.derived_geo_display != "Unavailable":
            limitations.append("Location clue is screenshot-derived rather than native EXIF GPS; use it as contextual support only unless corroborated.")
        else:
            limitations.append("No native GPS available; rely on timeline and external corroboration.")
        if record.time_conflicts:
            limitations.append("Time-candidate conflicts exist across filename, visible, or filesystem anchors.")
        if record.parser_status != "Valid" or record.signature_status == "Mismatch":
            limitations.append("Structure / parser issues reduce courtroom confidence until a second parser confirms the file.")
        if record.hidden_code_indicators:
            limitations.append("Container includes embedded code-like strings; context must be explained before courtroom use.")
        elif record.hidden_suspicious_embeds:
            limitations.append("Hidden-content scanning found structural warnings that still need analyst explanation.")
        if record.exif_warning:
            limitations.append(record.exif_warning)
        if record.created_time == "Unavailable":
            limitations.append("Filesystem birth time is unavailable on this platform; ctime was not treated as creation time.")
        strengths.append(f"Integrity status: {record.integrity_status}.")
        if record.visible_text_excerpt:
            strengths.append("On-screen text clues were preserved for later corroboration.")
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
        stats.hidden_content_count = sum(1 for record in self.records if record.hidden_code_indicators)
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

    def load_case_snapshot(self, case_id: str) -> List[EvidenceRecord]:
        snapshot_path = self.case_root / case_id / "case_snapshot.json"
        if not snapshot_path.exists():
            return []
        try:
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        loaded: List[EvidenceRecord] = []
        valid_fields = {field.name for field in fields(EvidenceRecord)}
        for raw in payload.get("records", []):
            prepared = {}
            for key, value in raw.items():
                if key not in valid_fields:
                    continue
                if key == "file_path":
                    prepared[key] = Path(value) if value else Path(".")
                else:
                    prepared[key] = value
            prepared.setdefault("case_id", case_id)
            prepared.setdefault("case_name", payload.get("case_name", self.active_case_name))
            prepared.setdefault("file_path", Path(prepared.get("file_name", "unknown")))
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
        hidden = sum(1 for record in self.records if record.hidden_code_indicators)
        integrity_ok = sum(1 for record in self.records if record.integrity_status in {"Verified", "Partial"})
        chain_ok, chain_note = self.db.verify_log_chain(self.active_case_id)
        chain_state = "verified" if chain_ok else "needs review"
        return (
            f"GPS strong anchors {gps_ok}/{len(self.records)} • Parser clean {parser_ok}/{len(self.records)} • "
            f"Hidden/code hits {hidden} • Integrity checked {integrity_ok}/{len(self.records)} • Custody chain {chain_state}"
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
        snapshot_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
