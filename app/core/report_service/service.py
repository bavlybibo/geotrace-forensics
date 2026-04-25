from __future__ import annotations

import csv
import hashlib
import html
import json
import logging
import re
import shutil
import matplotlib
matplotlib.use("Agg")
import matplotlib.artist  # noqa: F401 - preload for environments where pyplot expects matplotlib.artist
import matplotlib.pyplot as plt
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image as RLImage, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..anomalies import parse_timestamp
from ..models import EvidenceRecord
from ..validation_service import build_validation_metrics
from ..osint.privacy_review import build_osint_privacy_review
from ..reports.osint_appendix import build_osint_appendix_text
from ..ai import build_evidence_graph, case_readiness_scores, explain_contradictions, guardian_narrative, privacy_audit_status
try:
    from ...config import APP_COPYRIGHT, APP_NAME, APP_VERSION, APP_BUILD_CHANNEL
except ImportError:  # pragma: no cover - fallback for direct script execution
    from app.config import APP_COPYRIGHT, APP_NAME, APP_VERSION, APP_BUILD_CHANNEL
from PIL import Image, ImageSequence


class ReportService:
    def __init__(self, export_dir: Path) -> None:
        self.export_dir = export_dir
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("geotrace.report_service")

    def _safe_path(self, path: Path | str, *, privacy_mode: bool = True) -> str:
        path_obj = Path(path)
        if not privacy_mode:
            return str(path_obj)
        suffix = path_obj.suffix.lower()
        if suffix and not re.fullmatch(r"\.[a-z0-9]{1,8}", suffix):
            suffix = ""
        safe_leaf = f"[REDACTED_FILE]{suffix}"
        parts = list(path_obj.parts)
        if "case_data" in parts:
            return str(Path("[CASE_DATA]", safe_leaf))
        return str(Path("[REDACTED]", safe_leaf))

    def _normalize_privacy_level(self, privacy_mode: bool, privacy_level: str | None) -> str:
        if privacy_level:
            normalized = privacy_level.strip().lower().replace("-", "_")
            if normalized in {"full", "path_only", "redacted_text", "courtroom_redacted"}:
                return normalized
        return "redacted_text" if privacy_mode else "full"

    def _is_strict_redacted(self, privacy_level: str) -> bool:
        return privacy_level in {"redacted_text", "courtroom_redacted"}

    def _privacy_suffix(self, privacy_level: str) -> str:
        return {
            "full": "internal",
            "path_only": "path_only",
            "redacted_text": "shareable_redacted",
            "courtroom_redacted": "courtroom_redacted",
        }.get(privacy_level, "redacted")

    def _safe_file_name(self, record: EvidenceRecord, privacy_level: str) -> str:
        if not self._is_strict_redacted(privacy_level):
            return record.file_name
        suffix = Path(record.file_name).suffix.lower()
        if suffix and not re.fullmatch(r"\.[a-z0-9]{1,8}", suffix):
            suffix = ""
        return f"{record.evidence_id}{suffix}"

    def _safe_sensitive_label(self, value: str, privacy_level: str, replacement: str) -> str:
        clean = (value or "").strip()
        if self._is_strict_redacted(privacy_level) and clean and clean not in {"Unknown", "N/A", "Unavailable", "None"}:
            return replacement
        return clean or "Unknown"

    def _sanitize_export_value(self, value: Any, privacy_level: str, *, replacement: str | None = None) -> Any:
        if not self._is_strict_redacted(privacy_level):
            return value
        if value is None:
            return None
        if isinstance(value, dict):
            return {key: self._sanitize_export_value(item, privacy_level, replacement=replacement) for key, item in value.items()}
        if isinstance(value, list):
            return [self._sanitize_export_value(item, privacy_level, replacement=replacement) for item in value]
        if isinstance(value, str):
            return replacement if replacement is not None else self._redact_text(value, privacy_level)
        return value

    def _redact_text(self, value: str, privacy_level: str) -> str:
        if not self._is_strict_redacted(privacy_level) or not value:
            return value
        redacted = re.sub(r"https?://\S+|www\.\S+", "[REDACTED_URL]", value)
        redacted = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", redacted)
        redacted = re.sub(r"(?<![\w.])@[A-Za-z0-9_.-]{2,}", "[REDACTED_USERNAME]", redacted)
        redacted = re.sub(r"\b-?\d{1,3}\.\d{4,}\s*,\s*-?\d{1,3}\.\d{4,}\b", "[REDACTED_COORDINATES]", redacted)
        return redacted

    def _redact_collection(self, values: Any, privacy_level: str, *, replacement: str | None = None) -> Any:
        if not self._is_strict_redacted(privacy_level):
            return values
        if values is None:
            return values
        if isinstance(values, dict):
            return {key: self._redact_collection(value, privacy_level, replacement=replacement) for key, value in values.items()}
        if isinstance(values, list):
            if replacement:
                return [replacement for _ in values]
            return [self._redact_collection(value, privacy_level, replacement=replacement) for value in values]
        if isinstance(values, str):
            return replacement if replacement else self._redact_text(values, privacy_level)
        return values

    def _privacy_note(self, privacy_level: str) -> str:
        if privacy_level == "courtroom_redacted":
            return "Privacy level: courtroom_redacted — filenames, paths, previews, OCR text, URLs, usernames, emails, device labels, and location/entity text are removed from the courtroom package."
        if privacy_level == "redacted_text":
            return "Privacy level: redacted_text — paths, filenames, OCR text, URLs, usernames, emails, and location/entity text are redacted from shareable outputs."
        if privacy_level == "path_only":
            return "Privacy level: path_only — filesystem paths are redacted, but recovered text/entities remain visible for analyst review."
        return "Privacy level: full — no privacy redaction was applied."

    def _safe_geo_display(self, value: str, privacy_level: str) -> str:
        if not self._is_strict_redacted(privacy_level):
            return value
        clean = (value or "").strip()
        if not clean or clean.lower() in {"unavailable", "unknown", "no gps", "none", "absent"}:
            return value
        return "[REDACTED_LOCATION]"

    def _redact_freeform_text(self, value: str, privacy_level: str, *, replacement: str = "[REDACTED_TEXT]") -> str:
        if self._is_strict_redacted(privacy_level) and value:
            return replacement
        return value

    def _join_redacted(
        self,
        values: list[str],
        privacy_level: str,
        *,
        fallback: str = "None",
        limit: int | None = None,
        replacement: str | None = None,
    ) -> str:
        selected = list(values or [])
        if limit is not None:
            selected = selected[:limit]
        if not selected:
            return fallback
        redacted = self._redact_collection(selected, privacy_level, replacement=replacement)
        return ", ".join(str(item) for item in redacted)

    def _file_sha256(self, path: Path) -> str:
        try:
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        except Exception as exc:
            self.logger.warning("Could not hash report artifact %s: %s", path, exc)
            return ""

    def _artifact_entry(self, artifact_path: Path) -> dict:
        exists = artifact_path.exists()
        return {
            "path": self._safe_path(artifact_path, privacy_mode=True),
            "file_name": artifact_path.name,
            "exists": exists,
            "size_bytes": artifact_path.stat().st_size if exists else 0,
            "sha256": self._file_sha256(artifact_path) if exists else "",
        }

    def _collect_report_assets(self, privacy_level: str | None = None) -> dict:
        """Collect every packaged visual/report asset that should be hash-verified.

        `report_assets/` contains raw evidence previews and is omitted from strict
        redacted/courtroom exports. Root-level chart assets are safe to hash in
        the manifest, but sensitive map assets are still excluded in strict modes.
        """
        assets: dict[str, dict] = {}
        strict = self._is_strict_redacted(privacy_level or "full")
        sensitive_names = {"chart_map.png", "geolocation_map.html"}

        if not strict:
            assets_dir = self.export_dir / "report_assets"
            if assets_dir.exists():
                for asset_path in sorted(path for path in assets_dir.rglob("*") if path.is_file()):
                    try:
                        rel = asset_path.relative_to(self.export_dir).as_posix()
                    except Exception as exc:
                        self.logger.warning("Could not calculate relative path for report asset %s: %s", asset_path, exc)
                        rel = asset_path.name
                    entry = self._artifact_entry(asset_path)
                    entry["relative_path"] = rel
                    entry["file_name"] = rel
                    assets[rel] = entry

        for pattern in ("chart_*.png", "geolocation_map.html"):
            for asset_path in sorted(self.export_dir.glob(pattern)):
                if not asset_path.is_file():
                    continue
                if strict and asset_path.name in sensitive_names:
                    continue
                entry = self._artifact_entry(asset_path)
                entry["relative_path"] = asset_path.name
                assets[asset_path.name] = entry
        return assets

    def _clear_report_assets(self) -> None:
        assets_dir = self.export_dir / "report_assets"
        if assets_dir.exists():
            shutil.rmtree(assets_dir, ignore_errors=True)

    def _redaction_notice_html(self, label: str = "Evidence preview") -> str:
        return (
            "<div class='redaction-box'><strong>" + html.escape(label) + " omitted in shareable export.</strong> "
            "Generate an Internal Full report to include raw previews and unredacted OCR/location text.</div>"
        )


    def _prepare_preview_asset(self, record: EvidenceRecord, max_size: tuple[int, int] = (900, 540)) -> Path | None:
        assets_dir = self.export_dir / "report_assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(ch if ch.isalnum() or ch in {'-', '_'} else '_' for ch in record.file_name)[:80]
        output = assets_dir / f"{record.evidence_id}_{safe_name}.png"
        if output.exists():
            return output
        try:
            with Image.open(record.file_path) as image:
                frame = next(iter(ImageSequence.Iterator(image))).copy() if getattr(image, "is_animated", False) else image.copy()
                preview = frame.convert("RGB")
                preview.thumbnail(max_size)
                preview.save(output, format="PNG")
                return output
        except Exception as exc:
            self.logger.warning("Could not prepare preview asset for %s: %s", record.evidence_id, exc)
            return None

    def _corroboration_checklist_lines(self, record: EvidenceRecord, privacy_level: str = "full") -> list[str]:
        if record.ai_action_plan:
            return [self._redact_text(line, privacy_level) for line in record.ai_action_plan[:6]]
        lines = [f"Preserve original path and hashes for {record.evidence_id} before sharing or re-exporting."]
        lines.append(f"Validate the selected time anchor ({record.timestamp_source}) against uploads, chats, logs, or witness accounts.")
        if record.has_gps:
            lines.append(f"Verify native GPS coordinates externally around {self._safe_geo_display(record.gps_display, privacy_level)} before making courtroom location claims.")
        elif record.derived_geo_display != "Unavailable":
            lines.append(f"Treat derived geo ({self._safe_geo_display(record.derived_geo_display, privacy_level)}) as contextual only until browser/app history confirms it.")
        else:
            lines.append("Use timeline, source profile, and surrounding case context because no GPS anchor was recovered.")
        if record.visible_text_excerpt:
            lines.append("Cross-check OCR clues with the source application, browser history, or visible conversation context.")
        return [self._redact_text(line, privacy_level) for line in lines[:4]]

    def _ai_matrix_lines(self, record: EvidenceRecord, privacy_level: str = "full") -> list[str]:
        rows = record.ai_corroboration_matrix or []
        return [self._redact_text(row, privacy_level) for row in rows[:8]]

    def _build_static_map_chart(self, records: list[EvidenceRecord]) -> Path | None:
        gps_records = [r for r in records if r.has_gps or (r.derived_latitude is not None and r.derived_longitude is not None)]
        if not gps_records:
            return None
        output = self.export_dir / "chart_map.png"
        ordered = sorted(gps_records, key=lambda item: (parse_timestamp(item.timestamp) is None, parse_timestamp(item.timestamp) or item.timestamp, item.evidence_id))
        lats = [r.gps_latitude if r.gps_latitude is not None else r.derived_latitude for r in ordered]
        lons = [r.gps_longitude if r.gps_longitude is not None else r.derived_longitude for r in ordered]
        plt.close('all')
        fig, ax = plt.subplots(figsize=(8.8, 3.9), dpi=180)
        fig.patch.set_facecolor('#04101b')
        ax.set_facecolor('#04101b')
        ax.plot(lons, lats, linewidth=1.6, alpha=0.65, color='#21d0ff')
        for idx, record in enumerate(ordered, start=1):
            lon = record.gps_longitude if record.gps_longitude is not None else record.derived_longitude
            lat = record.gps_latitude if record.gps_latitude is not None else record.derived_latitude
            color = '#67ecff' if record.has_gps else '#ffd166'
            ax.scatter([lon], [lat], s=150, color=color, edgecolors='#e9f7ff', linewidths=0.8, zorder=5)
            ax.text(lon, lat, f'  #{idx:02d} {record.evidence_id}', color='#eef8ff', fontsize=8, va='bottom')
        ax.set_title('Map intelligence snapshot', color='#f3fbff', fontsize=12, pad=10, weight='bold')
        ax.set_xlabel('Longitude', color='#9ccae6')
        ax.set_ylabel('Latitude', color='#9ccae6')
        ax.tick_params(axis='x', colors='#dcefff', labelsize=8)
        ax.tick_params(axis='y', colors='#dcefff', labelsize=8)
        ax.grid(alpha=0.12, color='#7ecfff')
        for spine in ax.spines.values():
            spine.set_color('#2f5c8e')
        fig.tight_layout(pad=1.4)
        fig.savefig(output, facecolor=fig.get_facecolor(), bbox_inches='tight')
        plt.close(fig)
        return output

    def _case_metrics(self, records: List[EvidenceRecord]) -> dict:
        total = len(records)
        gps_count = sum(1 for record in records if record.has_gps)
        anomaly_count = sum(1 for record in records if record.risk_level != "Low")
        duplicate_groups = sorted({record.duplicate_group for record in records if record.duplicate_group})
        avg_score = round(sum(r.suspicion_score for r in records) / total) if total else 0
        dominant_source = Counter([record.source_type for record in records]).most_common(1)[0][0] if total else "Unknown"
        parser_issue_count = sum(1 for record in records if record.parser_status != "Valid" or record.signature_status == "Mismatch")
        hidden_count = sum(1 for record in records if record.hidden_code_indicators or record.hidden_suspicious_embeds)
        validation = build_validation_metrics(records)
        ai_flagged = sum(1 for record in records if record.ai_flags)
        ai_total_delta = sum(int(record.ai_score_delta or 0) for record in records)
        return {
            "total": total,
            "gps_count": gps_count,
            "anomaly_count": anomaly_count,
            "duplicate_groups": duplicate_groups,
            "avg_score": avg_score,
            "dominant_source": dominant_source,
            "parser_issue_count": parser_issue_count,
            "hidden_count": hidden_count,
            "ai_flagged": ai_flagged,
            "ai_total_delta": ai_total_delta,
            "validation_summary": validation.get("summary", "No linked validation dataset was found."),
            "validation_pass_rate": validation.get("pass_rate", 0.0),
        }

    def export_csv(self, records: Iterable[EvidenceRecord], *, privacy_mode: bool = True, privacy_level: str | None = None) -> Path:
        privacy_level = self._normalize_privacy_level(privacy_mode, privacy_level)
        privacy_mode = privacy_level != "full"
        suffix = self._privacy_suffix(privacy_level)
        output = self.export_dir / f"evidence_summary_{suffix}.csv"
        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "Privacy Level",
                    "Case ID",
                    "Evidence ID",
                    "File Name",
                    "Source Type",
                    "Timestamp",
                    "Timestamp Source",
                    "Timestamp Confidence",
                    "Device",
                    "GPS",
                    "Derived Geo",
                    "GPS Confidence",
                    "Score",
                    "Confidence",
                    "Evidentiary Value",
                    "Courtroom Strength",
                    "Risk",
                    "AI Flags",
                    "AI Score Delta",
                    "Integrity",
                    "SHA-256",
                ]
            )
            for record in records:
                writer.writerow(
                    [
                        privacy_level,
                        record.case_id,
                        record.evidence_id,
                        self._safe_file_name(record, privacy_level),
                        record.source_type,
                        record.timestamp,
                        record.timestamp_source,
                        record.timestamp_confidence,
                        self._safe_sensitive_label(record.device_model, privacy_level, "[REDACTED_DEVICE]"),
                        self._safe_geo_display(record.gps_display, privacy_level),
                        self._safe_geo_display(record.derived_geo_display, privacy_level),
                        record.gps_confidence,
                        record.suspicion_score,
                        record.confidence_score,
                        record.evidentiary_value,
                        record.courtroom_strength,
                        record.risk_level,
                        self._join_redacted(record.ai_flags, privacy_level, fallback="none"),
                        record.ai_score_delta,
                        record.integrity_status,
                        record.sha256,
                    ]
                )
        return output

    def export_json(self, records: Iterable[EvidenceRecord], *, privacy_mode: bool = True, privacy_level: str | None = None) -> Path:
        privacy_level = self._normalize_privacy_level(privacy_mode, privacy_level)
        privacy_mode = privacy_level != "full"
        output = self.export_dir / f"evidence_summary_{self._privacy_suffix(privacy_level)}.json"
        payload = []
        for record in records:
            payload.append(
                {
                    "case_id": record.case_id,
                    "case_name": record.case_name,
                    "evidence_id": record.evidence_id,
                    "file_name": self._safe_file_name(record, privacy_level),
                    "privacy_mode": privacy_mode,
                    "privacy_level": privacy_level,
                    "privacy_notes": self._privacy_note(privacy_level),
                    "file_path": self._safe_path(record.file_path, privacy_mode=privacy_mode),
                    "original_file_path": self._safe_path(record.original_file_path, privacy_mode=privacy_mode),
                    "working_copy_path": self._safe_path(record.working_copy_path, privacy_mode=privacy_mode),
                    "source_type": record.source_type,
                    "source_subtype": record.source_subtype,
                    "source_profile_confidence": record.source_profile_confidence,
                    "source_profile_reasons": self._redact_collection(record.source_profile_reasons, privacy_level),
                    "environment_profile": self._redact_text(record.environment_profile, privacy_level),
                    "app_detected": self._redact_text(record.app_detected, privacy_level),
                    "scene_group": record.scene_group,
                    "similarity_score": record.similarity_score,
                    "similarity_note": record.similarity_note,
                    "timestamp": record.timestamp,
                    "timestamp_source": record.timestamp_source,
                    "timestamp_confidence": record.timestamp_confidence,
                    "timestamp_verdict": record.timestamp_verdict,
                    "device_model": self._safe_sensitive_label(record.device_model, privacy_level, "[REDACTED_DEVICE]"),
                    "software": self._safe_sensitive_label(record.software, privacy_level, "[REDACTED_SOFTWARE]"),
                    "format": record.format_name,
                    "signature_status": record.signature_status,
                    "format_trust": record.format_trust,
                    "native_exif_count": len(record.exif),
                    "container_metadata": self._redact_collection(record.container_metadata, privacy_level),
                    "dimensions": record.dimensions,
                    "gps": {
                        "display": self._safe_geo_display(record.gps_display, privacy_level),
                        "latitude": None if self._is_strict_redacted(privacy_level) else record.gps_latitude,
                        "longitude": None if self._is_strict_redacted(privacy_level) else record.gps_longitude,
                        "altitude": None if self._is_strict_redacted(privacy_level) else record.gps_altitude,
                        "source": self._redact_freeform_text(record.gps_source, privacy_level, replacement="[REDACTED_LOCATION_SOURCE]"),
                        "confidence": record.gps_confidence,
                        "verification": self._redact_freeform_text(record.gps_verification, privacy_level, replacement="[REDACTED_LOCATION_CHECK]"),
                        "derived": {
                            "display": self._safe_geo_display(record.derived_geo_display, privacy_level),
                            "latitude": None if self._is_strict_redacted(privacy_level) else record.derived_latitude,
                            "longitude": None if self._is_strict_redacted(privacy_level) else record.derived_longitude,
                            "source": self._redact_freeform_text(record.derived_geo_source, privacy_level, replacement="[REDACTED_LOCATION_SOURCE]"),
                            "confidence": record.derived_geo_confidence,
                            "note": self._redact_freeform_text(record.derived_geo_note, privacy_level),
                        },
                        "status": self._redact_freeform_text(record.geo_status, privacy_level, replacement="[REDACTED_LOCATION_STATUS]"),
                    },
                    "anomaly_reasons": self._redact_collection(record.anomaly_reasons, privacy_level),
                    "anomaly_contributors": self._redact_collection(record.anomaly_contributors, privacy_level),
                    "osint_leads": self._redact_collection(record.osint_leads, privacy_level),
                    "osint_ai_scene": {
                        "label": record.osint_scene_label,
                        "confidence": record.osint_scene_confidence,
                        "summary": self._redact_freeform_text(record.osint_scene_summary, privacy_level),
                        "reasons": self._redact_collection(record.osint_scene_reasons, privacy_level),
                        "detected_map_context": self._redact_freeform_text(record.detected_map_context, privacy_level, replacement="[REDACTED_LOCATION_CONTEXT]"),
                        "possible_place": self._redact_freeform_text(record.possible_place, privacy_level, replacement="[REDACTED_LOCATION]"),
                        "map_confidence": record.map_confidence,
                    },
                    "osint_content_profile": {
                        "label": record.osint_content_label,
                        "confidence": record.osint_content_confidence,
                        "summary": self._redact_freeform_text(record.osint_content_summary, privacy_level),
                        "tags": self._redact_collection(record.osint_content_tags, privacy_level),
                        "visual_cues": self._redact_collection(record.osint_visual_cues, privacy_level),
                        "text_cues": self._redact_collection(record.osint_text_cues, privacy_level),
                        "location_hypotheses": self._redact_collection(record.osint_location_hypotheses, privacy_level, replacement="[REDACTED_LOCATION_HYPOTHESIS]"),
                        "source_context": self._redact_freeform_text(record.osint_source_context, privacy_level),
                        "limitations": self._redact_collection(record.osint_content_limitations, privacy_level),
                        "next_actions": self._redact_collection(record.osint_next_actions, privacy_level),
                        "structured_hypotheses": self._redact_collection(record.osint_hypothesis_cards, privacy_level, replacement="[REDACTED_OSINT_HYPOTHESIS]"),
                        "entities": self._redact_collection(record.osint_entities, privacy_level, replacement="[REDACTED_OSINT_ENTITY]"),
                        "corroboration_matrix": self._redact_collection(record.osint_corroboration_matrix, privacy_level, replacement="[REDACTED_OSINT_CORROBORATION]"),
                        "analyst_decisions": self._redact_collection(record.osint_analyst_decisions, privacy_level, replacement="[REDACTED_ANALYST_DECISION]"),
                        "privacy_review": record.osint_privacy_review,
                        "cache_status": record.osint_cache_status,
                    },
                    "map_intelligence": {
                        "app_detected": record.map_app_detected,
                        "map_type": record.map_type,
                        "route_overlay_detected": record.route_overlay_detected,
                        "route_confidence": record.route_confidence,
                        "candidate_city": self._redact_freeform_text(record.candidate_city, privacy_level, replacement="[REDACTED_LOCATION]"),
                        "candidate_area": self._redact_freeform_text(record.candidate_area, privacy_level, replacement="[REDACTED_LOCATION]"),
                        "landmarks_detected": self._redact_collection(record.landmarks_detected, privacy_level, replacement="[REDACTED_LOCATION]"),
                        "place_candidates": self._redact_collection(record.place_candidates, privacy_level, replacement="[REDACTED_LOCATION]"),
                        "confidence": record.map_intelligence_confidence,
                        "ocr_language_hint": record.map_ocr_language_hint,
                        "summary": self._redact_freeform_text(record.map_intelligence_summary, privacy_level, replacement="[REDACTED_LOCATION_CONTEXT]"),
                        "reasons": self._redact_collection(record.map_intelligence_reasons, privacy_level),
                        "evidence_basis": record.map_evidence_basis,
                        "evidence_strength": record.map_evidence_strength,
                        "limitations": self._redact_collection(record.map_limitations, privacy_level),
                        "recommended_actions": self._redact_collection(record.map_recommended_actions, privacy_level),
                        "place_candidate_rankings": self._redact_collection(record.place_candidate_rankings, privacy_level, replacement="[REDACTED_LOCATION_RANKING]"),
                    },
                    "analyst_verdict": self._redact_freeform_text(record.analyst_verdict, privacy_level),
                    "courtroom_notes": self._redact_freeform_text(record.courtroom_notes, privacy_level),
                    "hidden": {
                        "summary": self._redact_freeform_text(record.hidden_code_summary, privacy_level),
                        "overview": self._redact_freeform_text(record.hidden_content_overview, privacy_level),
                        "context_summary": self._redact_freeform_text(record.hidden_context_summary, privacy_level),
                        "types": record.hidden_finding_types,
                        "indicators": self._redact_collection(record.hidden_code_indicators, privacy_level),
                        "suspicious_embeds": self._redact_collection(record.hidden_suspicious_embeds, privacy_level),
                        "payload_markers": self._redact_collection(record.hidden_payload_markers, privacy_level),
                        "readable_strings": self._redact_collection(record.extracted_strings, privacy_level, replacement="[REDACTED_TEXT]"),
                        "urls": self._redact_collection(record.urls_found, privacy_level, replacement="[REDACTED_URL]"),
                        "stego_suspicion": record.stego_suspicion,
                    },
                    "visible_text": {
                        "excerpt": self._redact_freeform_text(record.visible_text_excerpt, privacy_level),
                        "lines": self._redact_collection(record.visible_text_lines, privacy_level, replacement="[REDACTED_TEXT]"),
                        "urls": self._redact_collection(record.visible_urls, privacy_level, replacement="[REDACTED_URL]"),
                        "times": self._redact_collection(record.visible_time_strings, privacy_level, replacement="[REDACTED_TIME]"),
                        "locations": self._redact_collection(record.visible_location_strings, privacy_level, replacement="[REDACTED_LOCATION]"),
                        "ocr_region_signals": self._redact_collection(record.ocr_region_signals, privacy_level, replacement="[REDACTED_OCR_REGION]"),
                    },
                    "ocr": {
                        "raw_text": self._redact_freeform_text(record.ocr_raw_text, privacy_level),
                        "note": self._redact_freeform_text(record.ocr_note, privacy_level),
                        "confidence": record.ocr_confidence,
                        "analyst_relevance": self._redact_freeform_text(record.ocr_analyst_relevance, privacy_level),
                        "entities": {
                            "app_names": self._redact_collection(record.ocr_app_names, privacy_level, replacement="[REDACTED_APP]"),
                            "locations": self._redact_collection(record.ocr_location_entities, privacy_level, replacement="[REDACTED_LOCATION]"),
                            "times": self._redact_collection(record.ocr_time_entities, privacy_level, replacement="[REDACTED_TIME]"),
                            "urls": self._redact_collection(record.ocr_url_entities, privacy_level, replacement="[REDACTED_URL]"),
                            "usernames": self._redact_collection(record.ocr_username_entities, privacy_level, replacement="[REDACTED_USERNAME]"),
                            "map_labels": self._redact_collection(record.ocr_map_labels, privacy_level, replacement="[REDACTED_LOCATION]"),
                        },
                    },
                    "acquisition": {
                        "imported_at": record.imported_at,
                        "original_path": self._safe_path(record.original_file_path, privacy_mode=privacy_mode),
                        "working_copy_path": self._safe_path(record.working_copy_path, privacy_mode=privacy_mode),
                        "source_sha256": record.source_sha256,
                        "source_md5": record.source_md5,
                        "working_sha256": record.working_sha256,
                        "working_md5": record.working_md5,
                        "copy_verified": record.copy_verified,
                        "acquisition_note": self._redact_text(record.acquisition_note, privacy_level),
                        "custody_events_slice": self._redact_collection(record.custody_event_summary, privacy_level),
                    },
                    "time_candidates": self._redact_collection(record.time_candidates, privacy_level, replacement="[REDACTED_TIME_CANDIDATE]"),
                    "time_conflicts": self._redact_collection(record.time_conflicts, privacy_level, replacement="[REDACTED_TIME_CONFLICT]"),
                    "integrity_note": self._redact_freeform_text(record.integrity_note, privacy_level),
                    "exif_warning": self._redact_freeform_text(record.exif_warning, privacy_level),
                    "created_time_note": self._redact_freeform_text(record.created_time_note, privacy_level),
                    "suspicion_score": record.suspicion_score,
                    "confidence_score": record.confidence_score,
                    "evidentiary_value": record.evidentiary_value,
                    "evidentiary_label": record.evidentiary_label,
                    "courtroom_strength": record.courtroom_strength,
                    "courtroom_label": record.courtroom_label,
                    "risk_level": record.risk_level,
                    "tags": self._redact_text(record.tags, privacy_level),
                    "bookmarked": record.bookmarked,
                    "sha256": record.sha256,
                    "md5": record.md5,
                    "perceptual_hash": record.perceptual_hash,
                    "metadata_issues": self._redact_collection(record.metadata_issues, privacy_level),
                    "metadata_strengths": self._redact_collection(record.metadata_strengths, privacy_level),
                    "metadata_recommendations": self._redact_collection(record.metadata_recommendations, privacy_level),
                    "metadata_issue_summary": self._redact_freeform_text(record.metadata_issue_summary, privacy_level),
                    "gps_ladder": self._redact_collection(record.gps_ladder, privacy_level, replacement="[REDACTED_LOCATION_CHECK]"),
                    "gps_primary_issue": self._redact_freeform_text(record.gps_primary_issue, privacy_level, replacement="[REDACTED_LOCATION_ISSUE]"),
                    "duplicate": {
                        "group": record.duplicate_group,
                        "relation": record.duplicate_relation,
                        "method": record.duplicate_method,
                        "peers": self._redact_collection(record.duplicate_peers, privacy_level),
                        "distance": record.duplicate_distance,
                    },
                    "score_explainability": {
                        "primary_issue": self._redact_freeform_text(record.score_primary_issue, privacy_level),
                        "reason": self._redact_freeform_text(record.score_reason, privacy_level),
                        "next_step": self._redact_freeform_text(record.score_next_step, privacy_level),
                        "summary": self._redact_freeform_text(record.score_summary, privacy_level),
                    },
                    "ai_assessment": {
                        "provider": record.ai_provider,
                        "risk_label": record.ai_risk_label,
                        "score_delta": record.ai_score_delta,
                        "confidence_delta": record.ai_confidence,
                        "priority_rank": record.ai_priority_rank,
                        "evidence_strength": record.evidence_strength_label,
                        "evidence_strength_score": record.evidence_strength_score,
                        "evidence_strength_reasons": self._redact_collection(record.evidence_strength_reasons, privacy_level),
                        "evidence_strength_limitations": self._redact_collection(record.evidence_strength_limitations, privacy_level),
                        "executive_note": self._redact_freeform_text(record.ai_executive_note, privacy_level),
                        "summary": self._redact_freeform_text(record.ai_summary, privacy_level),
                        "flags": self._redact_collection(record.ai_flags, privacy_level),
                        "reasons": self._redact_collection(record.ai_reasons, privacy_level),
                        "case_links": self._redact_collection(record.ai_case_links, privacy_level),
                        "evidence_graph": self._redact_collection(record.ai_evidence_graph, privacy_level),
                        "contradiction_explainer": self._redact_collection(record.ai_contradiction_explainer, privacy_level),
                        "courtroom_readiness": self._redact_freeform_text(record.ai_courtroom_readiness, privacy_level),
                        "next_best_action": self._redact_text(record.ai_next_best_action, privacy_level),
                        "privacy_audit": self._redact_freeform_text(record.ai_privacy_audit, privacy_level),
                        "action_plan": self._redact_collection(record.ai_action_plan, privacy_level),
                        "corroboration_matrix": self._redact_collection(record.ai_corroboration_matrix, privacy_level),
                        "breakdown": self._redact_collection(record.ai_breakdown, privacy_level, replacement="[REDACTED_AI_BREAKDOWN]"),
                    },
                    "validation": {
                        "hits": self._redact_collection(record.validation_hits, privacy_level),
                        "misses": self._redact_collection(record.validation_misses, privacy_level),
                    },
                }
            )
        output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return output

    def export_executive_summary(self, records: List[EvidenceRecord], case_id: str, case_name: str, *, privacy_mode: bool = True, privacy_level: str | None = None) -> Path:
        privacy_level = self._normalize_privacy_level(privacy_mode, privacy_level)
        output = self.export_dir / f"executive_summary_{self._privacy_suffix(privacy_level)}.txt"
        metrics = self._case_metrics(records)
        lines = [
            f"{APP_NAME} — Executive Summary",
            f"Case ID: {case_id}",
            f"Case Name: {case_name}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Version: {APP_VERSION} ({APP_BUILD_CHANNEL})",
            self._privacy_note(privacy_level),
            "",
            f"Total evidence items: {metrics['total']}",
            f"Native GPS items: {metrics['gps_count']}",
            f"Derived geo clues: {sum(1 for r in records if r.derived_geo_display != 'Unavailable')}",
            f"Map intelligence items: {sum(1 for r in records if r.map_intelligence_confidence > 0)}",
            f"Route/navigation screenshots: {sum(1 for r in records if r.route_overlay_detected)}",
            f"Review items (non-low risk): {metrics['anomaly_count']}",
            f"AI-assisted flags: {metrics['ai_flagged']} item(s) / total AI delta {metrics['ai_total_delta']}",
            f"Parser/signature issues: {metrics['parser_issue_count']}",
            f"Hidden/code hits: {metrics['hidden_count']}",
            f"Duplicate clusters: {len(metrics['duplicate_groups'])}",
            f"Average suspicion score: {metrics['avg_score']}",
            f"Dominant source profile: {metrics['dominant_source']}",
            f"Validation dataset: {metrics['validation_summary']}",
            "",
            "Top priority evidence:",
        ]
        for record in sorted(records, key=lambda r: (-r.evidentiary_value, -r.suspicion_score, -r.confidence_score, r.evidence_id))[:5]:
            lines.extend(
                [
                    f"- {record.evidence_id} | {self._safe_file_name(record, privacy_level)} | {record.risk_level} | Score {record.suspicion_score} | Confidence {record.confidence_score}% | Value {record.evidentiary_value}% | Courtroom {record.courtroom_strength}%",
                    f"  Time: {record.timestamp} ({record.timestamp_source}, {record.timestamp_confidence}%)",
                    f"  GPS: {self._safe_geo_display(record.gps_display, privacy_level)} ({record.gps_confidence}%) | Derived: {self._safe_geo_display(record.derived_geo_display, privacy_level)} ({record.derived_geo_confidence}%)",
                    f"  Map AI: {record.map_app_detected} | {record.map_type} | route {'yes' if record.route_overlay_detected else 'no'} | city {self._redact_freeform_text(record.candidate_city, privacy_level, replacement='[REDACTED_LOCATION]')}",
                    f"  Map basis: {', '.join(record.map_evidence_basis) if record.map_evidence_basis else 'not available'} | Place ranking: {self._join_redacted(record.place_candidate_rankings, privacy_level, limit=3, replacement='[REDACTED_LOCATION_RANKING]')}",
                    f"  AI: {self._redact_text(record.ai_risk_label, privacy_level)} | delta +{record.ai_score_delta} | flags: {self._join_redacted(record.ai_flags, privacy_level, fallback='none')}",
                    f"  Primary issue: {self._redact_freeform_text(record.score_primary_issue, privacy_level)}",
                    f"  Why it matters: {self._redact_freeform_text(record.score_reason, privacy_level)}",
                    f"  Next step: {self._redact_freeform_text(record.score_next_step, privacy_level)}",
                ]
            )
        output.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        return output


    def export_privacy_guardian_summary(self, records: List[EvidenceRecord], case_id: str, case_name: str, *, privacy_mode: bool = True, privacy_level: str | None = None) -> Path:
        privacy_level = self._normalize_privacy_level(privacy_mode, privacy_level)
        output = self.export_dir / f"privacy_guardian_{self._privacy_suffix(privacy_level)}.txt"
        audit = privacy_audit_status(records, privacy_level=privacy_level)
        lines = [
            f"{APP_NAME} — Privacy Guardian Pre-Export Check",
            f"Case ID: {case_id}",
            f"Case Name: {case_name}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            self._privacy_note(privacy_level),
            "",
            audit.get("summary", "Privacy audit unavailable."),
            "",
            "Export rule:",
            "- Internal Full may contain raw previews, paths, OCR text, URLs, usernames, and location context.",
            "- Shareable Redacted and Courtroom Redacted should not include raw preview images, exact coordinates, raw OCR text, or original filenames.",
        ]
        output.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        return output

    def export_ai_guardian_summary(self, records: List[EvidenceRecord], case_id: str, case_name: str, *, privacy_mode: bool = True, privacy_level: str | None = None) -> Path:
        privacy_level = self._normalize_privacy_level(privacy_mode, privacy_level)
        output = self.export_dir / f"ai_guardian_summary_{self._privacy_suffix(privacy_level)}.txt"
        readiness = case_readiness_scores(records)
        graph = build_evidence_graph(records)
        contradictions = explain_contradictions(records)
        privacy = privacy_audit_status(records, privacy_level=privacy_level)
        lines = [
            f"{APP_NAME} — AI Guardian Summary",
            f"Case ID: {case_id}",
            f"Case Name: {case_name}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            self._privacy_note(privacy_level),
            "", "Case Readiness", "--------------", readiness.get("summary", "Readiness unavailable."),
            "", "AI Guardian Narrative", "-------------------", guardian_narrative(records, privacy_level=privacy_level),
            "", "Map Intelligence", "----------------",
        ]
        map_records = [record for record in records if record.map_intelligence_confidence > 0 or record.route_overlay_detected]
        if map_records:
            for record in sorted(map_records, key=lambda item: (-item.map_intelligence_confidence, item.evidence_id))[:20]:
                route = "yes" if record.route_overlay_detected else "no"
                city = self._redact_freeform_text(record.candidate_city, privacy_level, replacement="[REDACTED_LOCATION]")
                area = self._redact_freeform_text(record.candidate_area, privacy_level, replacement="[REDACTED_LOCATION]")
                lines.append(f"- {record.evidence_id}: {record.map_app_detected} | {record.map_type} | route={route} ({record.route_confidence}%) | city={city} | area={area} | confidence={record.map_intelligence_confidence}%")
                if record.landmarks_detected:
                    lines.append("  Landmarks: " + self._join_redacted(record.landmarks_detected, privacy_level, limit=5, replacement="[REDACTED_LOCATION]"))
        else:
            lines.append("- No map/navigation intelligence detected yet.")
        lines.extend(["", "AI Evidence Graph", "-----------------"])
        if graph:
            lines.extend(f"- {edge.source_id} <-> {edge.target_id} [{edge.relation}, {edge.weight}%]: {self._redact_text(edge.reason, privacy_level)}" for edge in graph[:30])
        else:
            lines.append("- No meaningful evidence relationships were detected yet.")
        lines.extend(["", "AI Contradiction Explainer", "----------------------------"])
        if contradictions:
            lines.extend(f"- {self._redact_text(item, privacy_level)}" for item in contradictions[:20])
        else:
            lines.append("- No impossible-travel contradictions were found with current anchors.")
        lines.extend(["", "AI Privacy Auditor", "------------------", privacy.get("summary", "Privacy audit unavailable.")])
        lines.extend(["", "Per-Evidence Courtroom Readiness", "--------------------------------"])
        for record in sorted(records, key=lambda item: (-item.courtroom_strength, item.evidence_id)):
            lines.append(f"- {record.evidence_id} | Courtroom {record.courtroom_strength}% | AI priority #{record.ai_priority_rank or '-'} | Next: {self._redact_text(record.ai_next_best_action or record.score_next_step, privacy_level)}")
            if record.ai_courtroom_readiness:
                lines.append("  " + self._redact_text(record.ai_courtroom_readiness.replace(chr(10), " | "), privacy_level))
        output.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        return output

    def export_osint_appendix(self, records: List[EvidenceRecord], case_id: str, case_name: str, *, privacy_mode: bool = True, privacy_level: str | None = None) -> Path:
        privacy_level = self._normalize_privacy_level(privacy_mode, privacy_level)
        output = self.export_dir / f"osint_appendix_{self._privacy_suffix(privacy_level)}.txt"

        def _join(values, limit: int, replacement: str) -> str:
            return self._join_redacted(values, privacy_level, limit=limit, replacement=replacement)

        body = build_osint_appendix_text(
            list(records),
            case_id=case_id,
            case_name=case_name,
            privacy_level=privacy_level,
            file_name=lambda record: self._safe_file_name(record, privacy_level),
            redact_text=lambda value: self._redact_freeform_text(value, privacy_level),
            join_redacted=_join,
        )
        output.write_text(body, encoding="utf-8")
        return output

    def export_validation_summary(self, records: List[EvidenceRecord], case_id: str, case_name: str, *, privacy_mode: bool = True, privacy_level: str | None = None) -> Path:
        privacy_level = self._normalize_privacy_level(privacy_mode, privacy_level)
        output = self.export_dir / f"validation_summary_{self._privacy_suffix(privacy_level)}.txt"
        total = len(records)
        parser_valid = sum(1 for record in records if record.parser_status == "Valid")
        native_time = sum(1 for record in records if record.timestamp_confidence >= 80)
        native_gps = sum(1 for record in records if record.gps_confidence >= 80)
        hidden_hits = sum(1 for record in records if record.hidden_code_indicators)
        validation = build_validation_metrics(records)
        lines = [
            f"{APP_NAME} — Validation Summary",
            f"Case ID: {case_id}",
            f"Case Name: {case_name}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            self._privacy_note(privacy_level),
            "",
            f"Evidence count: {total}",
            f"Parser-success count: {parser_valid}/{total}",
            f"Strong time anchors: {native_time}/{total}",
            f"Strong GPS anchors: {native_gps}/{total}",
            f"Derived geo clues: {sum(1 for record in records if record.derived_geo_display != 'Unavailable' or record.possible_geo_clues)}",
            f"Map intelligence items: {sum(1 for record in records if record.map_intelligence_confidence > 0)}",
            f"Route/navigation screenshots: {sum(1 for record in records if record.route_overlay_detected)}",
            f"Hidden/code detections: {hidden_hits}",
            f"AI-assisted flagged items: {sum(1 for record in records if record.ai_flags)}/{total}",
            f"Courtroom-ready posture (>=60%): {sum(1 for record in records if record.courtroom_strength >= 60)}/{total}",
            f"OCR/entity-rich items: {sum(1 for record in records if (record.ocr_location_entities or record.ocr_time_entities or record.ocr_url_entities or record.ocr_username_entities))}/{total}",
            f"Validation dataset summary: {validation.get('summary', 'No linked validation dataset was found.')}",
            "",
            "Interpretation:",
            "- Strong time anchors = Native EXIF Original or equivalent embedded source.",
            "- Strong GPS anchors = valid native GPS coordinates recovered from EXIF tags.",
            "- Derived geo clues = location leads parsed from visible screenshot/browser/map content rather than native EXIF.",
            "- Map intelligence items = deterministic OSINT map/layout/route signals from pixels, OCR, and map UI text.",
            "- Parser-success count = files rendered successfully by Pillow in the current workflow.",
            "- OCR/entity-rich items = screenshots or captures where OCR recovered apps, locations, URLs, times, usernames, or map labels.",
            "- Hidden/code detections are heuristic findings and still require analyst review.",
            "- AI-assisted flags are batch-level triage signals; they help find outliers and timeline contradictions, but they do not replace manual forensic validation.",
        ]
        if validation.get('ground_truth_loaded'):
            lines.extend(["", "Per-file validation checks:"])
            for record in records:
                if record.validation_hits or record.validation_misses:
                    lines.append(f"- {self._safe_file_name(record, privacy_level)}: hits={len(record.validation_hits)} misses={len(record.validation_misses)}")
                    if record.validation_misses:
                        lines.extend([f"    miss: {self._redact_text(item, privacy_level)}" for item in record.validation_misses[:3]])
        output.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        return output

    def export_package_manifest(self, payload: dict, *, privacy_level: str | None = None) -> Path:
        output = self.export_dir / "export_manifest.json"
        enriched: dict = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "privacy_level": privacy_level or "unknown",
            "privacy_note": "Exported paths are share-safe where supported; hashes verify report artifacts, chart assets, and packaged preview assets where present.",
            "artifacts": {},
            "report_assets": {},
        }
        for key, value in payload.items():
            artifact_path = Path(value)
            enriched["artifacts"][key] = self._artifact_entry(artifact_path)
        enriched["report_assets"] = self._collect_report_assets(privacy_level)
        output.write_text(json.dumps(enriched, indent=2), encoding="utf-8")
        return output

    def export_courtroom_summary(self, records: List[EvidenceRecord], case_id: str, case_name: str, *, privacy_mode: bool = True, privacy_level: str | None = None) -> Path:
        privacy_level = self._normalize_privacy_level(privacy_mode, privacy_level)
        output = self.export_dir / f"courtroom_summary_{self._privacy_suffix(privacy_level)}.txt"
        metrics = self._case_metrics(records)
        ordered = sorted(records, key=lambda r: (-r.suspicion_score, r.evidence_id))
        lines = [
            f"{APP_NAME} — Courtroom Summary",
            f"Case ID: {case_id}",
            f"Case Name: {case_name}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Version: {APP_VERSION} ({APP_BUILD_CHANNEL})",
            self._privacy_note(privacy_level),
            "",
            "Executive Summary",
            "-----------------",
            f"Total evidence items: {metrics['total']}",
            f"High-risk items: {sum(1 for r in records if r.risk_level == 'High')}",
            f"GPS-bearing items: {metrics['gps_count']}",
            f"AI-assisted flagged items: {metrics['ai_flagged']}",
            f"Duplicate clusters: {len(metrics['duplicate_groups'])}",
            "",
            "Courtroom Readiness",
            "-------------------",
        ]
        for record in ordered[:5]:
            lines.extend(
                [
                    f"{record.evidence_id} | {self._safe_file_name(record, privacy_level)} | {record.risk_level} | Score {record.suspicion_score} | Value {record.evidentiary_value}% | Courtroom {record.courtroom_strength}%",
                    f"  Time: {record.timestamp} ({record.timestamp_source}, {record.timestamp_confidence}%)",
                    f"  GPS: {self._safe_geo_display(record.gps_display, privacy_level)} ({record.gps_confidence}%) | Derived: {self._safe_geo_display(record.derived_geo_display, privacy_level)} ({record.derived_geo_confidence}%)",
                    f"  Map AI: {record.map_app_detected} | {record.map_type} | route {'yes' if record.route_overlay_detected else 'no'} | city {self._redact_freeform_text(record.candidate_city, privacy_level, replacement='[REDACTED_LOCATION]')}",
                    f"  Map basis: {', '.join(record.map_evidence_basis) if record.map_evidence_basis else 'not available'} | Place ranking: {self._join_redacted(record.place_candidate_rankings, privacy_level, limit=3, replacement='[REDACTED_LOCATION_RANKING]')}",
                    f"  AI: {self._redact_text(record.ai_risk_label, privacy_level)} | delta +{record.ai_score_delta} | flags: {self._join_redacted(record.ai_flags, privacy_level, fallback='none')}",
                    f"  Parser: {record.parser_status} | Signature: {record.signature_status} | Trust: {record.format_trust}",
                    f"  Primary issue: {self._redact_freeform_text(record.score_primary_issue, privacy_level)}",
                    f"  Why it matters: {self._redact_freeform_text(record.score_reason, privacy_level)}",
                    f"  Courtroom note: {self._redact_freeform_text(record.courtroom_notes, privacy_level)}",
                    f"  Next step: {self._redact_freeform_text(record.score_next_step, privacy_level)}",
                    "",
                ]
            )
        output.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        return output

    def export_html(self, records: List[EvidenceRecord], case_id: str, case_name: str, custody_log: str = "", *, privacy_mode: bool = True, privacy_level: str | None = None) -> Path:
        privacy_level = self._normalize_privacy_level(privacy_mode, privacy_level)
        privacy_mode = privacy_level != "full"
        output = self.export_dir / f"forensic_report_{self._privacy_suffix(privacy_level)}.html"
        if self._is_strict_redacted(privacy_level):
            self._clear_report_assets()
        metrics = self._case_metrics(records)
        generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        def badge_class(level: str) -> str:
            return {"High": "badge-high", "Medium": "badge-medium"}.get(level, "badge-low")

        rows = "\n".join(
            f"""
            <tr>
                <td>{html.escape(record.evidence_id)}</td>
                <td><strong>{html.escape(self._safe_file_name(record, privacy_level))}</strong><br><span class='muted'>{html.escape(self._safe_path(record.original_file_path, privacy_mode=privacy_mode))}</span></td>
                <td>{html.escape(record.source_type)}</td>
                <td>{html.escape(record.timestamp)}<br><span class='muted'>{html.escape(record.timestamp_source)} • {record.timestamp_confidence}%</span></td>
                <td>{html.escape(self._safe_sensitive_label(record.device_model, privacy_level, "[REDACTED_DEVICE]"))}</td>
                <td>{html.escape(self._safe_geo_display(record.gps_display, privacy_level))}<br><span class='muted'>Native {record.gps_confidence}% • Derived {record.derived_geo_confidence}%</span><br><span class='muted'>{html.escape(self._safe_geo_display(record.derived_geo_display, privacy_level))}</span></td>
                <td>{record.suspicion_score}<br><span class='muted'>AI +{record.ai_score_delta}</span></td>
                <td>{record.confidence_score}%<br><span class='muted'>{html.escape(record.ai_risk_label)}</span></td>
                <td>{record.evidentiary_value}%</td>
                <td>{record.courtroom_strength}%</td>
                <td>{html.escape(record.parser_status)} / {html.escape(record.signature_status)}</td>
                <td><span class="risk {badge_class(record.risk_level)}">{html.escape(record.risk_level)}</span></td>
            </tr>
            """
            for record in records
        )

        appendix_blocks = []
        for record in records:
            preview_asset = None if self._is_strict_redacted(privacy_level) else self._prepare_preview_asset(record)
            preview_html = self._redaction_notice_html("Evidence preview") if self._is_strict_redacted(privacy_level) else ""
            if preview_asset is not None:
                rel_preview = preview_asset.relative_to(self.export_dir).as_posix()
                preview_html = f"<img class='evidence-preview' src='{html.escape(rel_preview)}' alt='{html.escape(self._safe_file_name(record, privacy_level))} preview'>"
            appendix_blocks.append(
                f"""
                <div class="detail-card">
                    <h3>{html.escape(record.evidence_id)} — {html.escape(self._safe_file_name(record, privacy_level))}</h3>
                    {preview_html}
                    <div class="pill-row">
                        <span class="pill">{html.escape(record.source_type)}</span>
                        <span class="pill">{html.escape(record.timestamp_source)} • {record.timestamp_confidence}%</span>
                        <span class="pill">Native GPS {html.escape(self._safe_geo_display(record.gps_display, privacy_level))} • {record.gps_confidence}%</span>
                        <span class="pill">Derived Geo {html.escape(self._safe_geo_display(record.derived_geo_display, privacy_level))} • {record.derived_geo_confidence}%</span>
                        <span class="pill">Signature {html.escape(record.signature_status)}</span>
                        <span class="pill">Trust {html.escape(record.format_trust)}</span>
                        <span class="pill">Score {record.suspicion_score}</span>
                        <span class="pill">Value {record.evidentiary_value}%</span>
                        <span class="pill">Courtroom {record.courtroom_strength}%</span>
                    </div>
                    <p><strong>Why this matters:</strong> {html.escape(self._redact_freeform_text(record.analyst_verdict, privacy_level))}</p>
                    <p><strong>Courtroom note:</strong> {html.escape(self._redact_freeform_text(record.courtroom_notes, privacy_level))}</p>
                    <p><strong>GPS verification:</strong> {html.escape(self._redact_freeform_text(record.gps_verification, privacy_level))}</p>
                    <p><strong>Derived geo:</strong> {html.escape(self._redact_freeform_text(record.derived_geo_note, privacy_level))}</p>
                    <p><strong>Hidden/content summary:</strong> {html.escape(self._redact_freeform_text(record.hidden_code_summary, privacy_level))}</p>
                    <p><strong>OCR analyst relevance:</strong> {html.escape(self._redact_freeform_text(record.ocr_analyst_relevance, privacy_level))}</p>
                    <p><strong>OCR note:</strong> {html.escape(self._redact_freeform_text(record.ocr_note, privacy_level))}</p>
                    <p><strong>OCR entities:</strong> Apps {html.escape(self._join_redacted(record.ocr_app_names, privacy_level))} • Locations {html.escape(self._join_redacted(record.ocr_location_entities, privacy_level, limit=3, replacement='[REDACTED_LOCATION]'))} • Times {html.escape(self._join_redacted(record.ocr_time_entities, privacy_level, limit=3))} • URLs {html.escape(self._join_redacted(record.ocr_url_entities, privacy_level, limit=2, replacement='[REDACTED_URL]'))} • Usernames {html.escape(self._join_redacted(record.ocr_username_entities, privacy_level, limit=3, replacement='[REDACTED_USERNAME]'))}</p>
                    <p><strong>AI-assisted review:</strong> {html.escape(self._redact_freeform_text(record.ai_summary, privacy_level))} Flags: {html.escape(self._join_redacted(record.ai_flags, privacy_level))}.</p>
                    <p><strong>OSINT AI scene:</strong> {html.escape(record.osint_scene_label)} • {record.osint_scene_confidence}% confidence • Map confidence {record.map_confidence}%</p>
                    <p><strong>OSINT Content v2:</strong> {html.escape(record.osint_content_label)} • {record.osint_content_confidence}% confidence</p>
                    <p><strong>Content summary:</strong> {html.escape(self._redact_freeform_text(record.osint_content_summary, privacy_level, replacement='[REDACTED_OSINT_CONTENT]'))}</p>
                    <p><strong>Content tags:</strong> {html.escape(self._join_redacted(record.osint_content_tags, privacy_level, limit=6, replacement='[REDACTED_OSINT_TAG]'))}</p>
                    <p><strong>Location hypotheses:</strong> {html.escape(self._join_redacted(record.osint_location_hypotheses, privacy_level, limit=4, replacement='[REDACTED_LOCATION_HYPOTHESIS]'))}</p>
                    <p><strong>Structured OSINT cards:</strong> {html.escape(self._join_redacted([f"{item.get('title', 'Hypothesis')}: {item.get('strength', 'weak_signal')} ({item.get('confidence', 0)}%)" for item in record.osint_hypothesis_cards[:4]], privacy_level, limit=4, replacement='[REDACTED_OSINT_CARD]'))}</p>
                    <p><strong>OSINT entities:</strong> {html.escape(self._join_redacted([f"{item.get('entity_type', 'entity')}:{item.get('value', '')}" for item in record.osint_entities[:5]], privacy_level, limit=5, replacement='[REDACTED_OSINT_ENTITY]'))}</p>
                    <p><strong>OSINT analyst decisions:</strong> {html.escape(self._join_redacted([f"{item.get('decision', 'needs_review')}: {item.get('analyst_note', '')}" for item in record.osint_analyst_decisions[:4]], privacy_level, limit=4, replacement='[REDACTED_ANALYST_DECISION]'))}</p>
                    <p><strong>OCR region signals:</strong> {html.escape(self._join_redacted([f"{item.get('region', 'region')}:{item.get('weight', 0)}%:{', '.join(item.get('place_hits', [])[:3])}" for item in record.ocr_region_signals[:4]], privacy_level, limit=4, replacement='[REDACTED_OCR_REGION]'))}</p>
                    <p><strong>OSINT privacy/cache:</strong> {html.escape(str(record.osint_privacy_review.get('warning', 'No OSINT privacy review generated.')))} • {html.escape(record.osint_cache_status)}</p>
                    <p><strong>Detected map context:</strong> {html.escape(self._redact_freeform_text(record.detected_map_context, privacy_level, replacement='[REDACTED_LOCATION_CONTEXT]'))}</p>
                    <p><strong>Map intelligence:</strong> {html.escape(record.map_app_detected)} • {html.escape(record.map_type)} • Route {'Detected' if record.route_overlay_detected else 'Not detected'} ({record.route_confidence}%) • Confidence {record.map_intelligence_confidence}%</p>
                    <p><strong>Map evidence basis:</strong> {html.escape(", ".join(record.map_evidence_basis) if record.map_evidence_basis else "Not available")}</p>
                    <p><strong>Place ranking:</strong> {html.escape(self._join_redacted(record.place_candidate_rankings, privacy_level, limit=4, replacement='[REDACTED_LOCATION_RANKING]'))}</p>
                    <p><strong>Candidate city/place:</strong> {html.escape(self._redact_freeform_text(record.candidate_city, privacy_level, replacement='[REDACTED_LOCATION]'))} • {html.escape(self._redact_freeform_text(record.candidate_area, privacy_level, replacement='[REDACTED_LOCATION]'))} • {html.escape(self._join_redacted(record.landmarks_detected, privacy_level, limit=4, replacement='[REDACTED_LOCATION]'))}</p>
                    <p><strong>AI priority:</strong> #{record.ai_priority_rank or '-'} — {html.escape(self._redact_freeform_text(record.ai_executive_note, privacy_level))}</p>
                    <p><strong>Acquisition:</strong> Original path {html.escape(self._safe_path(record.original_file_path, privacy_mode=privacy_mode))} • Working copy {html.escape(self._safe_path(record.working_copy_path, privacy_mode=privacy_mode))} • Imported {html.escape(record.imported_at)}</p>
                    <p><strong>Corroboration checklist:</strong></p>
                    <ul>{''.join(f'<li>{html.escape(lead)}</li>' for lead in self._corroboration_checklist_lines(record, privacy_level))}</ul>
                    <p><strong>AI evidence matrix:</strong></p>
                    <ul>{''.join(f'<li>{html.escape(row)}</li>' for row in self._ai_matrix_lines(record, privacy_level)[:5])}</ul>
                </div>
                """
            )
        osint_privacy = build_osint_privacy_review(records)
        osint_appendix_rows = []
        for record in records:
            if not (record.osint_hypothesis_cards or record.osint_entities or record.place_candidate_rankings):
                continue
            cards = self._join_redacted(
                [f"{item.get('title', 'Hypothesis')} — {item.get('strength', 'weak_signal')} — {item.get('confidence', 0)}%" for item in record.osint_hypothesis_cards[:5]],
                privacy_level,
                limit=5,
                replacement="[REDACTED_OSINT_CARD]",
            )
            entities = self._join_redacted(
                [f"{item.get('entity_type', 'entity')}:{item.get('value', '')}" for item in record.osint_entities[:6]],
                privacy_level,
                limit=6,
                replacement="[REDACTED_OSINT_ENTITY]",
            )
            decisions = self._join_redacted(
                [f"{item.get('decision', 'needs_review')}" for item in record.osint_analyst_decisions[:5]],
                privacy_level,
                limit=5,
                replacement="[REDACTED_ANALYST_DECISION]",
            )
            osint_appendix_rows.append(
                f"<tr><td>{html.escape(record.evidence_id)}</td><td>{html.escape(cards)}</td><td>{html.escape(entities)}</td><td>{html.escape(decisions)}</td></tr>"
            )
        osint_appendix_html = ""
        if osint_appendix_rows:
            osint_appendix_html = (
                '<section class="card">'
                '<h2>Appendix C — OSINT Intelligence Leads</h2>'
                f'<p class="muted">{html.escape(osint_privacy.get("warning", "OSINT privacy review unavailable."))} '
                f'Recommended export mode: {html.escape(str(osint_privacy.get("recommended_export_mode", "redacted_text")))}.</p>'
                '<table><thead><tr><th>Evidence</th><th>Hypotheses</th><th>Entities</th><th>Analyst decisions</th></tr></thead>'
                f'<tbody>{"".join(osint_appendix_rows)}</tbody></table>'
                '</section>'
            )

        custody_source = self._redact_freeform_text(custody_log, privacy_level, replacement="[REDACTED_CUSTODY_LOG]") if custody_log else ""
        custody_html = "<br>".join(html.escape(line) for line in custody_source.splitlines()[:50]) if custody_source else "No custody actions logged."

        if not self._is_strict_redacted(privacy_level):
            self._build_static_map_chart(records)
        chart_blocks = []
        for file_name, title in [
            ("chart_map.png", "Map Intelligence"),
            ("chart_sources.png", "Source Distribution"),
            ("chart_risks.png", "Risk Distribution"),
            ("chart_geo_duplicate.png", "GPS & Duplicate Coverage"),
            ("chart_timeline.png", "Timeline"),
            ("chart_relationships.png", "Evidence Relationship Graph"),
        ]:
            chart_path = self.export_dir / file_name
            if self._is_strict_redacted(privacy_level) and file_name == "chart_map.png":
                continue
            if chart_path.exists():
                chart_blocks.append(f"<div class='chart-card'><h3>{html.escape(title)}</h3><img src='{html.escape(file_name)}' alt='{html.escape(title)}'></div>")
        charts_html = "\n".join(chart_blocks) or "<p class='muted'>No charts were available at report generation time.</p>"

        ai_records = [record for record in records if record.ai_flags]
        if ai_records:
            ai_blocks = []
            for record in sorted(ai_records, key=lambda item: (-item.ai_score_delta, item.evidence_id)):
                ai_blocks.append(
                    f"""
                    <div class='ai-card'>
                        <div class='ai-head'>
                            <strong>{html.escape(record.evidence_id)} — {html.escape(self._safe_file_name(record, privacy_level))}</strong>
                            <span class='ai-delta'>AI +{record.ai_score_delta}</span>
                        </div>
                        <p>{html.escape(self._redact_freeform_text(record.ai_summary, privacy_level))}</p>
                        <p>{html.escape(self._redact_freeform_text(record.ai_executive_note, privacy_level))}</p>
                        <p class='muted'>Provider: {html.escape(record.ai_provider)} • Priority #{record.ai_priority_rank or '-'} • Flags: {html.escape(self._join_redacted(record.ai_flags, privacy_level))}</p>
                        <ul>{''.join(f'<li>{html.escape(item)}</li>' for item in self._corroboration_checklist_lines(record, privacy_level)[:3])}</ul>
                    </div>
                    """
                )
            ai_section_html = "\n".join(ai_blocks)
        else:
            ai_section_html = "<p class='muted'>AI-assisted batch review ran successfully and did not identify cross-evidence outliers in this export.</p>"

        readiness = case_readiness_scores(records)
        privacy_audit = privacy_audit_status(records, privacy_level=privacy_level)
        graph_edges = build_evidence_graph(records)
        contradiction_lines = explain_contradictions(records)
        map_items = [record for record in records if record.map_intelligence_confidence > 0 or record.route_overlay_detected]
        map_lines = []
        for record in sorted(map_items, key=lambda item: (-item.map_intelligence_confidence, item.evidence_id))[:6]:
            route_state = "route detected" if record.route_overlay_detected else "no route overlay"
            city = self._redact_freeform_text(record.candidate_city, privacy_level, replacement="[REDACTED_LOCATION]")
            area = self._redact_freeform_text(record.candidate_area, privacy_level, replacement="[REDACTED_LOCATION]")
            map_lines.append(f"<li>{html.escape(record.evidence_id)}: {html.escape(record.map_app_detected)} • {html.escape(record.map_type)} • {route_state} • confidence {record.map_intelligence_confidence}% • city {html.escape(city)} • area {html.escape(area)}</li>")
        map_html = ''.join(map_lines) or '<li>No map/navigation intelligence detected yet.</li>'
        guardian_html = f"""
            <div class='ai-card'><h3>Case Readiness Score</h3><p><strong>{readiness.get('case_readiness', 0)}%</strong> overall • Timeline {readiness.get('timeline_readiness', 0)}% • Location {readiness.get('location_readiness', 0)}% • Integrity {readiness.get('integrity_readiness', 0)}% • Privacy {readiness.get('privacy_readiness', 0)}% • Courtroom {readiness.get('courtroom_readiness', 0)}%</p><p class='muted'>{html.escape(str(readiness.get('summary', '')))}</p></div>
            <div class='ai-card'><h3>Map Intelligence</h3><ul>{map_html}</ul></div>
            <div class='ai-card'><h3>AI Privacy Auditor</h3><p>{html.escape(str(privacy_audit.get('summary', 'Privacy audit unavailable.'))).replace(chr(10), '<br>')}</p></div>
            <div class='ai-card'><h3>Evidence Graph</h3><ul>{''.join(f'<li>{html.escape(edge.source_id)} ↔ {html.escape(edge.target_id)} [{html.escape(edge.relation)}]: {html.escape(self._redact_text(edge.reason, privacy_level))}</li>' for edge in graph_edges[:8]) or '<li>No relationship edges detected yet.</li>'}</ul></div>
            <div class='ai-card'><h3>Contradiction Explainer</h3><ul>{''.join(f'<li>{html.escape(self._redact_text(item, privacy_level))}</li>' for item in contradiction_lines[:6]) or '<li>No impossible-travel contradiction detected.</li>'}</ul></div>
        """

        html_doc = f"""
        <!doctype html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{APP_NAME} Report</title>
            <style>
                body {{ margin:0; font-family:Segoe UI, Arial, sans-serif; background:#03111d; color:#e8f5ff; padding:28px; }}
                h1, h2, h3 {{ margin:0 0 12px 0; }}
                .hero {{ background:linear-gradient(90deg,#081a2c,#0c2740); border:1px solid #173b60; border-radius:26px; padding:28px; margin-bottom:22px; }}
                p, li {{ line-height:1.7; }}
                .muted {{ color:#93b3cf; font-size:13px; }}
                .metrics {{ display:grid; grid-template-columns:repeat(6, minmax(130px,1fr)); gap:16px; margin-top:22px; }}
                .metric {{ background:#071425; border:1px solid #173c63; border-radius:18px; padding:18px; }}
                .metric .value {{ font-size:32px; font-weight:800; color:#ffffff; }}
                .card {{ background:#081525; border:1px solid #173c63; border-radius:22px; padding:24px; margin-bottom:22px; }}
                .grid-charts {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
                .chart-card {{ background:#06111d; border:1px solid #143553; border-radius:18px; padding:16px; }}
                .chart-card img {{ width:100%; border-radius:14px; border:1px solid #1f496f; background:#030b15; }} .evidence-preview {{ width:100%; margin:10px 0 14px 0; border-radius:14px; border:1px solid #1f496f; background:#030b15; }}
                table {{ width:100%; border-collapse:collapse; overflow:hidden; border-radius:16px; }}
                th, td {{ padding:14px 12px; border-bottom:1px solid #153553; vertical-align:top; text-align:left; }}
                th {{ background:#10243f; color:#84dcff; }}
                tr:nth-child(even) {{ background:#091728; }}
                .risk {{ display:inline-block; padding:4px 10px; border-radius:999px; font-weight:700; }}
                .badge-high {{ background:#351621; color:#ffadbb; border:1px solid #874a5c; }}
                .badge-medium {{ background:#342b14; color:#ffd48b; border:1px solid #7a6331; }}
                .badge-low {{ background:#143124; color:#97efc5; border:1px solid #2f7753; }}
                .detail-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
                .detail-card {{ background:#06111d; border:1px solid #173b60; border-radius:18px; padding:18px; }}
                .pill-row {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:10px; }}
                .pill {{ background:#10243f; border:1px solid #27547f; border-radius:999px; padding:4px 10px; color:#dff5ff; font-size:13px; }}
                .ai-grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:14px; }}
                .ai-card {{ background:linear-gradient(135deg,#071827,#0d2036); border:1px solid #2a608e; border-radius:18px; padding:16px; box-shadow:0 14px 35px rgba(0,0,0,0.22); }}
                .ai-head {{ display:flex; align-items:center; justify-content:space-between; gap:12px; }}
                .ai-delta {{ background:#172f4d; color:#9fe9ff; border:1px solid #36739e; border-radius:999px; padding:4px 10px; font-weight:800; }}
                code {{ font-family:Consolas, monospace; color:#b9f2ff; }}
                .redaction-box {{ border:1px dashed #416983; background:#06111d; color:#b8d6e8; border-radius:14px; padding:14px; margin:10px 0 14px 0; }}
            </style>
        </head>
        <body>
            <section class="hero">
                <h1>{APP_NAME} — Investigation Report</h1>
                <p class="muted">Case: {html.escape(case_id)} | {html.escape(case_name)} | Generated: {generated} | Version: {APP_VERSION} ({APP_BUILD_CHANNEL})</p>\n                <p class="muted">{html.escape(self._privacy_note(privacy_level))}</p>
                <p>This report is structured as executive summary, evidence matrix, OCR/entity findings, forensic appendix, custody review, and courtroom-strength posture.</p>
                <div class="metrics">
                    <div class="metric"><div class="value">{metrics['total']}</div><div>Images</div></div>
                    <div class="metric"><div class="value">{metrics['gps_count']}</div><div>GPS Enabled</div></div>
                    <div class="metric"><div class="value">{metrics['anomaly_count']}</div><div>Review Items</div></div>
                    <div class="metric"><div class="value">{len(metrics['duplicate_groups'])}</div><div>Duplicate Clusters</div></div>
                    <div class="metric"><div class="value">{metrics['avg_score']}</div><div>Average Score</div></div>
                    <div class="metric"><div class="value">{metrics['ai_flagged']}</div><div>AI Flags</div></div>
                    <div class="metric"><div class="value">{sum(1 for r in records if r.courtroom_strength >= 60)}</div><div>Courtroom-Ready</div></div>
                </div>
            </section>

            <section class="card">
                <h2>Executive Summary</h2>
                <p>The current case contains <strong>{metrics['total']}</strong> evidence item(s). <strong>{metrics['gps_count']}</strong> item(s) contain native GPS, <strong>{sum(1 for r in records if r.derived_geo_display != 'Unavailable')}</strong> item(s) expose screenshot-derived geo clues, <strong>{len(metrics['duplicate_groups'])}</strong> duplicate cluster(s) were detected, and the dominant profile is <strong>{html.escape(metrics['dominant_source'])}</strong>.</p>
                <p>Parser/signature alerts: <strong>{metrics['parser_issue_count']}</strong>. Hidden/code alerts: <strong>{metrics['hidden_count']}</strong>. AI-assisted flagged items: <strong>{metrics['ai_flagged']}</strong>. OCR/entity recovery is preserved separately from raw strings so that map labels, usernames, URLs, and visible times remain analyst-friendly.</p>
                <p><strong>Validation:</strong> {html.escape(str(metrics['validation_summary']))}</p>
            </section>

            <section class="card">
                <h2>Operational Dashboards</h2>
                <div class="grid-charts">{charts_html}</div>
            </section>

            <section class="card">
                <h2>AI-Assisted Risk Review</h2>
                <p class="muted">This section summarizes batch-level outlier, timeline/geography, and metadata-authenticity signals. These findings are triage guidance and must be corroborated by the analyst.</p>
                <div class="ai-grid">{ai_section_html}</div>
            </section>

            <section class="card">
                <h2>AI Guardian Command Center</h2>
                <p class="muted">Readiness, relationship graph, contradiction explanations, and privacy posture before export.</p>
                <div class="ai-grid">{guardian_html}</div>
            </section>

            <section class="card">
                <h2>Evidence Matrix</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Evidence ID</th>
                            <th>File</th>
                            <th>Source</th>
                            <th>Time</th>
                            <th>Device</th>
                            <th>GPS</th>
                            <th>Score</th>
                            <th>Confidence</th>
                            <th>Value</th>
                            <th>Courtroom</th>
                            <th>Parser / Signature</th>
                            <th>Risk</th>
                        </tr>
                    </thead>
                    <tbody>{rows}</tbody>
                </table>
            </section>

            {osint_appendix_html}
            <section class="card">
                <h2>Deep Technical Appendix</h2>
                <div class="detail-grid">{''.join(appendix_blocks)}</div>
            </section>

            <section class="card">
                <h2>Corroboration Checklist</h2>
                <ul>{''.join(f"<li><strong>{html.escape(record.evidence_id)}</strong>: {'; '.join(html.escape(item) for item in self._corroboration_checklist_lines(record, privacy_level))}</li>" for record in records)}</ul>
            </section>

            <section class="card">
                <h2>Chain of Custody (Current Case Only)</h2>
                <p><code>{custody_html}</code></p>
            </section>
            <section class="card">
                <h2>Methodology, Limits & Report Identity</h2>
                <p><strong>Workflow:</strong> Acquire → Verify → Extract → Correlate → AI-Assisted Review → Score → Report. Scores combine authenticity, metadata, technical, and conservative AI-batch checks; they do not replace human validation.</p>
                <p><strong>Explainability model:</strong> every reviewed item now carries a primary issue, why-it-matters rationale, GPS verification ladder, and recommended next step so the score is not presented as a blind number.</p>
                <p><strong>Known limits:</strong> Filesystem timestamps may drift after copy/export operations. Missing GPS can be entirely normal for screenshots, graphics, or messaging exports. Parser failures require secondary validation before courtroom reliance.</p>
                <p class="muted">Generated by {APP_NAME} {APP_VERSION} ({APP_BUILD_CHANNEL}) • {APP_COPYRIGHT}</p>
            </section>
        </body>
        </html>
        """
        output.write_text(html_doc, encoding="utf-8")
        return output

    def export_pdf(self, records: List[EvidenceRecord], case_id: str, case_name: str, *, privacy_mode: bool = True, privacy_level: str | None = None) -> Path:
        privacy_level = self._normalize_privacy_level(privacy_mode, privacy_level)
        output = self.export_dir / f"forensic_report_{self._privacy_suffix(privacy_level)}.pdf"
        if self._is_strict_redacted(privacy_level):
            self._clear_report_assets()
        doc = SimpleDocTemplate(str(output), pagesize=A4, leftMargin=28, rightMargin=28, topMargin=28, bottomMargin=28)
        styles = getSampleStyleSheet()
        title = ParagraphStyle("TitleBlue", parent=styles["Title"], textColor=colors.HexColor("#1565c0"), spaceAfter=10)
        heading = ParagraphStyle("HeadingBlue", parent=styles["Heading2"], textColor=colors.HexColor("#1976d2"), spaceAfter=8)
        body = ParagraphStyle("Body", parent=styles["BodyText"], leading=15, spaceAfter=6)
        table_cell = ParagraphStyle("TableCell", parent=styles["BodyText"], fontSize=7.4, leading=8.8, wordWrap="CJK")
        table_header = ParagraphStyle("TableHeader", parent=styles["BodyText"], fontSize=7.8, leading=9.2, textColor=colors.white, fontName="Helvetica-Bold")
        timeline_chart = self.export_dir / "chart_timeline.png"
        map_chart = None if self._is_strict_redacted(privacy_level) else self._build_static_map_chart(records)
        readiness = case_readiness_scores(records)
        privacy_audit = privacy_audit_status(records, privacy_level=privacy_level)
        story = [
            Paragraph(f"{APP_NAME} — Investigation Report", title),
            Paragraph(f"Case: {html.escape(case_id)} — {html.escape(case_name)}", body),
            Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Version: {APP_VERSION} ({APP_BUILD_CHANNEL})", body),
            Paragraph(html.escape(self._privacy_note(privacy_level)), body),
            Spacer(1, 10),
            Paragraph("Executive Summary", heading),
            Paragraph(
                f"Total evidence items: {len(records)}. This PDF mirrors the executive summary, evidence matrix, OCR/entity findings, and courtroom-ready notes used in the HTML report.",
                body,
            ),
            Spacer(1, 8),
            Paragraph("AI Guardian Readiness", heading),
            Paragraph(html.escape(str(readiness.get("summary", "Readiness unavailable."))), body),
            Paragraph(html.escape(str(privacy_audit.get("summary", "Privacy audit unavailable."))).replace(chr(10), " | "), body),
            Spacer(1, 10),
            Paragraph("Evidence Matrix", heading),
        ]
        table_data = [[Paragraph(html.escape(h), table_header) for h in ["ID", "File", "Time", "GPS", "Score", "Risk"]]]
        for record in records:
            table_data.append([
                Paragraph(html.escape(str(record.evidence_id)), table_cell),
                Paragraph(html.escape(self._safe_file_name(record, privacy_level)), table_cell),
                Paragraph(f"{html.escape(str(record.timestamp))}<br/>({record.timestamp_confidence}%)", table_cell),
                Paragraph(f"{html.escape(self._safe_geo_display(record.gps_display, privacy_level))}<br/>({record.gps_confidence}%)", table_cell),
                Paragraph(html.escape(str(record.suspicion_score)), table_cell),
                Paragraph(html.escape(str(record.risk_level)), table_cell),
            ])
        table = Table(table_data, repeatRows=1, colWidths=[48, 170, 112, 96, 42, 46])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#10243f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cedff2")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f8fb")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ])
        )
        story.append(table)
        story.extend([
            Spacer(1, 10),
            Paragraph("Visual Overview", heading),
        ])
        if map_chart is not None and map_chart.exists():
            try:
                story.append(RLImage(str(map_chart), width=470, height=210))
                story.append(Spacer(1, 8))
            except Exception as exc:
                self.logger.warning("Could not embed map chart in courtroom PDF: %s", exc)
        if timeline_chart.exists():
            try:
                story.append(RLImage(str(timeline_chart), width=470, height=210))
                story.append(Spacer(1, 8))
            except Exception as exc:
                self.logger.warning("Could not embed timeline chart or evidence preview in courtroom PDF: %s", exc)
        story.extend([
            Paragraph("Validation, Methodology & Limits", heading),
            Paragraph("Workflow: Acquire → Verify → Extract → Correlate → AI-Assisted Review → Score → Report. Scores are triage aids and must be confirmed with analyst review.", body),
            Paragraph(f"Validation posture: parser-clean {sum(1 for r in records if r.parser_status == 'Valid')}/{len(records)} • courtroom-ready {sum(1 for r in records if r.courtroom_strength >= 60)}/{len(records)} • native GPS {sum(1 for r in records if r.gps_confidence >= 80)}/{len(records)} • AI-assisted flags {sum(1 for r in records if r.ai_flags)}/{len(records)}.", body),
            Paragraph("Limits: filesystem times can drift, missing GPS may be normal for exports/screenshots, AI flags are batch triage signals, and parser failures require secondary validation.", body),
            Paragraph(f"Build identity: {APP_NAME} {APP_VERSION} ({APP_BUILD_CHANNEL})", body),
            PageBreak(),
            Paragraph("Deep Technical Appendix", heading),
        ])
        for record in records:
            preview_asset = None if self._is_strict_redacted(privacy_level) else self._prepare_preview_asset(record, max_size=(720, 420))
            story.extend([
                Paragraph(f"{record.evidence_id} — {self._safe_file_name(record, privacy_level)}", styles["Heading3"]),
                Paragraph(
                    f"Risk {record.risk_level} / Score {record.suspicion_score} / Confidence {record.confidence_score}% / Value {record.evidentiary_value}% / Courtroom {record.courtroom_strength}% / Parser {record.parser_status} / Signature {record.signature_status}",
                    body,
                ),
            ])
            if self._is_strict_redacted(privacy_level):
                story.append(Paragraph("Evidence preview omitted in shareable/courtroom-redacted export. Generate an Internal Full report to include raw previews.", body))
                story.append(Spacer(1, 6))
            elif preview_asset is not None and preview_asset.exists():
                try:
                    story.append(RLImage(str(preview_asset), width=180, height=110))
                    story.append(Spacer(1, 6))
                except Exception as exc:
                    self.logger.warning("Could not embed evidence preview in courtroom PDF for %s: %s", record.evidence_id, exc)
            story.extend([
                Paragraph(f"Primary issue: {html.escape(self._redact_freeform_text(record.score_primary_issue, privacy_level))}", body),
                Paragraph(f"AI-assisted review: {html.escape(self._redact_freeform_text(record.ai_summary, privacy_level))}", body),
                Paragraph(f"AI priority: #{record.ai_priority_rank or '-'} — {html.escape(self._redact_freeform_text(record.ai_executive_note, privacy_level))}", body),
                Paragraph(f"Why it matters: {html.escape(self._redact_freeform_text(record.score_reason, privacy_level))}", body),
                Paragraph(f"Next step: {html.escape(self._redact_freeform_text(record.score_next_step, privacy_level))}", body),
                Paragraph(html.escape(self._redact_freeform_text(record.courtroom_notes, privacy_level)), body),
                Paragraph("Corroboration checklist: " + html.escape(" | ".join(self._corroboration_checklist_lines(record, privacy_level))), body),
                Spacer(1, 8),
            ])

        def add_footer(canvas, doc):
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.HexColor("#547799"))
            canvas.drawString(doc.leftMargin, 18, f"{APP_NAME} {APP_VERSION} • {APP_BUILD_CHANNEL}")
            canvas.drawRightString(A4[0] - doc.rightMargin, 18, APP_COPYRIGHT)
            canvas.restoreState()

        doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
        return output
