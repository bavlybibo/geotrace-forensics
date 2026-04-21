from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from dataclasses import fields
from pathlib import Path
from typing import Callable, List, Optional

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
        self.active_case = self.db.get_active_case() or CaseInfo(case_id, case_name, datetime.now(timezone.utc).isoformat(timespec="seconds"), datetime.now(timezone.utc).isoformat(timespec="seconds"), 0)
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
        baseline_device = dominant_device(combined)

        for index, record in enumerate(combined, start=1):
            if cancel_callback and cancel_callback():
                raise AnalysisCancelled()
            if progress_callback:
                progress_callback(62 + int(index / max(total, 1) * 28), f"Scoring {record.evidence_id} ({index}/{total})")
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
                )
            self.db.upsert_evidence(record)
            self.db.log_action(record.case_id, record.evidence_id, "ANALYZE", f"Risk={level}, Score={score}, Confidence={confidence}")

        self.records = combined
        self._write_case_snapshot()
        self.db.log_action(self.active_case_id, None, "BATCH_COMPLETE", f"Analysis complete for {len(self.records)} item(s)")
        if progress_callback:
            progress_callback(100, f"Analysis complete — {len(self.records)} evidence item(s)")
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
        basic = extract_basic_image_info(file_path)
        timestamp, timestamp_source = extract_timestamp(exif, file_path)
        device_model, camera_make = extract_device_model(exif)
        software = extract_software(exif)
        lat, lon, altitude, gps_display = extract_gps(exif)
        evidence_id = f"IMG-{index:03d}"
        imported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        created_time, modified_time = extract_file_times(file_path)
        metadata = build_metadata_summary(exif)
        normalized_exif = {k: v for k, v in exif.items() if k != "__raw_tags__"}
        source_type = classify_source(
            file_path,
            normalized_exif,
            software,
            int(basic["width"]),
            int(basic["height"]),
            str(basic["parser_status"]),
        )
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
        self.db.log_action(record.case_id, record.evidence_id, "IMPORT", f"Imported {record.file_name}")
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
            verdict_bits.append("Decoder health is degraded, so the visible preview and structural assumptions should be corroborated with a second parser before courtroom use.")
        elif record.signature_status == "Mismatch":
            verdict_bits.append("Header signature and file extension disagree, which is a strong structure-integrity concern even if a parser can still render the file.")
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
                    prepared[key] = Path(value) if value else Path('.')
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

    def export_chain_of_custody(self) -> str:
        logs = self.db.fetch_logs(self.active_case_id)
        if not logs:
            return "No chain-of-custody activity logged yet."
        lines = []
        for row in logs:
            evidence_id = row["evidence_id"] or "CASE"
            lines.append(f"[{row['action_time']}] {evidence_id} | {row['action']} | {row['details']}")
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
