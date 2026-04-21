from __future__ import annotations

import csv
import html
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image as RLImage, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .anomalies import parse_timestamp
from .models import EvidenceRecord
from app.config import APP_COPYRIGHT, APP_NAME, APP_VERSION, APP_BUILD_CHANNEL
from PIL import Image, ImageSequence


class ReportService:
    def __init__(self, export_dir: Path) -> None:
        self.export_dir = export_dir
        self.export_dir.mkdir(parents=True, exist_ok=True)

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
        except Exception:
            return None

    def _corroboration_checklist_lines(self, record: EvidenceRecord) -> list[str]:
        lines = [f"Preserve original path and hashes for {record.evidence_id} before sharing or re-exporting."]
        lines.append(f"Validate the selected time anchor ({record.timestamp_source}) against uploads, chats, logs, or witness accounts.")
        if record.has_gps:
            lines.append(f"Verify native GPS coordinates externally around {record.gps_display} before making courtroom location claims.")
        elif record.derived_geo_display != "Unavailable":
            lines.append(f"Treat derived geo ({record.derived_geo_display}) as contextual only until browser/app history confirms it.")
        else:
            lines.append("Use timeline, source profile, and surrounding case context because no GPS anchor was recovered.")
        if record.visible_text_excerpt:
            lines.append("Cross-check OCR clues with the source application, browser history, or visible conversation context.")
        return lines[:4]

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
        hidden_count = sum(1 for record in records if record.hidden_code_indicators)
        return {
            "total": total,
            "gps_count": gps_count,
            "anomaly_count": anomaly_count,
            "duplicate_groups": duplicate_groups,
            "avg_score": avg_score,
            "dominant_source": dominant_source,
            "parser_issue_count": parser_issue_count,
            "hidden_count": hidden_count,
        }

    def export_csv(self, records: Iterable[EvidenceRecord]) -> Path:
        output = self.export_dir / "evidence_summary.csv"
        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "Case ID",
                    "Evidence ID",
                    "File Name",
                    "Source Type",
                    "Timestamp",
                    "Timestamp Source",
                    "Timestamp Confidence",
                    "Device",
                    "GPS",
                    "GPS Confidence",
                    "Score",
                    "Confidence",
                    "Evidentiary Value",
                    "Risk",
                    "Integrity",
                    "SHA-256",
                ]
            )
            for record in records:
                writer.writerow(
                    [
                        record.case_id,
                        record.evidence_id,
                        record.file_name,
                        record.source_type,
                        record.timestamp,
                        record.timestamp_source,
                        record.timestamp_confidence,
                        record.device_model,
                        record.gps_display,
                        record.gps_confidence,
                        record.suspicion_score,
                        record.confidence_score,
                        record.evidentiary_value,
                        record.courtroom_strength,
                        record.risk_level,
                        record.integrity_status,
                        record.sha256,
                    ]
                )
        return output

    def export_json(self, records: Iterable[EvidenceRecord]) -> Path:
        output = self.export_dir / "evidence_summary.json"
        payload = []
        for record in records:
            payload.append(
                {
                    "case_id": record.case_id,
                    "case_name": record.case_name,
                    "evidence_id": record.evidence_id,
                    "file_name": record.file_name,
                    "file_path": str(record.file_path),
                    "source_type": record.source_type,
                    "source_profile_confidence": record.source_profile_confidence,
                    "environment_profile": record.environment_profile,
                    "app_detected": record.app_detected,
                    "scene_group": record.scene_group,
                    "similarity_score": record.similarity_score,
                    "similarity_note": record.similarity_note,
                    "timestamp": record.timestamp,
                    "timestamp_source": record.timestamp_source,
                    "timestamp_confidence": record.timestamp_confidence,
                    "timestamp_verdict": record.timestamp_verdict,
                    "device_model": record.device_model,
                    "software": record.software,
                    "format": record.format_name,
                    "signature_status": record.signature_status,
                    "format_trust": record.format_trust,
                    "dimensions": record.dimensions,
                    "gps": {
                        "display": record.gps_display,
                        "latitude": record.gps_latitude,
                        "longitude": record.gps_longitude,
                        "altitude": record.gps_altitude,
                        "source": record.gps_source,
                        "confidence": record.gps_confidence,
                        "verification": record.gps_verification,
                        "derived": {
                            "display": record.derived_geo_display,
                            "latitude": record.derived_latitude,
                            "longitude": record.derived_longitude,
                            "source": record.derived_geo_source,
                            "confidence": record.derived_geo_confidence,
                            "note": record.derived_geo_note,
                        },
                        "status": record.geo_status,
                    },
                    "anomaly_reasons": record.anomaly_reasons,
                    "anomaly_contributors": record.anomaly_contributors,
                    "osint_leads": record.osint_leads,
                    "analyst_verdict": record.analyst_verdict,
                    "courtroom_notes": record.courtroom_notes,
                    "hidden": {
                        "summary": record.hidden_code_summary,
                        "overview": record.hidden_content_overview,
                        "context_summary": record.hidden_context_summary,
                        "types": record.hidden_finding_types,
                        "indicators": record.hidden_code_indicators,
                        "suspicious_embeds": record.hidden_suspicious_embeds,
                        "payload_markers": record.hidden_payload_markers,
                        "readable_strings": record.extracted_strings,
                        "urls": record.urls_found,
                        "stego_suspicion": record.stego_suspicion,
                    },
                    "visible_text": {
                        "excerpt": record.visible_text_excerpt,
                        "lines": record.visible_text_lines,
                        "urls": record.visible_urls,
                        "times": record.visible_time_strings,
                        "locations": record.visible_location_strings,
                    },
                    "time_candidates": record.time_candidates,
                    "time_conflicts": record.time_conflicts,
                    "integrity_note": record.integrity_note,
                    "exif_warning": record.exif_warning,
                    "created_time_note": record.created_time_note,
                    "suspicion_score": record.suspicion_score,
                    "confidence_score": record.confidence_score,
                    "evidentiary_value": record.evidentiary_value,
                    "evidentiary_label": record.evidentiary_label,
                    "courtroom_strength": record.courtroom_strength,
                    "courtroom_label": record.courtroom_label,
                    "risk_level": record.risk_level,
                    "tags": record.tags,
                    "bookmarked": record.bookmarked,
                    "sha256": record.sha256,
                    "md5": record.md5,
                    "perceptual_hash": record.perceptual_hash,
                }
            )
        output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return output

    def export_executive_summary(self, records: List[EvidenceRecord], case_id: str, case_name: str) -> Path:
        output = self.export_dir / "executive_summary.txt"
        metrics = self._case_metrics(records)
        lines = [
            f"{APP_NAME} — Executive Summary",
            f"Case ID: {case_id}",
            f"Case Name: {case_name}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Version: {APP_VERSION} ({APP_BUILD_CHANNEL})",
            "",
            f"Total evidence items: {metrics['total']}",
            f"Native GPS items: {metrics['gps_count']}",
            f"Derived geo clues: {sum(1 for r in records if r.derived_geo_display != 'Unavailable')}",
            f"Review items (non-low risk): {metrics['anomaly_count']}",
            f"Parser/signature issues: {metrics['parser_issue_count']}",
            f"Hidden/code hits: {metrics['hidden_count']}",
            f"Duplicate clusters: {len(metrics['duplicate_groups'])}",
            f"Average suspicion score: {metrics['avg_score']}",
            f"Dominant source profile: {metrics['dominant_source']}",
            "",
            "Top priority evidence:",
        ]
        for record in sorted(records, key=lambda r: (-r.evidentiary_value, -r.suspicion_score, -r.confidence_score, r.evidence_id))[:5]:
            lines.extend(
                [
                    f"- {record.evidence_id} | {record.file_name} | {record.risk_level} | Score {record.suspicion_score} | Confidence {record.confidence_score}% | Value {record.evidentiary_value}% | Courtroom {record.courtroom_strength}%",
                    f"  Time: {record.timestamp} ({record.timestamp_source}, {record.timestamp_confidence}%)",
                    f"  GPS: {record.gps_display} ({record.gps_confidence}%) | Derived: {record.derived_geo_display} ({record.derived_geo_confidence}%)",
                    f"  Why it matters: {record.analyst_verdict}",
                ]
            )
        output.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        return output

    def export_validation_summary(self, records: List[EvidenceRecord], case_id: str, case_name: str) -> Path:
        output = self.export_dir / "validation_summary.txt"
        total = len(records)
        parser_valid = sum(1 for record in records if record.parser_status == "Valid")
        native_time = sum(1 for record in records if record.timestamp_confidence >= 80)
        native_gps = sum(1 for record in records if record.gps_confidence >= 80)
        hidden_hits = sum(1 for record in records if record.hidden_code_indicators)
        lines = [
            f"{APP_NAME} — Validation Summary",
            f"Case ID: {case_id}",
            f"Case Name: {case_name}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"Evidence count: {total}",
            f"Parser-success count: {parser_valid}/{total}",
            f"Strong time anchors: {native_time}/{total}",
            f"Strong GPS anchors: {native_gps}/{total}",
            f"Derived geo clues: {sum(1 for record in records if record.derived_geo_display != 'Unavailable')}",
            f"Hidden/code detections: {hidden_hits}",
            f"Courtroom-ready posture (>=60%): {sum(1 for record in records if record.courtroom_strength >= 60)}/{total}",
            "",
            "Interpretation:",
            "- Strong time anchors = Native EXIF Original or equivalent embedded source.",
            "- Strong GPS anchors = valid native GPS coordinates recovered from EXIF tags.",
            "- Derived geo clues = location leads parsed from visible screenshot/browser/map content rather than native EXIF.",
            "- Parser-success count = files rendered successfully by Pillow in the current workflow.",
            "- Hidden/code detections are heuristic findings and still require analyst review.",
        ]
        output.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        return output

    def export_package_manifest(self, payload: dict) -> Path:
        output = self.export_dir / "export_manifest.json"
        output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return output

    def export_courtroom_summary(self, records: List[EvidenceRecord], case_id: str, case_name: str) -> Path:
        output = self.export_dir / "courtroom_summary.txt"
        metrics = self._case_metrics(records)
        ordered = sorted(records, key=lambda r: (-r.suspicion_score, r.evidence_id))
        lines = [
            f"{APP_NAME} — Courtroom Summary",
            f"Case ID: {case_id}",
            f"Case Name: {case_name}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Version: {APP_VERSION} ({APP_BUILD_CHANNEL})",
            "",
            "Executive Summary",
            "-----------------",
            f"Total evidence items: {metrics['total']}",
            f"High-risk items: {sum(1 for r in records if r.risk_level == 'High')}",
            f"GPS-bearing items: {metrics['gps_count']}",
            f"Duplicate clusters: {len(metrics['duplicate_groups'])}",
            "",
            "Courtroom Readiness",
            "-------------------",
        ]
        for record in ordered[:5]:
            lines.extend(
                [
                    f"{record.evidence_id} | {record.file_name} | {record.risk_level} | Score {record.suspicion_score} | Value {record.evidentiary_value}% | Courtroom {record.courtroom_strength}%",
                    f"  Time: {record.timestamp} ({record.timestamp_source}, {record.timestamp_confidence}%)",
                    f"  GPS: {record.gps_display} ({record.gps_confidence}%) | Derived: {record.derived_geo_display} ({record.derived_geo_confidence}%)",
                    f"  Parser: {record.parser_status} | Signature: {record.signature_status} | Trust: {record.format_trust}",
                    f"  Analyst verdict: {record.analyst_verdict}",
                    f"  Courtroom note: {record.courtroom_notes}",
                    "",
                ]
            )
        output.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        return output

    def export_html(self, records: List[EvidenceRecord], case_id: str, case_name: str, custody_log: str = "") -> Path:
        output = self.export_dir / "forensic_report.html"
        metrics = self._case_metrics(records)
        generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        def badge_class(level: str) -> str:
            return {"High": "badge-high", "Medium": "badge-medium"}.get(level, "badge-low")

        rows = "\n".join(
            f"""
            <tr>
                <td>{html.escape(record.evidence_id)}</td>
                <td><strong>{html.escape(record.file_name)}</strong><br><span class='muted'>{html.escape(str(record.file_path))}</span></td>
                <td>{html.escape(record.source_type)}</td>
                <td>{html.escape(record.timestamp)}<br><span class='muted'>{html.escape(record.timestamp_source)} • {record.timestamp_confidence}%</span></td>
                <td>{html.escape(record.device_model)}</td>
                <td>{html.escape(record.gps_display)}<br><span class='muted'>Native {record.gps_confidence}% • Derived {record.derived_geo_confidence}%</span><br><span class='muted'>{html.escape(record.derived_geo_display)}</span></td>
                <td>{record.suspicion_score}</td>
                <td>{record.confidence_score}%</td>
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
            preview_asset = self._prepare_preview_asset(record)
            preview_html = ""
            if preview_asset is not None:
                rel_preview = preview_asset.relative_to(self.export_dir).as_posix()
                preview_html = f"<img class='evidence-preview' src='{html.escape(rel_preview)}' alt='{html.escape(record.file_name)} preview'>"
            appendix_blocks.append(
                f"""
                <div class="detail-card">
                    <h3>{html.escape(record.evidence_id)} — {html.escape(record.file_name)}</h3>
                    {preview_html}
                    <div class="pill-row">
                        <span class="pill">{html.escape(record.source_type)}</span>
                        <span class="pill">{html.escape(record.timestamp_source)} • {record.timestamp_confidence}%</span>
                        <span class="pill">Native GPS {html.escape(record.gps_display)} • {record.gps_confidence}%</span>
                        <span class="pill">Derived Geo {html.escape(record.derived_geo_display)} • {record.derived_geo_confidence}%</span>
                        <span class="pill">Signature {html.escape(record.signature_status)}</span>
                        <span class="pill">Trust {html.escape(record.format_trust)}</span>
                        <span class="pill">Score {record.suspicion_score}</span>
                        <span class="pill">Value {record.evidentiary_value}%</span>
                        <span class="pill">Courtroom {record.courtroom_strength}%</span>
                    </div>
                    <p><strong>Why this matters:</strong> {html.escape(record.analyst_verdict)}</p>
                    <p><strong>Courtroom note:</strong> {html.escape(record.courtroom_notes)}</p>
                    <p><strong>GPS verification:</strong> {html.escape(record.gps_verification)}</p>
                    <p><strong>Derived geo:</strong> {html.escape(record.derived_geo_note)}</p>
                    <p><strong>Hidden/content summary:</strong> {html.escape(record.hidden_code_summary)}</p>
                    <p><strong>Corroboration checklist:</strong></p>
                    <ul>{''.join(f'<li>{html.escape(lead)}</li>' for lead in self._corroboration_checklist_lines(record))}</ul>
                </div>
                """
            )
        custody_html = "<br>".join(html.escape(line) for line in custody_log.splitlines()[:50]) if custody_log else "No custody actions logged."

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
            if chart_path.exists():
                chart_blocks.append(f"<div class='chart-card'><h3>{html.escape(title)}</h3><img src='{html.escape(file_name)}' alt='{html.escape(title)}'></div>")
        charts_html = "\n".join(chart_blocks) or "<p class='muted'>No charts were available at report generation time.</p>"

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
                code {{ font-family:Consolas, monospace; color:#b9f2ff; }}
            </style>
        </head>
        <body>
            <section class="hero">
                <h1>{APP_NAME} — Investigation Report</h1>
                <p class="muted">Case: {html.escape(case_id)} | {html.escape(case_name)} | Generated: {generated} | Version: {APP_VERSION} ({APP_BUILD_CHANNEL})</p>
                <p>This report is structured as executive summary, evidence matrix, forensic appendix, custody review, and courtroom-strength posture.</p>
                <div class="metrics">
                    <div class="metric"><div class="value">{metrics['total']}</div><div>Images</div></div>
                    <div class="metric"><div class="value">{metrics['gps_count']}</div><div>GPS Enabled</div></div>
                    <div class="metric"><div class="value">{metrics['anomaly_count']}</div><div>Review Items</div></div>
                    <div class="metric"><div class="value">{len(metrics['duplicate_groups'])}</div><div>Duplicate Clusters</div></div>
                    <div class="metric"><div class="value">{metrics['avg_score']}</div><div>Average Score</div></div>
                    <div class="metric"><div class="value">{sum(1 for r in records if r.courtroom_strength >= 60)}</div><div>Courtroom-Ready</div></div>
                </div>
            </section>

            <section class="card">
                <h2>Executive Summary</h2>
                <p>The current case contains <strong>{metrics['total']}</strong> evidence item(s). <strong>{metrics['gps_count']}</strong> item(s) contain native GPS, <strong>{sum(1 for r in records if r.derived_geo_display != 'Unavailable')}</strong> item(s) expose screenshot-derived geo clues, <strong>{len(metrics['duplicate_groups'])}</strong> duplicate cluster(s) were detected, and the dominant profile is <strong>{html.escape(metrics['dominant_source'])}</strong>.</p>
                <p>Parser/signature alerts: <strong>{metrics['parser_issue_count']}</strong>. Hidden/code alerts: <strong>{metrics['hidden_count']}</strong>. Readable strings without code markers are preserved for context but are not counted as hidden-code alerts.</p>
            </section>

            <section class="card">
                <h2>Operational Dashboards</h2>
                <div class="grid-charts">{charts_html}</div>
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

            <section class="card">
                <h2>Deep Technical Appendix</h2>
                <div class="detail-grid">{''.join(appendix_blocks)}</div>
            </section>

            <section class="card">
                <h2>Corroboration Checklist</h2>
                <ul>{''.join(f"<li><strong>{html.escape(record.evidence_id)}</strong>: {'; '.join(html.escape(item) for item in self._corroboration_checklist_lines(record))}</li>" for record in records)}</ul>
            </section>

            <section class="card">
                <h2>Chain of Custody (Current Case Only)</h2>
                <p><code>{custody_html}</code></p>
            </section>
            <section class="card">
                <h2>Methodology, Limits & Report Identity</h2>
                <p><strong>Workflow:</strong> Acquire → Verify → Extract → Correlate → Score → Report. Scores combine authenticity, metadata, and technical checks; they do not replace human validation.</p>
                <p><strong>Known limits:</strong> Filesystem timestamps may drift after copy/export operations. Missing GPS can be entirely normal for screenshots, graphics, or messaging exports. Parser failures require secondary validation before courtroom reliance.</p>
                <p class="muted">Generated by {APP_NAME} {APP_VERSION} ({APP_BUILD_CHANNEL}) • {APP_COPYRIGHT}</p>
            </section>
        </body>
        </html>
        """
        output.write_text(html_doc, encoding="utf-8")
        return output

    def export_pdf(self, records: List[EvidenceRecord], case_id: str, case_name: str) -> Path:
        output = self.export_dir / "forensic_report.pdf"
        doc = SimpleDocTemplate(str(output), pagesize=A4, leftMargin=28, rightMargin=28, topMargin=28, bottomMargin=28)
        styles = getSampleStyleSheet()
        title = ParagraphStyle("TitleBlue", parent=styles["Title"], textColor=colors.HexColor("#1565c0"), spaceAfter=10)
        heading = ParagraphStyle("HeadingBlue", parent=styles["Heading2"], textColor=colors.HexColor("#1976d2"), spaceAfter=8)
        body = ParagraphStyle("Body", parent=styles["BodyText"], leading=15, spaceAfter=6)
        timeline_chart = self.export_dir / "chart_timeline.png"
        map_chart = self._build_static_map_chart(records)
        story = [
            Paragraph(f"{APP_NAME} — Investigation Report", title),
            Paragraph(f"Case: {html.escape(case_id)} — {html.escape(case_name)}", body),
            Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Version: {APP_VERSION} ({APP_BUILD_CHANNEL})", body),
            Spacer(1, 10),
            Paragraph("Executive Summary", heading),
            Paragraph(
                f"Total evidence items: {len(records)}. This PDF mirrors the executive summary, evidence matrix, and courtroom-ready notes used in the HTML report.",
                body,
            ),
            Spacer(1, 10),
            Paragraph("Evidence Matrix", heading),
        ]
        table_data = [["ID", "File", "Time", "GPS", "Score", "Risk"]]
        for record in records:
            table_data.append([
                record.evidence_id,
                record.file_name,
                f"{record.timestamp} ({record.timestamp_confidence}%)",
                f"{record.gps_display} ({record.gps_confidence}%)",
                str(record.suspicion_score),
                record.risk_level,
            ])
        table = Table(table_data, repeatRows=1, colWidths=[52, 140, 115, 90, 48, 48])
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
            except Exception:
                pass
        if timeline_chart.exists():
            try:
                story.append(RLImage(str(timeline_chart), width=470, height=210))
                story.append(Spacer(1, 8))
            except Exception:
                pass
        story.extend([
            Paragraph("Validation, Methodology & Limits", heading),
            Paragraph("Workflow: Acquire → Verify → Extract → Correlate → Score → Report. Scores are triage aids and must be confirmed with analyst review.", body),
            Paragraph(f"Validation posture: parser-clean {sum(1 for r in records if r.parser_status == 'Valid')}/{len(records)} • courtroom-ready {sum(1 for r in records if r.courtroom_strength >= 60)}/{len(records)} • native GPS {sum(1 for r in records if r.gps_confidence >= 80)}/{len(records)}.", body),
            Paragraph("Limits: filesystem times can drift, missing GPS may be normal for exports/screenshots, and parser failures require secondary validation.", body),
            Paragraph(f"Build identity: {APP_NAME} {APP_VERSION} ({APP_BUILD_CHANNEL})", body),
            PageBreak(),
            Paragraph("Deep Technical Appendix", heading),
        ])
        for record in records:
            preview_asset = self._prepare_preview_asset(record, max_size=(720, 420))
            story.extend([
                Paragraph(f"{record.evidence_id} — {record.file_name}", styles["Heading3"]),
                Paragraph(
                    f"Risk {record.risk_level} / Score {record.suspicion_score} / Confidence {record.confidence_score}% / Value {record.evidentiary_value}% / Courtroom {record.courtroom_strength}% / Parser {record.parser_status} / Signature {record.signature_status}",
                    body,
                ),
            ])
            if preview_asset is not None and preview_asset.exists():
                try:
                    story.append(RLImage(str(preview_asset), width=180, height=110))
                    story.append(Spacer(1, 6))
                except Exception:
                    pass
            story.extend([
                Paragraph(html.escape(record.analyst_verdict), body),
                Paragraph(html.escape(record.courtroom_notes), body),
                Paragraph("Corroboration checklist: " + html.escape(" | ".join(self._corroboration_checklist_lines(record))), body),
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
