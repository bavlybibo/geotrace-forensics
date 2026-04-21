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

    def load_images(self, paths: List[Path]) -> List[EvidenceRecord]:
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
            score, confidence, level, reasons = detect_anomalies(record, baseline_device, record.file_path)
            record.suspicion_score = score
            record.confidence_score = confidence
            record.risk_level = level
            record.anomaly_reasons = reasons
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
        source_type = classify_source(file_path, {k: v for k, v in exif.items() if k != "__raw_tags__"}, software, int(basic["width"]), int(basic["height"]))
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
        )
        self.db.log_action(record.evidence_id, "IMPORT", f"Imported {record.file_name}")
        return record

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
                    "note": record.note,
                }
            )
        snapshot_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
