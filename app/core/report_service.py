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
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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
                    "Timestamp",
                    "Device",
                    "GPS",
                    "Score",
                    "Risk",
                    "Integrity",
                ]
            )
            for record in records:
                writer.writerow(
                    [
                        record.evidence_id,
                        record.file_name,
                        record.timestamp,
                        record.device_model,
                        record.gps_display,
                        record.suspicion_score,
                        record.risk_level,
                        record.integrity_status,
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
                    "timestamp": record.timestamp,
                    "device_model": record.device_model,
                    "software": record.software,
                    "gps": {
                        "display": record.gps_display,
                        "latitude": record.gps_latitude,
                        "longitude": record.gps_longitude,
                    },
                    "anomaly_reasons": record.anomaly_reasons,
                    "suspicion_score": record.suspicion_score,
                    "risk_level": record.risk_level,
                    "sha256": record.sha256,
                    "md5": record.md5,
                }
            )
        output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return output

    def export_html(self, records: List[EvidenceRecord], case_name: str) -> Path:
        output = self.export_dir / "forensic_report.html"
        total = len(records)
        gps_count = sum(1 for record in records if record.has_gps)
        anomaly_count = sum(1 for record in records if record.risk_level != "Low")
        device_count = len({record.device_model for record in records if record.device_model not in {"Unknown", ""}})

        def badge_class(level: str) -> str:
            if level == "High":
                return "badge-high"
            if level == "Medium":
                return "badge-medium"
            return "badge-low"

        rows = "\n".join(
            f"""
            <tr>
                <td>{html.escape(record.evidence_id)}</td>
                <td>{html.escape(record.file_name)}</td>
                <td>{html.escape(record.timestamp)}</td>
                <td>{html.escape(record.device_model)}</td>
                <td>{html.escape(record.gps_display)}</td>
                <td>{record.suspicion_score}</td>
                <td><span class="risk {badge_class(record.risk_level)}">{html.escape(record.risk_level)}</span></td>
                <td>{html.escape('; '.join(record.anomaly_reasons))}</td>
            </tr>
            """
            for record in records
        )

        html_doc = f"""
        <html>
        <head>
            <title>{case_name} - Forensic Report</title>
            <style>
                body {{ font-family: Segoe UI, Arial, sans-serif; background:#06101b; color:#eaf4ff; margin:0; padding:28px; }}
                .card {{ background:#0c1a2d; border:1px solid #173555; border-radius:20px; padding:22px; margin-bottom:18px; }}
                h1,h2 {{ color:#7fd9ff; margin-top:0; }}
                table {{ width:100%; border-collapse:collapse; overflow:hidden; border-radius:14px; }}
                th, td {{ border:1px solid #193754; padding:11px; font-size:13px; vertical-align:top; }}
                th {{ background:#10243f; color:#88e2ff; text-align:left; }}
                .metrics {{ display:grid; grid-template-columns: repeat(4, minmax(160px, 1fr)); gap:14px; }}
                .metric {{ background:#071525; padding:16px; border-radius:16px; border:1px solid #173555; }}
                .metric .value {{ font-size:28px; font-weight:800; color:#ffffff; }}
                .muted {{ color:#9ab2cc; }}
                .risk {{ display:inline-block; padding:4px 10px; border-radius:999px; font-weight:700; }}
                .badge-high {{ background:#321a25; color:#ff91a5; border:1px solid #7f4356; }}
                .badge-medium {{ background:#332814; color:#ffd98a; border:1px solid #7d6030; }}
                .badge-low {{ background:#173125; color:#97efc5; border:1px solid #2f7753; }}
                ul {{ margin-bottom: 0; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>GeoTrace Forensics Report</h1>
                <p class="muted">Case: {case_name} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <div class="metrics">
                    <div class="metric"><div class="value">{total}</div><div>Images Loaded</div></div>
                    <div class="metric"><div class="value">{gps_count}</div><div>GPS Enabled</div></div>
                    <div class="metric"><div class="value">{anomaly_count}</div><div>Potential Anomalies</div></div>
                    <div class="metric"><div class="value">{device_count}</div><div>Known Devices</div></div>
                </div>
            </div>
            <div class="card">
                <h2>Executive Summary</h2>
                <p>This investigation package analyzed uploaded image evidence, extracted available metadata, attempted timestamp recovery from both EXIF and filename patterns, assessed geolocation availability, scored anomaly indicators, and preserved evidence integrity using cryptographic hashes.</p>
            </div>
            <div class="card">
                <h2>Evidence Findings</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Evidence ID</th>
                            <th>File</th>
                            <th>Timestamp</th>
                            <th>Device</th>
                            <th>GPS</th>
                            <th>Score</th>
                            <th>Risk</th>
                            <th>Investigation Notes</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows}
                    </tbody>
                </table>
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
        normal = styles["BodyText"]

        story = [
            Paragraph("GeoTrace Forensics Report", title_style),
            Spacer(1, 12),
            Paragraph(f"Case: {case_name}", normal),
            Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal),
            Spacer(1, 12),
            Paragraph(
                "This report summarizes EXIF extraction, timestamp recovery, GPS analysis, anomaly detection, and evidence integrity preservation for imported image evidence.",
                normal,
            ),
            Spacer(1, 12),
        ]

        table_data = [["Evidence ID", "File", "Timestamp", "Device", "GPS", "Score", "Risk"]]
        for record in records:
            table_data.append(
                [
                    record.evidence_id,
                    record.file_name,
                    record.timestamp,
                    record.device_model,
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
        doc.build(story)
        return output
