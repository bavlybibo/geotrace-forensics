from __future__ import annotations

import csv
import html
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import EvidenceRecord


class ReportService:
    def __init__(self, export_dir: Path) -> None:
        self.export_dir = export_dir
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_csv(self, records: Iterable[EvidenceRecord]) -> Path:
        output = self.export_dir / "evidence_summary.csv"
        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "Evidence ID",
                    "File Name",
                    "Source Type",
                    "Timestamp",
                    "Timestamp Source",
                    "Device",
                    "GPS",
                    "Score",
                    "Confidence",
                    "Risk",
                    "Integrity",
                    "SHA-256",
                ]
            )
            for record in records:
                writer.writerow(
                    [
                        record.evidence_id,
                        record.file_name,
                        record.source_type,
                        record.timestamp,
                        record.timestamp_source,
                        record.device_model,
                        record.gps_display,
                        record.suspicion_score,
                        record.confidence_score,
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
                    "evidence_id": record.evidence_id,
                    "file_name": record.file_name,
                    "file_path": str(record.file_path),
                    "source_type": record.source_type,
                    "timestamp": record.timestamp,
                    "timestamp_source": record.timestamp_source,
                    "device_model": record.device_model,
                    "software": record.software,
                    "format": record.format_name,
                    "dimensions": record.dimensions,
                    "orientation": record.orientation,
                    "gps": {
                        "display": record.gps_display,
                        "latitude": record.gps_latitude,
                        "longitude": record.gps_longitude,
                        "altitude": record.gps_altitude,
                    },
                    "anomaly_reasons": record.anomaly_reasons,
                    "osint_leads": record.osint_leads,
                    "suspicion_score": record.suspicion_score,
                    "confidence_score": record.confidence_score,
                    "risk_level": record.risk_level,
                    "sha256": record.sha256,
                    "md5": record.md5,
                    "perceptual_hash": record.perceptual_hash,
                }
            )
        output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return output

    def export_html(self, records: List[EvidenceRecord], case_name: str, custody_log: str = "") -> Path:
        output = self.export_dir / "forensic_report.html"
        total = len(records)
        gps_count = sum(1 for record in records if record.has_gps)
        anomaly_count = sum(1 for record in records if record.risk_level != "Low")
        device_count = len({record.device_model for record in records if record.device_model not in {"Unknown", ""}})
        duplicate_groups = sorted({record.duplicate_group for record in records if record.duplicate_group})
        screenshots = sum(1 for record in records if "Screenshot" in record.source_type or "Messaging" in record.source_type)

        def badge_class(level: str) -> str:
            return {"High": "badge-high", "Medium": "badge-medium"}.get(level, "badge-low")

        rows = "\n".join(
            f"""
            <tr>
                <td>{html.escape(record.evidence_id)}</td>
                <td>{html.escape(record.file_name)}</td>
                <td>{html.escape(record.source_type)}</td>
                <td>{html.escape(record.timestamp)}<br><span class='muted'>{html.escape(record.timestamp_source)}</span></td>
                <td>{html.escape(record.device_model)}</td>
                <td>{html.escape(record.gps_display)}</td>
                <td>{record.suspicion_score}</td>
                <td>{record.confidence_score}</td>
                <td><span class="risk {badge_class(record.risk_level)}">{html.escape(record.risk_level)}</span></td>
                <td>{html.escape('; '.join(record.anomaly_reasons))}</td>
            </tr>
            """
            for record in records
        )

        lead_blocks = "\n".join(
            f"""
            <div class="card small">
                <h3>{html.escape(record.evidence_id)} — {html.escape(record.file_name)}</h3>
                <ul>{''.join(f'<li>{html.escape(lead)}</li>' for lead in record.osint_leads)}</ul>
            </div>
            """
            for record in records[:8]
        )

        custody_html = "<br>".join(html.escape(line) for line in custody_log.splitlines()[:20]) if custody_log else "No custody actions logged."

        html_doc = f"""
        <!doctype html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>GeoTrace Forensics Report</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background:#06101b; color:#eef8ff; margin:0; padding:32px; }}
                .card {{ background:#0b1930; border:1px solid #183c63; border-radius:22px; padding:24px; margin-bottom:22px; box-shadow: 0 12px 26px rgba(0,0,0,.18); }}
                .small {{ padding:18px 20px; }}
                h1,h2,h3 {{ color:#7edcff; margin-top:0; }}
                p, li {{ line-height:1.55; }}
                .muted {{ color:#93b3cf; font-size: 13px; }}
                .metrics {{ display:grid; grid-template-columns:repeat(6, minmax(120px,1fr)); gap:16px; margin-top:20px; }}
                .metric {{ background:#071425; border:1px solid #173c63; border-radius:18px; padding:18px; }}
                .metric .value {{ font-size:32px; font-weight:800; color:#ffffff; }}
                table {{ width:100%; border-collapse:collapse; overflow:hidden; border-radius:16px; }}
                th, td {{ padding:14px 12px; border-bottom:1px solid #153553; vertical-align:top; text-align:left; }}
                th {{ background:#10243f; color:#84dcff; }}
                tr:nth-child(even) {{ background:#091728; }}
                .risk {{ display:inline-block; padding:4px 10px; border-radius:999px; font-weight:700; }}
                .badge-high {{ background:#351621; color:#ffadbb; border:1px solid #874a5c; }}
                .badge-medium {{ background:#342b14; color:#ffd48b; border:1px solid #7a6331; }}
                .badge-low {{ background:#143124; color:#97efc5; border:1px solid #2f7753; }}
                .grid-two {{ display:grid; grid-template-columns:1.2fr .8fr; gap:20px; }}
                code {{ font-family:Consolas, monospace; color:#b9f2ff; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>GeoTrace Forensics X — Investigation Report</h1>
                <p class="muted">Case: {html.escape(case_name)} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <div class="metrics">
                    <div class="metric"><div class="value">{total}</div><div>Images</div></div>
                    <div class="metric"><div class="value">{gps_count}</div><div>GPS Enabled</div></div>
                    <div class="metric"><div class="value">{anomaly_count}</div><div>Potential Anomalies</div></div>
                    <div class="metric"><div class="value">{device_count}</div><div>Known Devices</div></div>
                    <div class="metric"><div class="value">{len(duplicate_groups)}</div><div>Duplicate Clusters</div></div>
                    <div class="metric"><div class="value">{screenshots}</div><div>Screenshots/Exports</div></div>
                </div>
            </div>
            <div class="grid-two">
                <div class="card">
                    <h2>Executive Summary</h2>
                    <p>The platform analyzed uploaded image evidence, preserved cryptographic integrity using SHA-256 and MD5 hashes, extracted available EXIF data, recovered timestamps from embedded tags and filename patterns, evaluated GPS availability, profiled the likely source type, and generated investigative leads for manual follow-up.</p>
                    <p>Methodology used: <strong>Acquire → Verify → Extract → Correlate → Score → Report</strong>.</p>
                </div>
                <div class="card">
                    <h2>Methodology Highlights</h2>
                    <ul>
                        <li>Hashing on import for evidence integrity.</li>
                        <li>Metadata extraction across camera, software, and authoring tags.</li>
                        <li>Timestamp recovery with fallback hierarchy.</li>
                        <li>Near-duplicate visual fingerprint clustering.</li>
                        <li>Context-aware anomaly scoring to reduce false positives on screenshots and exports.</li>
                    </ul>
                </div>
            </div>
            <div class="card">
                <h2>Evidence Findings</h2>
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
                            <th>Risk</th>
                            <th>Investigation Notes</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows}
                    </tbody>
                </table>
            </div>
            <div class="card">
                <h2>OSINT / Investigation Leads</h2>
                {lead_blocks}
            </div>
            <div class="card">
                <h2>Chain of Custody (Excerpt)</h2>
                <p><code>{custody_html}</code></p>
            </div>
        </body>
        </html>
        """
        output.write_text(html_doc, encoding="utf-8")
        return output

    def export_pdf(self, records: List[EvidenceRecord], case_name: str) -> Path:
        output = self.export_dir / "forensic_report.pdf"
        doc = SimpleDocTemplate(str(output), pagesize=A4, title="GeoTrace Forensics Report")
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TitleCyber",
            parent=styles["Heading1"],
            textColor=colors.HexColor("#0c4c8a"),
            fontSize=20,
            leading=24,
        )
        heading = ParagraphStyle("Section", parent=styles["Heading2"], textColor=colors.HexColor("#0d558f"))
        normal = styles["BodyText"]

        story = [
            Paragraph("GeoTrace Forensics X — Investigation Report", title_style),
            Spacer(1, 10),
            Paragraph(f"Case: {case_name}", normal),
            Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal),
            Spacer(1, 14),
            Paragraph("Executive Summary", heading),
            Paragraph(
                "This report summarizes image-evidence integrity hashing, metadata extraction, timestamp recovery, source profiling, duplicate fingerprinting, and anomaly scoring for the supplied investigation package.",
                normal,
            ),
            Spacer(1, 10),
            Paragraph("Methodology", heading),
            Paragraph("Acquire → Verify → Extract → Correlate → Score → Report", normal),
            Spacer(1, 12),
        ]

        table_data = [["ID", "File", "Source", "Time", "GPS", "Score", "Risk"]]
        for record in records:
            table_data.append(
                [
                    record.evidence_id,
                    record.file_name[:28],
                    record.source_type,
                    record.timestamp,
                    record.gps_display,
                    str(record.suspicion_score),
                    record.risk_level,
                ]
            )

        table = Table(table_data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0c4c8a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#b6c6d8")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f7fbff")),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 14))
        story.append(Paragraph("Top Investigation Leads", heading))
        for record in records[:6]:
            story.append(Paragraph(f"<b>{record.evidence_id} — {record.file_name}</b>", normal))
            for lead in record.osint_leads[:3]:
                story.append(Paragraph(f"• {lead}", normal))
            story.append(Spacer(1, 6))
        doc.build(story)
        return output
