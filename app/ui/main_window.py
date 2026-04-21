from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import List

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.case_manager import CaseManager
from app.core.map_service import MapService
from app.core.models import EvidenceRecord
from app.core.report_service import ReportService
from .styles import APP_STYLESHEET
from .widgets import StatCard


class GeoTraceMainWindow(QMainWindow):
    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.project_root = project_root
        self.case_manager = CaseManager(project_root)
        self.map_service = MapService(project_root / "exports")
        self.report_service = ReportService(project_root / "exports")
        self.records: List[EvidenceRecord] = []
        self.filtered_records: List[EvidenceRecord] = []
        self.current_preview_pixmap: QPixmap | None = None

        self.setWindowTitle("GeoTrace Forensics — Image Metadata & Geolocation Analysis")
        self.resize(1620, 980)
        self.setMinimumSize(1280, 820)
        self.setStyleSheet(APP_STYLESHEET)
        self._build_ui()
        self.refresh_dashboard()
        self.clear_details()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(self._build_header())
        root.addWidget(self._build_stat_cards())
        root.addWidget(self._build_controls())
        root.addWidget(self._build_main_area(), 1)
        root.addWidget(self._build_footer())

        self.setCentralWidget(central)

    def _build_header(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("HeaderFrame")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(8)

        title = QLabel("GeoTrace Forensics")
        title.setObjectName("TitleLabel")

        subtitle = QLabel(
            "Image evidence intelligence platform for EXIF extraction, timestamp recovery, geolocation analysis, anomaly scoring, and chain-of-custody reporting."
        )
        subtitle.setObjectName("SubtitleLabel")
        subtitle.setWordWrap(True)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        self.case_badge = QLabel("Case: GT-2026-001")
        self.case_badge.setObjectName("BadgeLabel")
        self.mode_badge = QLabel("Mode: Investigation")
        self.mode_badge.setObjectName("BadgeLabel")
        self.export_badge = QLabel("Exports: Ready")
        self.export_badge.setObjectName("BadgeLabel")
        badge_row.addWidget(self.case_badge)
        badge_row.addWidget(self.mode_badge)
        badge_row.addWidget(self.export_badge)
        badge_row.addStretch(1)

        left.addWidget(title)
        left.addWidget(subtitle)
        left.addLayout(badge_row)

        right = QVBoxLayout()
        right.setSpacing(6)
        self.case_label = QLabel("Case ID: GT-2026-001")
        self.case_label.setObjectName("SubtitleLabel")
        self.status_label = QLabel("Status: Awaiting evidence")
        self.status_label.setObjectName("SubtitleLabel")
        self.integrity_label = QLabel("Integrity: 0/0 Verified")
        self.integrity_label.setObjectName("SubtitleLabel")
        right.addWidget(self.case_label, alignment=Qt.AlignRight)
        right.addWidget(self.status_label, alignment=Qt.AlignRight)
        right.addWidget(self.integrity_label, alignment=Qt.AlignRight)
        right.addStretch(1)

        layout.addLayout(left, 3)
        layout.addLayout(right, 1)
        return frame

    def _build_stat_cards(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("PanelFrame")
        layout = QGridLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        self.card_total = StatCard("Images Loaded")
        self.card_gps = StatCard("GPS Enabled")
        self.card_anomalies = StatCard("Anomalies Detected")
        self.card_devices = StatCard("Devices Identified")
        self.card_timeline = StatCard("Timeline Span")
        self.card_integrity = StatCard("Evidence Integrity")

        cards = [
            self.card_total,
            self.card_gps,
            self.card_anomalies,
            self.card_devices,
            self.card_timeline,
            self.card_integrity,
        ]
        positions = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]
        for card, (row, column) in zip(cards, positions):
            layout.addWidget(card, row, column)
            layout.setColumnStretch(column, 1)
        return frame

    def _build_controls(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("PanelFrame")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        self.btn_load_images = QPushButton("Import Image Files")
        self.btn_load_images.setObjectName("PrimaryButton")
        self.btn_load_images.clicked.connect(self.import_images)

        self.btn_load_folder = QPushButton("Import Folder")
        self.btn_load_folder.clicked.connect(self.import_folder)

        self.btn_generate_report = QPushButton("Generate Reports")
        self.btn_generate_report.clicked.connect(self.generate_reports)

        self.btn_open_map = QPushButton("Open Geolocation Map")
        self.btn_open_map.clicked.connect(self.open_map)
        self.btn_open_map.setEnabled(False)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search by evidence ID, filename, source type, device, or GPS...")
        self.search_box.textChanged.connect(self.apply_filters)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All Evidence", "Has GPS", "High Risk", "Medium Risk", "Low Risk"])
        self.filter_combo.currentTextChanged.connect(self.apply_filters)

        layout.addWidget(self.btn_load_images)
        layout.addWidget(self.btn_load_folder)
        layout.addWidget(self.btn_generate_report)
        layout.addWidget(self.btn_open_map)
        layout.addWidget(self.search_box, 1)
        layout.addWidget(self.filter_combo)
        return frame

    def _build_main_area(self) -> QWidget:
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([980, 560])
        return splitter

    def _build_left_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("PanelFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        heading_row = QHBoxLayout()
        title = QLabel("Evidence Inventory")
        title.setObjectName("SectionLabel")
        self.inventory_meta = QLabel("Load image evidence to begin forensic analysis.")
        self.inventory_meta.setObjectName("MutedLabel")
        heading_row.addWidget(title)
        heading_row.addStretch(1)
        heading_row.addWidget(self.inventory_meta)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Ready")

        self.table = QTableWidget(0, 8)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setHorizontalHeaderLabels(
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
        self.table.itemSelectionChanged.connect(self.populate_details)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)

        layout.addLayout(heading_row)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.table, 1)
        return frame

    def _build_right_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("PanelFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_preview_tab(), "Preview")
        self.tabs.addTab(self._build_metadata_tab(), "Metadata")
        self.tabs.addTab(self._build_timeline_tab(), "Timeline")
        self.tabs.addTab(self._build_custody_tab(), "Custody")
        layout.addWidget(self.tabs)
        return frame

    def _build_preview_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        title = QLabel("Evidence Preview")
        title.setObjectName("SectionLabel")

        self.image_scroll = QScrollArea()
        self.image_scroll.setWidgetResizable(True)
        self.image_scroll.setMinimumHeight(360)
        self.image_scroll.setFrameShape(QFrame.NoFrame)

        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(10, 10, 10, 10)

        self.image_preview = QLabel("No evidence selected")
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setMinimumHeight(320)
        self.image_preview.setStyleSheet(
            "border: 1px dashed #2b527e; border-radius: 16px; background:#081524; padding: 12px;"
        )
        self.image_preview.setWordWrap(True)
        preview_layout.addWidget(self.image_preview)

        self.image_scroll.setWidget(preview_container)

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMinimumHeight(220)
        self.summary_text.setPlaceholderText("Image intelligence summary will appear here.")

        layout.addWidget(title)
        layout.addWidget(self.image_scroll, 1)
        layout.addWidget(self.summary_text)
        return widget

    def _build_metadata_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        title = QLabel("Metadata Intelligence")
        title.setObjectName("SectionLabel")
        self.metadata_view = QPlainTextEdit()
        self.metadata_view.setReadOnly(True)

        notes_title = QLabel("Investigator Notes")
        notes_title.setObjectName("SectionLabel")
        self.note_editor = QTextEdit()
        self.note_editor.setPlaceholderText("Add analyst observations for the selected evidence item...")
        save_button = QPushButton("Save Investigator Note")
        save_button.clicked.connect(self.save_note)

        layout.addWidget(title)
        layout.addWidget(self.metadata_view, 1)
        layout.addWidget(notes_title)
        layout.addWidget(self.note_editor)
        layout.addWidget(save_button)
        return widget

    def _build_timeline_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        title = QLabel("Timeline & Alerts")
        title.setObjectName("SectionLabel")
        self.timeline_text = QPlainTextEdit()
        self.timeline_text.setReadOnly(True)
        layout.addWidget(title)
        layout.addWidget(self.timeline_text, 1)
        return widget

    def _build_custody_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        title = QLabel("Chain of Custody")
        title.setObjectName("SectionLabel")
        self.custody_text = QPlainTextEdit()
        self.custody_text.setReadOnly(True)
        refresh_button = QPushButton("Refresh Custody Log")
        refresh_button.clicked.connect(self.populate_custody_log)
        layout.addWidget(title)
        layout.addWidget(self.custody_text, 1)
        layout.addWidget(refresh_button)
        return widget

    def _build_footer(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("PanelFrame")
        layout = QGridLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(8)

        tips = [
            "Auto SHA-256 hashing and evidence fingerprinting on import",
            "Context-aware anomaly scoring to reduce false positives on screenshots/exports",
            "Interactive Folium map generation for GPS-enabled evidence",
            "HTML, PDF, CSV, and JSON report export for presentation and documentation",
        ]
        for idx, text in enumerate(tips):
            label = QLabel(f"• {text}")
            label.setObjectName("SubtitleLabel")
            layout.addWidget(label, idx // 2, idx % 2)
        return frame

    def import_images(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Evidence Images",
            str(self.project_root),
            "Images (*.jpg *.jpeg *.png *.tif *.tiff *.webp)",
        )
        if files:
            self._load_paths([Path(file) for file in files])

    def import_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Evidence Folder", str(self.project_root))
        if folder:
            self._load_paths([Path(folder)])

    def _load_paths(self, paths: List[Path]) -> None:
        self.progress_bar.setFormat("Analyzing evidence...")
        self.progress_bar.setValue(15)
        self.records = self.case_manager.load_images(paths)
        self.progress_bar.setValue(80)
        self.filtered_records = list(self.records)
        self.populate_table(self.filtered_records)
        self.refresh_dashboard()
        self.populate_timeline()
        self.populate_custody_log()
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Analysis complete")
        if self.filtered_records:
            self.table.selectRow(0)
        else:
            self.clear_details()
        self.status_label.setText(f"Status: {len(self.records)} evidence items analyzed")
        self.inventory_meta.setText(f"Loaded {len(self.records)} evidence items.")

    def populate_table(self, records: List[EvidenceRecord]) -> None:
        self.table.setRowCount(0)
        for record in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                record.evidence_id,
                record.file_name,
                record.timestamp,
                record.device_model,
                record.gps_display,
                str(record.suspicion_score),
                record.risk_level,
                record.integrity_status,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in {5, 6, 7}:
                    item.setTextAlignment(Qt.AlignCenter)
                if column == 6:
                    if value == "High":
                        item.setForeground(QColor("#ff6b81"))
                    elif value == "Medium":
                        item.setForeground(QColor("#ffd166"))
                    else:
                        item.setForeground(QColor("#8ef5c8"))
                if column == 7:
                    item.setForeground(QColor("#9fe8ff"))
                self.table.setItem(row, column, item)
            self.table.setRowHeight(row, 42)

        if self.table.rowCount() == 0:
            self.inventory_meta.setText("No results match the current filter.")
        else:
            self.inventory_meta.setText(f"Showing {len(records)} evidence items.")

    def refresh_dashboard(self) -> None:
        stats = self.case_manager.build_stats()
        self.card_total.set_value(str(stats.total_images))
        self.card_gps.set_value(str(stats.gps_enabled))
        self.card_anomalies.set_value(str(stats.anomaly_count))
        self.card_devices.set_value(str(stats.device_count))
        self.card_timeline.set_value(stats.timeline_span)
        self.card_integrity.set_value(stats.integrity_summary)
        self.integrity_label.setText(f"Integrity: {stats.integrity_summary}")
        self.btn_open_map.setEnabled(stats.gps_enabled > 0)
        self.btn_generate_report.setEnabled(stats.total_images > 0)

    def apply_filters(self) -> None:
        query = self.search_box.text().lower().strip()
        mode = self.filter_combo.currentText()
        filtered: List[EvidenceRecord] = []
        for record in self.case_manager.records:
            haystack = " ".join(
                [
                    record.evidence_id,
                    record.file_name,
                    record.device_model,
                    record.gps_display,
                    record.timestamp,
                    record.software,
                ]
            ).lower()
            if query and query not in haystack:
                continue
            if mode == "Has GPS" and not record.has_gps:
                continue
            if mode == "High Risk" and record.risk_level != "High":
                continue
            if mode == "Medium Risk" and record.risk_level != "Medium":
                continue
            if mode == "Low Risk" and record.risk_level != "Low":
                continue
            filtered.append(record)

        self.filtered_records = filtered
        self.populate_table(filtered)
        if filtered:
            self.table.selectRow(0)
        else:
            self.clear_details()

    def selected_record(self) -> EvidenceRecord | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        evidence_id_item = self.table.item(row, 0)
        if evidence_id_item is None:
            return None
        evidence_id = evidence_id_item.text()
        for record in self.case_manager.records:
            if record.evidence_id == evidence_id:
                return record
        return None

    def clear_details(self) -> None:
        self.current_preview_pixmap = None
        self.image_preview.clear()
        self.image_preview.setText("Select an evidence item to inspect the preview, metadata, and investigation notes.")
        self.summary_text.clear()
        self.metadata_view.clear()
        self.note_editor.clear()
        self.timeline_text.setPlaceholderText("Timeline output will appear here after evidence is loaded.")

    def populate_details(self) -> None:
        record = self.selected_record()
        if not record:
            self.clear_details()
            return

        pixmap = QPixmap(str(record.file_path))
        self.current_preview_pixmap = pixmap if not pixmap.isNull() else None
        self._render_preview()

        reasons_html = "".join(f"<li>{reason}</li>" for reason in record.anomaly_reasons)
        gps_text = record.gps_display if record.has_gps else "Unavailable"
        summary_html = f"""
        <div style='line-height:1.55;'>
            <div style='font-size:16pt; font-weight:800; color:#7fd9ff; margin-bottom:8px;'>Evidence Intelligence Summary</div>
            <div><b>Evidence ID:</b> {record.evidence_id}</div>
            <div><b>File:</b> {record.file_name}</div>
            <div><b>Timestamp:</b> {record.timestamp}</div>
            <div><b>Device:</b> {record.device_model}</div>
            <div><b>Software:</b> {record.software}</div>
            <div><b>Resolution:</b> {record.width} × {record.height}</div>
            <div><b>GPS:</b> {gps_text}</div>
            <div><b>Suspicion Score:</b> {record.suspicion_score}/100 &nbsp;&nbsp; <b>Risk:</b> {record.risk_level}</div>
            <div><b>Integrity:</b> {record.integrity_status}</div>
            <div style='margin-top:10px; font-weight:700; color:#b9d9f6;'>Key Findings</div>
            <ul style='margin-top:6px;'>{reasons_html}</ul>
        </div>
        """
        self.summary_text.setHtml(summary_html)

        metadata_lines = [
            f"Evidence ID: {record.evidence_id}",
            f"Path: {record.file_path}",
            f"Imported: {record.imported_at}",
            f"Dimensions: {record.width} x {record.height}",
            f"Timestamp: {record.timestamp}",
            f"Device: {record.device_model}",
            f"Software: {record.software}",
            f"GPS: {record.gps_display}",
            f"SHA-256: {record.sha256}",
            f"MD5: {record.md5}",
            "",
            "--- EXIF / METADATA ---",
        ]
        if record.exif:
            metadata_lines.extend([f"{key}: {value}" for key, value in sorted(record.exif.items())])
        else:
            metadata_lines.append("No embedded EXIF metadata extracted from this file.")
        self.metadata_view.setPlainText("\n".join(metadata_lines))
        self.note_editor.setPlainText(record.note)

    def _render_preview(self) -> None:
        if not self.current_preview_pixmap or self.current_preview_pixmap.isNull():
            self.image_preview.setText("Preview unavailable for the selected evidence.")
            return

        viewport = self.image_scroll.viewport().size()
        target_width = max(300, viewport.width() - 30)
        target_height = max(280, viewport.height() - 30)
        scaled = self.current_preview_pixmap.scaled(
            target_width,
            target_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.image_preview.setPixmap(scaled)

    def populate_timeline(self) -> None:
        if not self.case_manager.records:
            self.timeline_text.setPlainText("No evidence loaded yet.")
            return

        lines = ["EVENT TIMELINE", "=" * 72]
        sorted_records = sorted(self.case_manager.records, key=lambda rec: rec.timestamp)
        for record in sorted_records:
            lines.append(
                f"{record.timestamp:<22} | {record.evidence_id:<8} | Score {record.suspicion_score:<3} | {record.risk_level:<6} | {record.file_name}"
            )
            lines.append(f"    GPS: {record.gps_display}")
            for reason in record.anomaly_reasons:
                lines.append(f"    - {reason}")
            if record.note:
                lines.append(f"    Analyst note: {record.note}")
            lines.append("")
        self.timeline_text.setPlainText("\n".join(lines))

    def populate_custody_log(self) -> None:
        self.custody_text.setPlainText(self.case_manager.export_chain_of_custody())

    def save_note(self) -> None:
        record = self.selected_record()
        if not record:
            self._show_message("No Selection", "Select an evidence item first.", icon=QMessageBox.Warning)
            return
        note = self.note_editor.toPlainText().strip()
        self.case_manager.update_note(record.evidence_id, note)
        self._show_message("Note Saved", f"Investigator note saved for {record.evidence_id}.")
        self.populate_custody_log()
        self.populate_timeline()

    def open_map(self) -> None:
        if not self.case_manager.records:
            self._show_message("No Evidence", "Import images before opening the map.", icon=QMessageBox.Warning)
            return
        map_path = self.map_service.create_map(self.case_manager.records)
        if map_path is None:
            self._show_message("No GPS Data", "No GPS-enabled images are available to plot.")
            return
        webbrowser.open(map_path.as_uri())
        self.case_manager.db.log_action("CASE", "EXPORT_MAP", str(map_path))
        self.populate_custody_log()
        self._show_message("Map Generated", f"Interactive geolocation map opened:\n{map_path.name}")

    def generate_reports(self) -> None:
        if not self.case_manager.records:
            self._show_message("No Evidence", "Import images before generating reports.", icon=QMessageBox.Warning)
            return
        html_path = self.report_service.export_html(self.case_manager.records, "GT-2026-001")
        pdf_path = self.report_service.export_pdf(self.case_manager.records, "GT-2026-001")
        csv_path = self.report_service.export_csv(self.case_manager.records)
        json_path = self.report_service.export_json(self.case_manager.records)
        self.case_manager.db.log_action(
            "CASE",
            "EXPORT_REPORT",
            f"{html_path.name}, {pdf_path.name}, {csv_path.name}, {json_path.name}",
        )
        self.populate_custody_log()
        self._show_message(
            "Reports Generated",
            "Generated report package in the exports folder:\n"
            f"• {html_path.name}\n"
            f"• {pdf_path.name}\n"
            f"• {csv_path.name}\n"
            f"• {json_path.name}",
        )
        webbrowser.open(html_path.as_uri())

    def _show_message(self, title: str, text: str, icon=QMessageBox.Information) -> None:
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setIcon(icon)
        box.setText(text)
        box.setStandardButtons(QMessageBox.Ok)
        box.exec_()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._render_preview()
