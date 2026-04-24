from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from PyQt5.QtGui import QPixmap

try:
    from ...core.models import EvidenceRecord
except ImportError:  # pragma: no cover - fallback for direct script execution
    from app.core.models import EvidenceRecord
from ..widgets import ChartCard


class ChartRenderingMixin:
    """Dashboard chart rendering kept separate from the main UI shell.

    This isolates matplotlib-heavy code and keeps the main window focused on
    event wiring and page composition.
    """

    def update_charts(self) -> None:
        records = self.case_manager.records
        if not records:
            for card in [self.chart_sources, self.chart_risks, self.chart_geo, self.chart_relationships]:
                card.set_chart_pixmap(None, "Load evidence to generate charts.")
            self.duplicate_terminal.setPlainText("Load evidence to generate duplicate-cluster analysis.")
            return

        source_counts: Dict[str, int] = {}
        for record in records:
            source_counts[record.source_type] = source_counts.get(record.source_type, 0) + 1
        self._render_adaptive_chart(self.chart_sources, list(source_counts.keys()), list(source_counts.values()), self.export_dir / "chart_sources.png", "source")

        risk_order = ["Low", "Medium", "High"]
        risk_counts = [sum(1 for r in records if r.risk_level == risk) for risk in risk_order]
        self._render_adaptive_chart(self.chart_risks, risk_order, risk_counts, self.export_dir / "chart_risks.png", "risk")

        self._render_coverage_chart(records)
        self._render_relationship_graph(records)
        self.duplicate_terminal.setPlainText(self._build_duplicate_terminal_text())

    def _render_coverage_chart(self, records: List[EvidenceRecord]) -> None:
        output_path = self.export_dir / "chart_geo_duplicate.png"
        gps_yes = sum(1 for r in records if r.has_gps)
        gps_no = sum(1 for r in records if not r.has_gps)
        dup_yes = sum(1 for r in records if r.duplicate_group)
        dup_no = sum(1 for r in records if not r.duplicate_group)
        if len(records) <= 1:
            text = (
                f"Single item only\n\nGPS: {'present' if gps_yes else 'absent'}\n"
                f"Duplicate status: {'clustered' if dup_yes else 'unique'}\n"
                "Adaptive mode replaces misleading mixed-category bars."
            )
            self.chart_geo.set_chart_pixmap(None, text)
            return
        plt.close("all")
        fig, ax = plt.subplots(figsize=(8.8, 3.9), dpi=180)
        fig.patch.set_facecolor("#04101b")
        ax.set_facecolor("#04101b")
        positions = [0, 1]
        width = 0.28
        ax.bar([p - width/2 for p in positions], [gps_yes, dup_yes], width=width, color="#20beff", edgecolor="#dff6ff", linewidth=0.5, label="Present / Clustered")
        ax.bar([p + width/2 for p in positions], [gps_no, dup_no], width=width, color="#2a86d1", edgecolor="#dff6ff", linewidth=0.5, label="Absent / Unique")
        ax.set_xticks(positions)
        ax.set_xticklabels(["GPS status", "Similarity status"], color="#eef8ff", fontsize=9)
        ax.tick_params(axis="y", colors="#dcefff", labelsize=8)
        ax.grid(axis="y", alpha=0.12, color="#7ecfff")
        ax.legend(facecolor="#06111d", edgecolor="#21486d", labelcolor="#eef8ff", fontsize=8)
        for x, val in zip([p - width/2 for p in positions], [gps_yes, dup_yes]):
            ax.text(x, val + 0.05, str(val), ha="center", va="bottom", color="#ffffff", fontsize=9, weight="bold")
        for x, val in zip([p + width/2 for p in positions], [gps_no, dup_no]):
            ax.text(x, val + 0.05, str(val), ha="center", va="bottom", color="#ffffff", fontsize=9, weight="bold")
        for spine in ax.spines.values():
            spine.set_color("#2f5c8e")
        fig.tight_layout(pad=1.4)
        fig.savefig(output_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close(fig)
        self.chart_geo.set_chart_pixmap(QPixmap(str(output_path)), "Coverage chart unavailable")

    def _render_adaptive_chart(self, card: ChartCard, labels: List[str], values: List[int], output_path: Path, kind: str) -> None:
        total = sum(values)
        nonzero = [(label, value) for label, value in zip(labels, values) if value > 0]
        if total <= 1:
            if kind == "coverage":
                text = "Single item only\n\nNo GPS → show explanation instead of empty bars.\nNo duplicates → 'No visual reuse found'."
            elif kind == "risk":
                label = nonzero[0][0] if nonzero else "No data"
                text = f"Single-item risk summary\n\n{label}: {nonzero[0][1] if nonzero else 0}\nAdaptive mode avoids oversized empty charts."
            else:
                label = nonzero[0][0] if nonzero else "No data"
                text = f"Single-item source summary\n\n{label}: {nonzero[0][1] if nonzero else 0}\nAdaptive mode avoids stretched charts."
            card.set_chart_pixmap(None, text)
            return

        plt.close("all")
        fig, ax = plt.subplots(figsize=(8.8, 3.9), dpi=180)
        fig.patch.set_facecolor("#04101b")
        ax.set_facecolor("#04101b")
        colors = ["#20beff", "#4bdfff", "#72ccff", "#2a86d1", "#6a7bff"]
        bars = ax.bar(range(len(labels)), values, color=colors[: len(labels)], edgecolor="#dff6ff", linewidth=0.5)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, color="#eef8ff", fontsize=9)
        ax.tick_params(axis="y", colors="#dcefff", labelsize=8)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05, str(value), ha="center", va="bottom", color="#ffffff", fontsize=9, weight="bold")
        ax.margins(x=0.08, y=0.08)
        for spine in ax.spines.values():
            spine.set_color("#2f5c8e")
        ax.grid(axis="both", alpha=0.12, color="#7ecfff")
        fig.tight_layout(pad=1.4)
        fig.savefig(output_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close(fig)
        card.set_chart_pixmap(QPixmap(str(output_path)), "Chart unavailable")

    def _build_duplicate_terminal_text(self) -> str:
        clusters: Dict[str, List[EvidenceRecord]] = {}
        for record in self.case_manager.records:
            if record.duplicate_group:
                clusters.setdefault(record.duplicate_group, []).append(record)
        lines = ["[ DUPLICATE DIFF / REUSE REVIEW ]", "=" * 96]
        if not clusters:
            lines.append("No visual reuse found in the active case. Exact-hash, perceptual-hash, and derivative heuristics did not produce any duplicate clusters.")
            return "\n".join(lines)
        for cluster, items in sorted(clusters.items()):
            lines.append(f"{cluster} ({len(items)} file(s))")
            lines.append("-" * 96)
            lead = items[0]
            lines.append(f"Lead item: {lead.evidence_id} — {lead.file_name} — {lead.dimensions} — {lead.timestamp}")
            for peer in items[1:]:
                lines.append(
                    f"Peer: {peer.evidence_id} — {peer.file_name} | relation {peer.duplicate_relation or 'linked'} | method {peer.duplicate_method or 'heuristic'} | distance {peer.duplicate_distance} | time {peer.timestamp}"
                )
            similarity_notes = [peer.similarity_note for peer in items if peer.similarity_note]
            if similarity_notes:
                lines.append(f"Correlation explanation: {similarity_notes[0]}")
            lines.append("Interpretation: use relation type, method, and distance together to decide whether the file is exact reuse, near-duplicate, or derivative/edited media.")
            lines.append("")
        singles = [record for record in self.case_manager.records if not record.duplicate_group and record.duplicate_relation]
        if singles:
            lines.extend(["[ CLOSEST NON-CLUSTERED PEERS ]", "-" * 96])
            for record in singles[:6]:
                lines.append(
                    f"{record.evidence_id}: {record.duplicate_relation} via {record.duplicate_method or 'heuristic'} | closest peer {', '.join(record.duplicate_peers) if record.duplicate_peers else 'unknown'} | note {record.similarity_note}"
                )
        return "\n".join(lines)


    def _render_relationship_graph(self, records: List[EvidenceRecord]) -> None:
        output_path = self.export_dir / "chart_relationships.png"
        if len(records) <= 1:
            self.chart_relationships.set_chart_pixmap(None, "Single item only\n\nRelationship graph becomes useful when at least two items exist with shared time, device, or duplicate signals.")
            return

        plt.close("all")
        fig, ax = plt.subplots(figsize=(8.8, 3.9), dpi=180)
        fig.patch.set_facecolor("#04101b")
        ax.set_facecolor("#04101b")
        xs = []
        ys = []
        for idx, record in enumerate(records):
            xs.append(idx)
            ys.append(1 + (idx % 3))
        for idx, record in enumerate(records):
            for jdx in range(idx + 1, len(records)):
                peer = records[jdx]
                same_device = record.device_model not in {"Unknown", ""} and record.device_model == peer.device_model
                same_day = record.timestamp[:10] == peer.timestamp[:10] and record.timestamp != "Unknown" and peer.timestamp != "Unknown"
                same_dup = bool(record.duplicate_group and record.duplicate_group == peer.duplicate_group)
                if same_device or same_day or same_dup:
                    color = "#ffd166" if same_dup else "#2ecfff" if same_device else "#66ecff"
                    ax.plot([xs[idx], xs[jdx]], [ys[idx], ys[jdx]], color=color, linewidth=1.4, alpha=0.55)
        for idx, record in enumerate(records):
            tone = "#ff8fa4" if record.risk_level == "High" else "#ffd166" if record.risk_level == "Medium" else "#61e3a8"
            ax.scatter(xs[idx], ys[idx], s=140, color=tone, edgecolors="#dff6ff", linewidths=0.7, zorder=5)
            ax.text(xs[idx], ys[idx] + 0.17, record.evidence_id, ha="center", va="bottom", fontsize=7.5, color="#eef8ff")
        ax.set_title("Evidence Relationship Graph", color="#f3fbff", fontsize=12, pad=10, weight="bold")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color("#2f5c8e")
        fig.tight_layout(pad=1.4)
        fig.savefig(output_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close(fig)
        self.chart_relationships.set_chart_pixmap(QPixmap(str(output_path)), "Relationship graph unavailable")

