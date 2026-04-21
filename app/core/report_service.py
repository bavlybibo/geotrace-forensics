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
                    "Case ID",
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
                        record.case_id,
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
                    "case_id": record.case_id,
                    "case_name": record.case_name,
                    "evidence_id": record.evidence_id,
                    "file_name": record.file_name,
                    "file_path": str(record.file_path),
                    "source_type": record.source_type,
                    "timestamp": record.timestamp,
                    "timestamp_source": record.timestamp_source,
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
                    },
                    "anomaly_reasons": record.anomaly_reasons,
                    "osint_leads": record.osint_leads,
                    "analyst_verdict": record.analyst_verdict,
                    "suspicion_score": record.suspicion_score,
                    "confidence_score": record.confidence_score,
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

    def export_courtroom_summary(self, records: List[EvidenceRecord], case_id: str, case_name: str) -> Path:
        output = self.export_dir / "courtroom_summary.txt"
        total = len(records)
        high = sum(1 for r in records if r.risk_level == "High")
        gps = sum(1 for r in records if r.has_gps)
        duplicates = len({r.duplicate_group for r in records if r.duplicate_group})
        ordered = sorted(records, key=lambda r: (-r.suspicion_score, r.evidence_id))
        lines = [
            f"GeoTrace Forensics X — Courtroom Summary",
            f"Case ID: {case_id}",
            f"Case Name: {case_name}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "Executive Summary",
            "-----------------",
            f"Total evidence items: {total}",
            f"High-risk items: {high}",
            f"GPS-bearing items: {gps}",
            f"Duplicate clusters: {duplicates}",
            "",
            "Most Important Findings",
            "-----------------------",
        ]
        for record in ordered[:5]:
            lines.extend(
                [
                    f"{record.evidence_id} | {record.file_name} | {record.risk_level} | Score {record.suspicion_score}",
                    f"  Time: {record.timestamp} ({record.timestamp_source})",
                    f"  Parser: {record.parser_status} | Signature: {record.signature_status} | Trust: {record.format_trust}",
                    f"  GPS: {record.gps_display}",
                    f"  Analyst note: {record.analyst_verdict}",
                    "",
                ]
            )
        output.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        return output

    def export_html(self, records: List[EvidenceRecord], case_id: str, case_name: str, custody_log: str = "") -> Path:
        output = self.export_dir / "forensic_report.html"
        total = len(records)
        gps_count = sum(1 for record in records if record.has_gps)
        anomaly_count = sum(1 for record in records if record.risk_level != "Low")
        duplicate_groups = sorted({record.duplicate_group for record in records if record.duplicate_group})
        avg_score = round(sum(r.suspicion_score for r in records) / total) if total else 0
        generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        dominant_source = (
            max({r.source_type for r in records}, key=lambda s: sum(1 for r in records if r.source_type == s))
            if total
            else "Unknown"
        )

        def badge_class(level: str) -> str:
            return {"High": "badge-high", "Medium": "badge-medium"}.get(level, "badge-low")

        rows = "\n".join(
            f"""
            <tr>
                <td>{html.escape(record.evidence_id)}</td>
                <td><strong>{html.escape(record.file_name)}</strong><br><span class='muted'>{html.escape(str(record.file_path))}</span></td>
                <td>{html.escape(record.source_type)}</td>
                <td>{html.escape(record.timestamp)}<br><span class='muted'>{html.escape(record.timestamp_source)}</span></td>
                <td>{html.escape(record.device_model)}</td>
                <td>{html.escape(record.gps_display)}</td>
                <td>{record.suspicion_score}</td>
                <td>{record.confidence_score}%</td>
                <td>{html.escape(record.parser_status)} / {html.escape(record.signature_status)}</td>
                <td><span class="risk {badge_class(record.risk_level)}">{html.escape(record.risk_level)}</span></td>
            </tr>
            """
            for record in records
        )

        appendix_blocks = []
        for record in records:
            appendix_blocks.append(
                f"""
                <div class="detail-card">
                    <h3>{html.escape(record.evidence_id)} — {html.escape(record.file_name)}</h3>
                    <div class="pill-row">
                        <span class="pill">{html.escape(record.source_type)}</span>
                        <span class="pill">{html.escape(record.timestamp_source)}</span>
                        <span class="pill">{html.escape(record.gps_display)}</span>
                        <span class="pill">Signature {html.escape(record.signature_status)}</span>
                        <span class="pill">Trust {html.escape(record.format_trust)}</span>
                        <span class="pill">Score {record.suspicion_score}</span>
                    </div>
                    <p>{html.escape(record.analyst_verdict)}</p>
                    <ul>{''.join(f'<li>{html.escape(lead)}</li>' for lead in record.osint_leads[:4])}</ul>
                </div>
                """
            )
        custody_html = "<br>".join(html.escape(line) for line in custody_log.splitlines()[:40]) if custody_log else "No custody actions logged."

        chart_blocks = []
        for file_name, title in [
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
            <title>GeoTrace Forensics X Report</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background:#04101b; color:#eef8ff; margin:0; padding:28px; }}
                .hero {{ background: linear-gradient(135deg, #08192d, #0c2441); border:1px solid #173c63; border-radius:28px; padding:32px; margin-bottom:24px; box-shadow:0 16px 34px rgba(0,0,0,.18); }}
                h1,h2,h3 {{ color:#7edcff; margin-top:0; }}
                p, li {{ line-height:1.7; }}
                .muted {{ color:#93b3cf; font-size:13px; }}
                .metrics {{ display:grid; grid-template-columns:repeat(6, minmax(130px,1fr)); gap:16px; margin-top:22px; }}
                .metric {{ background:#071425; border:1px solid #173c63; border-radius:18px; padding:18px; }}
                .metric .value {{ font-size:32px; font-weight:800; color:#ffffff; }}
                .card {{ background:#081525; border:1px solid #173c63; border-radius:22px; padding:24px; margin-bottom:22px; }}
                .grid-two {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
                .grid-charts {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
                .chart-card {{ background:#06111d; border:1px solid #143553; border-radius:18px; padding:16px; }}
                .chart-card img {{ width:100%; border-radius:14px; border:1px solid #1f496f; background:#030b15; }}
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
                <h1>GeoTrace Forensics X — Investigation Report</h1>
                <p class="muted">Case: {html.escape(case_id)} | {html.escape(case_name)} | Generated: {generated}</p>
                <p>This report is structured in three layers: <strong>Executive Summary</strong>, <strong>Evidence Matrix</strong>, and <strong>Deep Technical Appendix</strong>.</p>
                <div class="metrics">
                    <div class="metric"><div class="value">{total}</div><div>Images</div></div>
                    <div class="metric"><div class="value">{gps_count}</div><div>GPS Enabled</div></div>
                    <div class="metric"><div class="value">{anomaly_count}</div><div>Review Items</div></div>
                    <div class="metric"><div class="value">{len(duplicate_groups)}</div><div>Duplicate Clusters</div></div>
                    <div class="metric"><div class="value">{avg_score}</div><div>Average Score</div></div>
                    <div class="metric"><div class="value">{html.escape(dominant_source)}</div><div>Dominant Source</div></div>
                </div>
            </section>

            <section class="card">
                <h2>Executive Summary</h2>
                <p>The current case contains <strong>{total}</strong> evidence item(s). <strong>{gps_count}</strong> item(s) contain native GPS, <strong>{len(duplicate_groups)}</strong> duplicate cluster(s) were detected, and the dominant profile is <strong>{html.escape(dominant_source)}</strong>. Average suspicion score across the set is <strong>{avg_score}</strong>.</p>
                <p>Decoder health, timestamp provenance, signature status, and source workflow were all considered together so malformed or export-style media are not treated like camera-original evidence.</p>
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
                <h2>Chain of Custody (Current Case Only)</h2>
                <p><code>{custody_html}</code></p>
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
        story = [
            Paragraph("GeoTrace Forensics X — Investigation Report", title),
            Paragraph(f"Case: {html.escape(case_id)} — {html.escape(case_name)}", body),
            Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", body),
            Spacer(1, 10),
            Paragraph("Executive Summary", heading),
            Paragraph(f"Total evidence items: {len(records)}. This PDF is intentionally concise and mirrors the Executive Summary, Evidence Matrix, and Technical Appendix structure used in the HTML report.", body),
            Spacer(1, 10),
            Paragraph("Evidence Matrix", heading),
        ]
        table_data = [["ID", "File", "Time", "GPS", "Score", "Risk"]]
        for record in records:
            table_data.append([record.evidence_id, record.file_name, record.timestamp, record.gps_display, str(record.suspicion_score), record.risk_level])
        table = Table(table_data, repeatRows=1, colWidths=[52, 140, 115, 90, 48, 48])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#10243f")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cedff2")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f8fb")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)
        story.append(PageBreak())
        story.append(Paragraph("Deep Technical Appendix", heading))
        for record in records:
            story.extend([
                Paragraph(f"{record.evidence_id} — {record.file_name}", styles["Heading3"]),
                Paragraph(f"Risk {record.risk_level} / Score {record.suspicion_score} / Parser {record.parser_status} / Signature {record.signature_status}", body),
                Paragraph(html.escape(record.analyst_verdict), body),
                Spacer(1, 8),
            ])
        doc.build(story)
        return output
