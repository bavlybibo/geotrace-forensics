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
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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
        avg_score = round(sum(r.suspicion_score for r in records) / total) if total else 0
        generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        dominant_source = (
            max({r.source_type for r in records}, key=lambda s: sum(1 for r in records if r.source_type == s))
            if total
            else "Unknown"
        )

        def badge_class(level: str) -> str:
            return {"High": "badge-high", "Medium": "badge-medium"}.get(level, "badge-low")

        def chip(text: str, level: str = "neutral") -> str:
            return f"<span class='chip chip-{html.escape(level)}'>{html.escape(text)}</span>"

        rows = "\n".join(
            f"""
            <tr>
                <td>{html.escape(record.evidence_id)}</td>
                <td>
                    <strong>{html.escape(record.file_name)}</strong><br>
                    <span class='muted'>{html.escape(str(record.file_path))}</span>
                </td>
                <td>{html.escape(record.source_type)}</td>
                <td>{html.escape(record.timestamp)}<br><span class='muted'>{html.escape(record.timestamp_source)}</span></td>
                <td>{html.escape(record.device_model)}</td>
                <td>{html.escape(record.gps_display)}</td>
                <td>{record.suspicion_score}</td>
                <td>{record.confidence_score}%</td>
                <td><span class="risk {badge_class(record.risk_level)}">{html.escape(record.risk_level)}</span></td>
                <td>{html.escape(record.integrity_status)}</td>
            </tr>
            """
            for record in records
        )

        evidence_cards = []
        for record in records[:12]:
            image_html = ""
            try:
                image_html = f"<img class='thumb' src='{record.file_path.as_uri()}' alt='{html.escape(record.file_name)}'>"
            except Exception:
                image_html = ""
            leads_html = "".join(f"<li>{html.escape(lead)}</li>" for lead in record.osint_leads[:3])
            flags_html = "".join(f"<li>{html.escape(flag)}</li>" for flag in record.anomaly_reasons[:3])
            evidence_cards.append(
                f"""
                <section class="detail-card">
                    <div class="detail-header">
                        <div>
                            <h3>{html.escape(record.evidence_id)} — {html.escape(record.file_name)}</h3>
                            <div class="pill-row">
                                {chip(record.source_type, 'cyan')}
                                {chip(record.timestamp_source, 'neutral')}
                                {chip(f'Score {record.suspicion_score}', 'neutral')}
                                {chip(record.risk_level, 'risk' if record.risk_level == 'High' else 'warn' if record.risk_level == 'Medium' else 'good')}
                            </div>
                        </div>
                        {image_html}
                    </div>
                    <div class="detail-grid">
                        <div>
                            <p><strong>Analyst verdict:</strong> {html.escape(record.analyst_verdict)}</p>
                            <p><strong>Timestamp:</strong> {html.escape(record.timestamp)} ({html.escape(record.timestamp_source)})</p>
                            <p><strong>GPS:</strong> {html.escape(record.gps_display)}</p>
                            <p><strong>Device / Software:</strong> {html.escape(record.device_model)} / {html.escape(record.software)}</p>
                            <p><strong>Hashes:</strong><br><code>{html.escape(record.sha256)}</code></p>
                        </div>
                        <div>
                            <h4>Key Flags</h4>
                            <ul>{flags_html or '<li>No major metadata anomaly was flagged.</li>'}</ul>
                            <h4>OSINT Leads</h4>
                            <ul>{leads_html}</ul>
                        </div>
                    </div>
                </section>
                """
            )
        evidence_cards_html = "\n".join(evidence_cards)
        custody_html = "<br>".join(html.escape(line) for line in custody_log.splitlines()[:40]) if custody_log else "No custody actions logged."

        chart_blocks = []
        for file_name, title in [
            ("chart_sources.png", "Source Distribution"),
            ("chart_risks.png", "Risk Distribution"),
            ("chart_geo_duplicate.png", "GPS & Duplicate Coverage"),
            ("chart_timeline.png", "Visual Timeline"),
        ]:
            chart_path = self.export_dir / file_name
            if chart_path.exists():
                chart_blocks.append(
                    f"<div class='chart-card'><h3>{html.escape(title)}</h3><img src='{html.escape(file_name)}' alt='{html.escape(title)}'></div>"
                )
        charts_html = "\n".join(chart_blocks) or "<p class='muted'>No charts were available at report generation time.</p>"

        methodology = [
            "SHA-256 and MD5 hashing on evidence import to preserve integrity tracking.",
            "Timestamp recovery hierarchy: EXIF → filename pattern → filesystem times.",
            "Perceptual hashing to expose visually similar or re-exported image clusters.",
            "Context-aware scoring that distinguishes screenshots/exports from native camera originals.",
            "Analyst-style verdict generation with recommended next actions and evidentiary caveats.",
        ]
        methodology_html = "".join(f"<li>{html.escape(item)}</li>" for item in methodology)

        overall_assessment = (
            f"This case package contains <strong>{total}</strong> image artifacts. The dominant source profile is "
            f"<strong>{html.escape(dominant_source)}</strong>, with <strong>{gps_count}</strong> GPS-bearing files, "
            f"<strong>{len(duplicate_groups)}</strong> duplicate clusters, and an average anomaly score of <strong>{avg_score}</strong>. "
            f"The batch includes <strong>{screenshots}</strong> screenshot/export-style items, which lowers expected native EXIF depth and shifts more weight to filename, workflow, and custody-based reasoning."
        )

        html_doc = f"""
        <!doctype html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>GeoTrace Forensics X Report</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background:#04101b; color:#eef8ff; margin:0; padding:28px; }}
                .hero {{ background: linear-gradient(135deg, #08192d, #0c2441); border:1px solid #173c63; border-radius:28px; padding:32px; margin-bottom:24px; box-shadow:0 16px 34px rgba(0,0,0,.18); }}
                h1,h2,h3,h4 {{ color:#7edcff; margin-top:0; }}
                p, li {{ line-height:1.65; }}
                .muted {{ color:#93b3cf; font-size:13px; }}
                .metrics {{ display:grid; grid-template-columns:repeat(6, minmax(130px,1fr)); gap:16px; margin-top:22px; }}
                .metric {{ background:#071425; border:1px solid #173c63; border-radius:18px; padding:18px; }}
                .metric .value {{ font-size:32px; font-weight:800; color:#ffffff; }}
                .card {{ background:#081525; border:1px solid #173c63; border-radius:22px; padding:24px; margin-bottom:22px; }}
                .grid-two {{ display:grid; grid-template-columns:1.1fr .9fr; gap:20px; }}
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
                .detail-card {{ background:#06111d; border:1px solid #173b60; border-radius:20px; padding:18px; margin-bottom:16px; }}
                .detail-header {{ display:flex; justify-content:space-between; gap:18px; align-items:flex-start; }}
                .detail-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-top:14px; }}
                .thumb {{ width:220px; max-height:180px; object-fit:contain; border-radius:14px; border:1px solid #1f496f; background:#030b15; }}
                .pill-row {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:8px; }}
                .chip {{ display:inline-block; padding:4px 10px; border-radius:999px; font-size:12px; font-weight:700; }}
                .chip-neutral {{ background:#10243f; border:1px solid #27547f; color:#dff5ff; }}
                .chip-cyan {{ background:#0d2943; border:1px solid #36bdff; color:#9be7ff; }}
                .chip-good {{ background:#133124; border:1px solid #2f7753; color:#97efc5; }}
                .chip-warn {{ background:#342b14; border:1px solid #7a6331; color:#ffd48b; }}
                .chip-risk {{ background:#351621; border:1px solid #874a5c; color:#ffadbb; }}
                code {{ font-family:Consolas, monospace; color:#b9f2ff; word-break:break-all; }}
            </style>
        </head>
        <body>
            <section class="hero">
                <h1>GeoTrace Forensics X — Investigation Report</h1>
                <p class="muted">Case: {html.escape(case_name)} | Generated: {generated}</p>
                <p>{overall_assessment}</p>
                <div class="pill-row">
                    {chip(dominant_source, 'cyan')}
                    {chip(f'GPS Enabled {gps_count}', 'good' if gps_count else 'warn')}
                    {chip(f'Duplicate Clusters {len(duplicate_groups)}', 'neutral')}
                    {chip(f'Average Score {avg_score}', 'warn' if avg_score >= 30 else 'good')}
                </div>
                <div class="metrics">
                    <div class="metric"><div class="value">{total}</div><div>Images</div></div>
                    <div class="metric"><div class="value">{gps_count}</div><div>GPS Enabled</div></div>
                    <div class="metric"><div class="value">{anomaly_count}</div><div>Potential Anomalies</div></div>
                    <div class="metric"><div class="value">{device_count}</div><div>Known Devices</div></div>
                    <div class="metric"><div class="value">{len(duplicate_groups)}</div><div>Duplicate Clusters</div></div>
                    <div class="metric"><div class="value">{avg_score}</div><div>Average Score</div></div>
                </div>
            </section>

            <section class="grid-two">
                <div class="card">
                    <h2>Executive Summary</h2>
                    <p>GeoTrace performed integrity hashing, metadata extraction, timestamp recovery, source profiling, duplicate fingerprinting, and analyst-style verdict generation for each evidence item. The scoring model is context-aware, so screenshots and messaging exports are not treated the same way as camera originals.</p>
                    <p><strong>Operational workflow:</strong> Acquire → Verify → Extract → Correlate → Score → Report</p>
                </div>
                <div class="card">
                    <h2>Methodology Highlights</h2>
                    <ul>{methodology_html}</ul>
                </div>
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
                            <th>Risk</th>
                            <th>Integrity</th>
                        </tr>
                    </thead>
                    <tbody>{rows}</tbody>
                </table>
            </section>

            <section class="card">
                <h2>Evidence Detail Cards</h2>
                {evidence_cards_html}
            </section>

            <section class="card">
                <h2>Chain of Custody (Excerpt)</h2>
                <p><code>{custody_html}</code></p>
            </section>
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

        total = len(records)
        gps = sum(1 for r in records if r.has_gps)
        avg_score = round(sum(r.suspicion_score for r in records) / total) if total else 0

        story = [
            Paragraph("GeoTrace Forensics X — Investigation Report", title_style),
            Spacer(1, 10),
            Paragraph(f"Case: {case_name}", normal),
            Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal),
            Spacer(1, 12),
            Paragraph("Executive Summary", heading),
            Paragraph(
                f"This report summarizes integrity hashing, metadata extraction, timestamp recovery, source profiling, duplicate fingerprinting, and analyst-style evidence verdicting for {total} image artifact(s). GPS-bearing files: {gps}. Average anomaly score: {avg_score}.",
                normal,
            ),
            Spacer(1, 10),
            Paragraph("Methodology", heading),
            Paragraph("Acquire → Verify → Extract → Correlate → Score → Report", normal),
            Spacer(1, 10),
        ]

        table_data = [["ID", "File", "Source", "Timestamp", "GPS", "Score", "Risk"]]
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
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123b67")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#8eb8d6")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f5fbff")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f5fbff"), colors.HexColor("#eaf6ff")]),
                ]
            )
        )
        story.extend([Paragraph("Evidence Matrix", heading), table, Spacer(1, 16)])

        for record in records[:8]:
            story.append(Paragraph(f"{record.evidence_id} — {record.file_name}", heading))
            story.append(Paragraph(record.analyst_verdict, normal))
            story.append(Paragraph(f"Timestamp: {record.timestamp} ({record.timestamp_source})", normal))
            story.append(Paragraph(f"GPS: {record.gps_display}", normal))
            story.append(Paragraph(f"Device / Software: {record.device_model} / {record.software}", normal))
            if record.file_path.exists():
                try:
                    story.append(Image(str(record.file_path), width=220, height=150))
                except Exception:
                    pass
            story.append(Spacer(1, 14))
        doc.build(story)
        return output
