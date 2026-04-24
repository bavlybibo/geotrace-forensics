from __future__ import annotations

from typing import List

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

try:
    from ...core.anomalies import parse_timestamp
    from ...core.models import EvidenceRecord
    from ..widgets import AutoHeightNarrativeView, ChartCard
except ImportError:  # pragma: no cover - fallback for direct script execution
    from app.core.anomalies import parse_timestamp
    from app.core.models import EvidenceRecord
    from app.ui.widgets import AutoHeightNarrativeView, ChartCard


class TimelinePageMixin:

    def _build_timeline_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        hero = QFrame()
        hero.setObjectName("PanelFrame")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(14, 14, 14, 14)
        hero_layout.setSpacing(8)
        title = QLabel("Timeline Review")
        title.setObjectName("SectionLabel")
        meta = QLabel("Single-item cases collapse into a compact anchor card while larger cases can still render full charts.")
        meta.setObjectName("SectionMetaLabel")
        hero_layout.addWidget(title)
        hero_layout.addWidget(meta)
        layout.addWidget(hero)

        badge_row = QGridLayout()
        badge_row.setHorizontalSpacing(8)
        badge_row.setVerticalSpacing(8)
        self.timeline_badge_start = self._timeline_badge("Earliest: —")
        self.timeline_badge_end = self._timeline_badge("Latest: —")
        self.timeline_badge_span = self._timeline_badge("Span: —")
        self.timeline_badge_order = self._timeline_badge("Ordering: —")
        for idx, badge in enumerate([self.timeline_badge_start, self.timeline_badge_end, self.timeline_badge_span, self.timeline_badge_order]):
            badge_row.addWidget(badge, 0, idx)
        layout.addLayout(badge_row)

        self.timeline_chart = ChartCard("Timeline Reconstruction", "Single-item cases use a compact evidence anchor instead of a giant empty plot.")
        self.timeline_narrative = AutoHeightNarrativeView("Timeline narrative generation will appear here after evidence is loaded.", max_auto_height=200)
        self.timeline_text = AutoHeightNarrativeView("Timeline analysis will appear here after evidence is loaded.", max_auto_height=220)
        layout.addWidget(self.timeline_chart, 1)
        layout.addWidget(self._shell("Timeline Narrative", self.timeline_narrative, "Readable chronological story generated from the available anchors and parser context."))
        layout.addWidget(self._shell("Timeline Analyst Notes", self.timeline_text, "Chronological interpretation with parser, signature, and trust context."))
        layout.addStretch(1)
        return widget

    def _timeline_badge(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("TimelineBadge")
        lbl.setWordWrap(True)
        return lbl

    def populate_timeline(self) -> None:
        records = self.case_manager.records
        if not records:
            self.timeline_text.setPlainText("No evidence loaded yet.")
            if hasattr(self, "timeline_narrative"):
                self.timeline_narrative.setPlainText("No evidence loaded yet.")
            self.timeline_chart.set_chart_pixmap(None, "Load evidence to generate a visual timeline.")
            self._set_timeline_defaults()
            return
        ordered = sorted(records, key=lambda r: (r.timestamp == "Unknown", r.timestamp, r.evidence_id))
        lines = ["[ TIMELINE ANALYST OUTPUT ]", "=" * 96]
        parsed_points = []
        for idx, record in enumerate(ordered, start=1):
            lines.append(
                f"#{idx:02d}  {record.timestamp:<19} | {record.evidence_id:<8} | {record.risk_level:<6} | Score {record.suspicion_score:<3} | {record.source_type}"
            )
            lines.append(f"      File        : {record.file_name}")
            lines.append(f"      Native GPS  : {record.gps_display}")
            lines.append(f"      Derived Geo : {record.derived_geo_display}")
            lines.append(f"      Time Source : {record.timestamp_source}")
            lines.append(f"      Parser      : {record.parser_status} | Signature {record.signature_status} | Trust {record.format_trust}")
            if record.duplicate_group:
                lines.append(f"      Duplicate   : {record.duplicate_group}")
            if record.anomaly_reasons:
                lines.append(f"      Lead        : {record.anomaly_reasons[0]}")
            lines.append("-" * 96)
            dt = parse_timestamp(record.timestamp)
            if dt is not None:
                parsed_points.append((record, dt))
        self.timeline_text.setPlainText("\n".join(lines))

        if parsed_points:
            first_record, first_dt = parsed_points[0]
            last_record, last_dt = parsed_points[-1]
            span = last_dt - first_dt
            self.timeline_badge_start.setText(f"Earliest: {first_dt.strftime('%Y-%m-%d %H:%M')}")
            self.timeline_badge_end.setText(f"Latest: {last_dt.strftime('%Y-%m-%d %H:%M')}")
            self.timeline_badge_span.setText(f"Span: {str(span).split('.')[0]}")
            self.timeline_badge_order.setText(f"Ordering: {len(parsed_points)} anchored item(s)")
        else:
            self._set_timeline_defaults()
        if hasattr(self, "timeline_narrative"):
            self.timeline_narrative.setPlainText(self._build_timeline_narrative(ordered, parsed_points))
        self._render_timeline_chart(ordered)

    def _build_timeline_narrative(self, ordered: List[EvidenceRecord], parsed_points: List[tuple[EvidenceRecord, object]]) -> str:
        if not ordered:
            return "No evidence loaded yet."
        if len(ordered) == 1:
            record = ordered[0]
            code_hint = " "
            if record.hidden_code_indicators:
                code_hint = " Byte-level scanning also recovered code-like markers that should be reviewed before sharing or executing anything derived from the file."
            elif record.extracted_strings:
                code_hint = " Readable strings were recovered from the container for analyst context, but no strong code markers were identified."
            return (
                f"Single-item narrative: {record.evidence_id} is currently the only anchored item in the case. "
                f"Its strongest chronological lead is {record.timestamp_source} at {record.timestamp_confidence}% confidence. "
                f"Analytic confidence is {record.confidence_score}%, evidentiary value is {record.evidentiary_value}%, and courtroom strength is {record.courtroom_strength}%. "
                f"Source profile reads as {record.source_type}, parser state is {record.parser_status}, and trust is {record.format_trust}. "
                f"Native GPS is {'present' if record.has_gps else 'absent'} while derived geo is {record.derived_geo_display if record.derived_geo_display != 'Unavailable' else 'absent'}."
                + code_hint +
                " Next move: corroborate the time anchor with uploads, chats, witness timelines, or cloud sync history before making chronology claims."
            )
        first = ordered[0]
        last = ordered[-1]
        risky = [r.evidence_id for r in ordered if r.risk_level == "High"]
        duplicates = sorted({r.duplicate_group for r in ordered if r.duplicate_group})
        return (
            f"The reconstructed sequence begins with {first.evidence_id} at {first.timestamp} and ends with {last.evidence_id} at {last.timestamp}. "
            f"Anchored items: {len(parsed_points)} of {len(ordered)}. "
            f"High-priority items: {', '.join(risky) if risky else 'none'}. "
            f"Duplicate clusters observed: {len(duplicates)}. "
            "Analyst reading: validate major time gaps, then compare duplicate/derivative media to determine whether later items represent reposts, edits, or separate captures."
        )

    def _render_timeline_chart(self, ordered: List[EvidenceRecord]) -> None:
        parsed = [(record, parse_timestamp(record.timestamp)) for record in ordered]
        dated = [(record, dt) for record, dt in parsed if dt is not None]
        output_path = self.export_dir / "chart_timeline.png"
        if not dated:
            self.timeline_chart.set_chart_pixmap(None, "No recoverable timestamps were available. Use source workflow, filesystem time, and case notes as the main pivots.")
            return
        if len(dated) == 1:
            record, dt = dated[0]
            self.timeline_chart.set_chart_pixmap(
                None,
                f"Single anchored item only\n\n{record.evidence_id} at {dt.strftime('%Y-%m-%d %H:%M')}\nTime source: {record.timestamp_source}\nRisk: {record.risk_level} / Score {record.suspicion_score}\n\nMini-card mode is used instead of a stretched full timeline.",
            )
            return

        plt.close("all")
        fig, ax = plt.subplots(figsize=(12.8, 4.5), dpi=180)
        fig.patch.set_facecolor("#04101b")
        ax.set_facecolor("#04101b")

        x_values = [dt for _, dt in dated]
        y_values = list(range(len(dated), 0, -1))
        ax.plot(x_values, y_values, color="#2ecfff", linewidth=1.8, alpha=0.55, zorder=2)

        risk_edge = {"High": "#ff8fa4", "Medium": "#ffd166", "Low": "#61e3a8"}
        source_fill = {"Native EXIF Original": "#1ca8ff", "Embedded EXIF": "#53c4ff", "Embedded EXIF Digitized": "#53c4ff", "Filename Pattern": "#ffd166", "Filesystem Modified Time": "#f7a35c", "Filesystem Birth / Creation Time": "#f7a35c", "Unavailable": "#8c6cff"}
        marker_sizes = [68 + (record.confidence_score * 0.55) for record, _ in dated]
        edge_colors = [risk_edge.get(record.risk_level, "#dff8ff") for record, _ in dated]
        face_colors = [source_fill.get(record.timestamp_source, "#6dd3ff") for record, _ in dated]
        ax.scatter(x_values, y_values, s=marker_sizes, color=face_colors, edgecolors=edge_colors, linewidths=1.9, zorder=5)

        for idx, ((record, dt), y) in enumerate(zip(dated, y_values)):
            label_y = y + 0.42 if idx % 2 == 0 else y - 0.68
            ax.text(
                dt,
                label_y,
                f"{record.evidence_id} • {record.timestamp_source} • {record.risk_level}",
                color="#eef8ff",
                fontsize=7.2,
                ha="center",
                va="center",
                bbox=dict(boxstyle="round,pad=0.26", facecolor="#081a2b", edgecolor="#21486d", alpha=0.96),
                zorder=6,
            )
            if record.parser_status != "Valid" or record.signature_status == "Mismatch":
                ax.text(dt, y - 0.95, "tamper / parser review", color="#ffcf7a", fontsize=6.8, ha="center", zorder=6)

        for (prev_record, prev_dt), (curr_record, curr_dt) in zip(dated, dated[1:]):
            gap = curr_dt - prev_dt
            if gap.total_seconds() >= 4 * 3600:
                midpoint = prev_dt + gap / 2
                ax.axvspan(prev_dt, curr_dt, color="#10314d", alpha=0.12, zorder=1)
                ax.text(midpoint, min(y_values) - 0.58, f"Gap {str(gap).split('.')[0]}", color="#89b9d9", fontsize=7, ha="center")

        ax.text(0.99, 1.02, "Fill = time source | Edge = risk | Labels = tamper/parser flags", transform=ax.transAxes, ha="right", va="bottom", color="#8fb7d6", fontsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d\n%H:%M"))
        ax.tick_params(axis="x", colors="#dcefff", labelsize=8)
        ax.tick_params(axis="y", colors="#dcefff", labelsize=8)
        ax.set_yticks(y_values)
        ax.set_yticklabels([record.evidence_id for record, _ in dated])
        ax.set_ylabel("Reconstructed order", color="#dcefff")
        ax.set_xlabel("Recovered timeline anchors", color="#9ccae6")
        ax.grid(axis="x", alpha=0.16, color="#78cfff")
        ax.grid(axis="y", alpha=0.05, color="#78cfff")
        ax.set_title("Chronological Evidence Reconstruction", color="#f3fbff", fontsize=12, pad=12, weight="bold")
        for spine in ax.spines.values():
            spine.set_color("#2f5c8e")
        fig.tight_layout(pad=1.4)
        fig.savefig(output_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close(fig)
        self.timeline_chart.set_chart_pixmap(QPixmap(str(output_path)), "Timeline chart unavailable")
