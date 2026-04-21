from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List

from .anomalies import assign_duplicate_groups, detect_anomalies, dominant_device, parse_timestamp
from .case_db import CaseDatabase
from .exif_service import (
    build_metadata_summary,
    build_osint_leads,
    classify_source,
    compute_perceptual_hash,
    extract_basic_image_info,
    extract_device_model,
    extract_exif,
    extract_file_times,
    extract_gps,
    extract_software,
    extract_timestamp,
    is_supported_image,
)
from .hashing import compute_hashes
from .models import CaseStats, EvidenceRecord


class CaseManager:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.case_root = project_root / "case_data"
        self.case_root.mkdir(parents=True, exist_ok=True)
        self.db = CaseDatabase(self.case_root / "geotrace_case.db")
        self.records: List[EvidenceRecord] = []
        self.case_id = "GT-2026-001"

    def load_images(self, paths: List[Path]) -> List[EvidenceRecord]:
        self.db.reset_case()
        collected: List[EvidenceRecord] = []
        for file_path in paths:
            if file_path.is_dir():
                for child in sorted(file_path.rglob("*")):
                    if child.is_file() and is_supported_image(child):
                        collected.append(self._build_record(child, len(collected) + 1))
            elif file_path.is_file() and is_supported_image(file_path):
                collected.append(self._build_record(file_path, len(collected) + 1))

        assign_duplicate_groups(collected)
        baseline_device = dominant_device(collected)
        for record in collected:
            score, confidence, level, reasons, authenticity, metadata, technical, breakdown = detect_anomalies(record, baseline_device, record.file_path)
            record.suspicion_score = score
            record.confidence_score = confidence
            record.risk_level = level
            record.anomaly_reasons = reasons
            record.authenticity_score = authenticity
            record.metadata_score = metadata
            record.technical_score = technical
            record.score_breakdown = breakdown
            record.analyst_verdict = self._derive_analyst_verdict(record)
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
                    record.format_trust,
                    record.declared_format,
                    record.detected_format,
                    record.parser_status,
                )
            self.db.upsert_evidence(record)
            self.db.log_action(record.evidence_id, "ANALYZE", f"Risk={level}, Score={score}, Confidence={confidence}")

        self.records = collected
        self._write_case_snapshot()
        return self.records

    def _build_record(self, file_path: Path, index: int) -> EvidenceRecord:
        hashes = compute_hashes(file_path)
        exif = extract_exif(file_path)
        basic = extract_basic_image_info(file_path)
        timestamp, timestamp_source = extract_timestamp(exif, file_path)
        device_model, camera_make = extract_device_model(exif)
        software = extract_software(exif)
        lat, lon, altitude, gps_display = extract_gps(exif)
        evidence_id = f"IMG-{index:03d}"
        imported_at = datetime.utcnow().isoformat(timespec="seconds")
        created_time, modified_time = extract_file_times(file_path)
        metadata = build_metadata_summary(exif)
        source_type = classify_source(
            file_path,
            {k: v for k, v in exif.items() if k != "__raw_tags__"},
            software,
            int(basic["width"]),
            int(basic["height"]),
            str(basic["parser_status"]),
            str(basic["format_trust"]),
        )
        record = EvidenceRecord(
            evidence_id=evidence_id,
            file_path=file_path,
            file_name=file_path.name,
            sha256=hashes["sha256"],
            md5=hashes["md5"],
            perceptual_hash=compute_perceptual_hash(file_path),
            file_size=file_path.stat().st_size,
            imported_at=imported_at,
            exif={k: v for k, v in exif.items() if k != "__raw_tags__"},
            timestamp=timestamp,
            timestamp_source=timestamp_source,
            created_time=created_time,
            modified_time=modified_time,
            device_model=device_model,
            camera_make=camera_make,
            software=software,
            source_type=source_type,
            format_name=str(basic["format_name"]),
            declared_format=str(basic["declared_format"]),
            detected_format=str(basic["detected_format"]),
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
            parse_error=str(basic["parse_error"]),
            frame_count=int(basic["frame_count"]),
            is_animated=bool(basic["is_animated"]),
            animation_duration_ms=int(basic["animation_duration_ms"]),
        )
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
            record.format_trust,
            record.declared_format,
            record.detected_format,
            record.parser_status,
        )
        self.db.log_action(record.evidence_id, "IMPORT", f"Imported {record.file_name}")
        return record

    def _derive_analyst_verdict(self, record: EvidenceRecord) -> str:
        verdict_bits: list[str] = []
        if record.source_type in {"Screenshot", "Messaging Export", "Screenshot / Export"}:
            verdict_bits.append("The file profile is consistent with a screenshot or exported chat artifact rather than a camera-original photo.")
        elif record.source_type == "Camera Photo":
            verdict_bits.append("The file retains characteristics of a camera-origin image with richer acquisition metadata.")
        elif record.source_type == "Edited / Exported":
            verdict_bits.append("The metadata profile suggests the media likely passed through an editing or export workflow.")
        elif record.source_type == "Malformed / Unsupported Asset":
            verdict_bits.append("The file could not be cleanly decoded, so it should be treated as malformed or unsupported until a second parser confirms its structure.")
        elif record.source_type == "Signature Mismatch Asset":
            verdict_bits.append(f"The file extension suggests {record.declared_format}, but the detected signature points to {record.detected_format}. Treat it as a mismatched asset until workflow context explains the discrepancy.")
        else:
            verdict_bits.append("The source profile is mixed, so the file should be treated as a derivative image until corroborated.")

        if record.timestamp_source == "Embedded EXIF":
            verdict_bits.append("Timestamp confidence is stronger because the time came from embedded EXIF tags.")
        elif record.timestamp_source == "Filename Pattern":
            verdict_bits.append("Timestamp was recovered from filename structure, so it is useful for triage but should be corroborated externally.")
        elif record.timestamp_source.startswith("Filesystem"):
            verdict_bits.append("Time values rely on filesystem metadata, which can drift after copying or export operations.")
        else:
            verdict_bits.append("No reliable native timestamp was recovered.")

        if record.has_gps:
            verdict_bits.append("Location intelligence is available and should be correlated with maps, venues, and surrounding evidence.")
        else:
            verdict_bits.append("No GPS coordinates were present, so timeline and source correlation become the primary investigative anchors.")

        if record.duplicate_group:
            verdict_bits.append(f"Visual fingerprinting links this file to {record.duplicate_group}, which may indicate reposting, versioning, or duplicate capture.")
        if record.parser_status != "Valid":
            verdict_bits.append("Parser health is degraded, which means preview, dimensions, and embedded structure should be corroborated before courtroom use.")
        elif record.format_trust == "Mismatch":
            verdict_bits.append(f"Format trust is degraded because the declared extension ({record.declared_format}) does not match the detected signature ({record.detected_format}).")
        elif record.format_trust != "Verified":
            verdict_bits.append("Format trust is not fully verified because extension and header confidence do not fully align.")
        elif record.is_animated:
            verdict_bits.append("The media is animated, so frame-level review is important because the visible first frame may not represent the full sequence.")

        if record.risk_level == "High":
            verdict_bits.append("Priority review is recommended because metadata anomalies materially affect source confidence.")
        elif record.risk_level == "Medium":
            verdict_bits.append("Moderate review is recommended to verify whether the observed gaps are benign or workflow-driven.")
        else:
            verdict_bits.append("Current metadata signals do not point to aggressive manipulation, but provenance still requires case context.")
        return " ".join(verdict_bits)

    def build_stats(self) -> CaseStats:
        stats = CaseStats()
        stats.total_images = len(self.records)
        stats.gps_enabled = sum(1 for record in self.records if record.has_gps)
        stats.anomaly_count = sum(1 for record in self.records if record.risk_level != "Low")
        stats.device_count = len({record.device_model for record in self.records if record.device_model not in {"", "Unknown"}})
        stats.timeline_span = self._timeline_span()
        verified = sum(1 for record in self.records if record.integrity_status == "Verified")
        stats.integrity_summary = f"{verified}/{len(self.records)} Verified" if self.records else "0/0 Verified"
        stats.screenshots_count = sum(1 for record in self.records if "Screenshot" in record.source_type or "Messaging" in record.source_type)
        stats.duplicates_count = len({record.duplicate_group for record in self.records if record.duplicate_group})
        stats.avg_score = round(sum(r.suspicion_score for r in self.records) / len(self.records)) if self.records else 0
        return stats

    def update_note(self, evidence_id: str, note: str) -> None:
        for record in self.records:
            if record.evidence_id == evidence_id:
                record.note = note
                self.db.upsert_evidence(record)
                self.db.log_action(evidence_id, "NOTE", note or "Note cleared")
                break
        self._write_case_snapshot()

    def export_chain_of_custody(self) -> str:
        logs = self.db.fetch_logs()
        if not logs:
            return "No chain-of-custody activity logged yet."
        return "\n".join(f"[{row[0]}] {row[1]} | {row[2]} | {row[3]}" for row in logs)

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
        snapshot_path = self.case_root / "case_snapshot.json"
        payload = []
        for record in self.records:
            payload.append(
                {
                    "evidence_id": record.evidence_id,
                    "file_name": record.file_name,
                    "timestamp": record.timestamp,
                    "timestamp_source": record.timestamp_source,
                    "device_model": record.device_model,
                    "source_type": record.source_type,
                    "gps_display": record.gps_display,
                    "suspicion_score": record.suspicion_score,
                    "confidence_score": record.confidence_score,
                    "risk_level": record.risk_level,
                    "anomaly_reasons": record.anomaly_reasons,
                    "osint_leads": record.osint_leads,
                    "duplicate_group": record.duplicate_group,
                    "analyst_verdict": record.analyst_verdict,
                    "parser_status": record.parser_status,
                    "preview_status": record.preview_status,
                    "structure_status": record.structure_status,
                    "format_trust": record.format_trust,
                    "format_signature": record.format_signature,
                    "declared_format": record.declared_format,
                    "detected_format": record.detected_format,
                    "authenticity_score": record.authenticity_score,
                    "metadata_score": record.metadata_score,
                    "technical_score": record.technical_score,
                    "score_breakdown": record.score_breakdown,
                    "note": record.note,
                }
            )
        snapshot_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
