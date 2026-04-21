from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import List

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QIcon, QPixmap
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
    QSplitter,
    QStyle,
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
from .widgets import ChartCard, ResizableImageLabel, StatCard, TerminalView


class GeoTraceMainWindow(QMainWindow):
    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.project_root = project_root
        self.export_dir = project_root / "exports"
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.case_manager = CaseManager(project_root)
        self.map_service = MapService(self.export_dir)
        self.report_service = ReportService(self.export_dir)
        self.records: List[EvidenceRecord] = []
        self.filtered_records: List[EvidenceRecord] = []
        self.current_preview_pixmap: QPixmap | None = None
        self.current_map_path: Path | None = None
        self.assets_dir = project_root / "assets"

        self.setWindowTitle("GeoTrace Forensics X — Image Metadata & Geolocation Analysis")
        self.resize(1780, 1080)
        self.setMinimumSize(1460, 900)
        self.setStyleSheet(APP_STYLESHEET)
        icon_path = self.assets_dir / "app_icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
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

        self.setCentralWidget(central)

    def _build_header(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("HeaderFrame")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(8)

        title = QLabel("GeoTrace Forensics X")
        title.setObjectName("TitleLabel")
        subtitle = QLabel(
            "Image intelligence command center for EXIF extraction, timestamp recovery, geolocation analysis, duplicate clustering, anomaly scoring, and forensic reporting."
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
        self.formats_badge = QLabel("Formats: JPG • JPEG • PNG • TIFF • WEBP • BMP • GIF • HEIC")
        self.formats_badge.setObjectName("BadgeLabel")
        for badge in [self.case_badge, self.mode_badge, self.export_badge, self.formats_badge]:
            badge_row.addWidget(badge)
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
        self.method_label = QLabel("Workflow: Acquire → Verify → Extract → Correlate → Score → Report")
        self.method_label.setObjectName("SubtitleLabel")
        for widget in [self.case_label, self.status_label, self.integrity_label, self.method_label]:
            right.addWidget(widget, alignment=Qt.AlignRight)
        right.addStretch(1)

        layout.addLayout(left, 3)
        layout.addLayout(right, 2)
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
        self.card_duplicates = StatCard("Duplicate Clusters")
        self.card_avg_score = StatCard("Average Score")

        cards = [
            self.card_total,
            self.card_gps,
            self.card_anomalies,
            self.card_devices,
            self.card_timeline,
            self.card_integrity,
            self.card_duplicates,
            self.card_avg_score,
        ]
        positions = [(0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 1), (1, 2), (1, 3)]
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
        self.btn_load_images.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btn_load_images.clicked.connect(self.import_images)

        self.btn_load_folder = QPushButton("Import Folder")
        self.btn_load_folder.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.btn_load_folder.clicked.connect(self.import_folder)

        self.btn_generate_report = QPushButton("Generate Reports")
        self.btn_generate_report.setIcon(self.style().standardIcon(QStyle.SP_DriveFDIcon))
        self.btn_generate_report.clicked.connect(self.generate_reports)

        self.btn_open_map = QPushButton("Open Geolocation Map")
        self.btn_open_map.setObjectName("GhostButton")
        self.btn_open_map.setIcon(self.style().standardIcon(QStyle.SP_DialogHelpButton))
        self.btn_open_map.clicked.connect(self.open_map)
        self.btn_open_map.setEnabled(False)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search by evidence ID, filename, source type, device, GPS, or software...")
        self.search_box.textChanged.connect(self.apply_filters)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(
            [
                "All Evidence",
                "Has GPS",
                "High Risk",
                "Medium Risk",
                "Low Risk",
                "Screenshots / Exports",
                "Camera Photos",
                "Edited / Exported",
                "Duplicate Cluster",
            ]
        )
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
        splitter.setSizes([460, 1220])
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

        self.table = QTableWidget(0, 9)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setHorizontalHeaderLabels(
            ["Evidence ID", "File Name", "Timestamp", "Source", "Device", "GPS", "Score", "Risk", "Integrity"]
        )
        self.table.itemSelectionChanged.connect(self.populate_details)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for idx in [2, 3, 4, 5, 6, 7, 8]:
            header.setSectionResizeMode(idx, QHeaderView.ResizeToContents)
        self.table.setSortingEnabled(True)

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
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._build_preview_tab(), "Preview")
        self.tabs.addTab(self._build_metadata_tab(), "Metadata")
        self.tabs.addTab(self._build_geo_tab(), "Geo")
        self.tabs.addTab(self._build_timeline_tab(), "Timeline")
        self.tabs.addTab(self._build_insights_tab(), "Insights")
        self.tabs.addTab(self._build_custody_tab(), "Custody")
        layout.addWidget(self.tabs)
        return frame

    def _build_preview_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)

        preview_shell = QFrame()
        preview_shell.setObjectName("PanelFrame")
        preview_layout = QVBoxLayout(preview_shell)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        preview_layout.setSpacing(8)
        self.image_preview = ResizableImageLabel(
            "Select an evidence item to inspect preview, metadata, and image intelligence.",
            min_height=620,
        )
        self.image_preview.setStyleSheet(
            "border: 1px dashed #2b527e; border-radius: 16px; background:#06111d; padding: 12px;"
        )
        preview_layout.addWidget(self.image_preview, 1)

        terminal_shell = QFrame()
        terminal_shell.setObjectName("PanelFrame")
        terminal_layout = QVBoxLayout(terminal_shell)
        terminal_layout.setContentsMargins(12, 12, 12, 12)
        terminal_layout.setSpacing(8)
        summary_label = QLabel("Evidence Intelligence Terminal")
        summary_label.setObjectName("SectionLabel")
        self.summary_text = TerminalView("Executive evidence summary will appear here.")
        self.summary_text.setMinimumWidth(420)
        terminal_layout.addWidget(summary_label)
        terminal_layout.addWidget(self.summary_text, 1)

        split.addWidget(preview_shell)
        split.addWidget(terminal_shell)
        split.setSizes([740, 460])

        layout.addWidget(split, 1)
        return widget

    def _build_metadata_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        split = QSplitter(Qt.Vertical)
        split.setChildrenCollapsible(False)

        self.metadata_view = TerminalView("Metadata extraction details will appear here.")
        metadata_shell = QFrame()
        metadata_shell.setObjectName("PanelFrame")
        metadata_layout = QVBoxLayout(metadata_shell)
        metadata_layout.setContentsMargins(12, 12, 12, 12)
        metadata_label = QLabel("Metadata Terminal")
        metadata_label.setObjectName("SectionLabel")
        metadata_layout.addWidget(metadata_label)
        metadata_layout.addWidget(self.metadata_view, 1)

        notes_shell = QFrame()
        notes_shell.setObjectName("PanelFrame")
        notes_layout = QVBoxLayout(notes_shell)
        notes_layout.setContentsMargins(12, 12, 12, 12)
        notes_layout.setSpacing(8)
        notes_label = QLabel("Investigator Notes")
        notes_label.setObjectName("SectionLabel")
        self.note_editor = QTextEdit()
        self.note_editor.setPlaceholderText("Add analyst observations, significance, correlation ideas, or follow-up questions for the selected evidence item...")
        self.note_editor.setMaximumHeight(140)
        save_button = QPushButton("Save Investigator Note")
        save_button.clicked.connect(self.save_note)
        notes_layout.addWidget(notes_label)
        notes_layout.addWidget(self.note_editor)
        notes_layout.addWidget(save_button)

        split.addWidget(metadata_shell)
        split.addWidget(notes_shell)
        split.setSizes([560, 180])

        layout.addWidget(split, 1)
        return widget

    def _build_geo_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        status = QLabel("Location intelligence, GPS parsing, and OSINT leads")
        status.setObjectName("MutedLabel")
        top_row.addWidget(status)
        top_row.addStretch(1)
        self.geo_open_map_btn = QPushButton("Open Current Map in Browser")
        self.geo_open_map_btn.clicked.connect(self.open_map)
        self.geo_open_map_btn.setEnabled(False)
        top_row.addWidget(self.geo_open_map_btn)

        self.geo_text = TerminalView("GPS findings, altitude, map availability, and investigation leads will appear here.")
        layout.addLayout(top_row)
        layout.addWidget(self.geo_text, 1)
        return widget

    def _build_timeline_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        self.timeline_text = TerminalView("Timeline output will appear here after evidence is loaded.")
        layout.addWidget(self.timeline_text, 1)
        return widget

    def _build_insights_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        chart_grid = QGridLayout()
        chart_grid.setHorizontalSpacing(12)
        chart_grid.setVerticalSpacing(12)
        self.chart_sources = ChartCard("Source-Type Distribution")
        self.chart_risks = ChartCard("Risk Distribution")
        self.chart_duplicates = ChartCard("Duplicate & GPS Intelligence")
        chart_grid.addWidget(self.chart_sources, 0, 0)
        chart_grid.addWidget(self.chart_risks, 0, 1)
        chart_grid.addWidget(self.chart_duplicates, 1, 0, 1, 2)
        chart_grid.setColumnStretch(0, 1)
        chart_grid.setColumnStretch(1, 1)
        layout.addLayout(chart_grid, 1)
        return widget

    def _build_custody_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Evidence acquisition and action log"))
        controls.addStretch(1)
        refresh_button = QPushButton("Refresh Custody Log")
        refresh_button.clicked.connect(self.populate_custody_log)
        controls.addWidget(refresh_button)
        self.custody_text = TerminalView("No chain-of-custody activity logged yet.")
        layout.addLayout(controls)
        layout.addWidget(self.custody_text, 1)
        return widget

    def import_images(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Evidence Images",
            str(self.project_root),
            "Images (*.jpg *.jpeg *.png *.tif *.tiff *.webp *.bmp *.gif *.heic *.heif)",
        )
        if files:
            self._load_paths([Path(file) for file in files])

    def import_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Evidence Folder", str(self.project_root))
        if folder:
            self._load_paths([Path(folder)])

    def _load_paths(self, paths: List[Path]) -> None:
        self.progress_bar.setFormat("Acquiring evidence…")
        self.progress_bar.setValue(10)
        self.records = self.case_manager.load_images(paths)
        self.progress_bar.setFormat("Extracting metadata…")
        self.progress_bar.setValue(55)
        self.filtered_records = list(self.records)
        self.populate_table(self.filtered_records)
        self.refresh_dashboard()
        self.populate_timeline()
        self.populate_custody_log()
        self.current_map_path = self.map_service.create_map(self.records)
        self.btn_open_map.setEnabled(self.current_map_path is not None)
        self.geo_open_map_btn.setEnabled(self.current_map_path is not None)
        self.update_charts()
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Analysis complete")
        if self.filtered_records:
            self.table.selectRow(0)
        else:
            self.clear_details()
        self.status_label.setText(f"Status: {len(self.records)} evidence items analyzed")
        self.inventory_meta.setText(f"Loaded {len(self.records)} evidence items.")

    def populate_table(self, records: List[EvidenceRecord]) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for record in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                record.evidence_id,
                record.file_name,
                self._display_timestamp(record.timestamp),
                record.source_type,
                record.device_model,
                record.gps_display,
                str(record.suspicion_score),
                record.risk_level,
                record.integrity_status,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if column in {6, 7, 8}:
                    item.setTextAlignment(Qt.AlignCenter)
                if column == 7:
                    if value == "High":
                        item.setForeground(QColor("#ff8ba0"))
                    elif value == "Medium":
                        item.setForeground(QColor("#ffd166"))
                    else:
                        item.setForeground(QColor("#8ef5c8"))
                if column == 8:
                    item.setForeground(QColor("#9fe8ff"))
                self.table.setItem(row, column, item)
            self.table.setRowHeight(row, 42)

        self.table.setSortingEnabled(True)
        if self.table.rowCount() == 0:
            self.inventory_meta.setText("No results match the current filter.")
        else:
            self.inventory_meta.setText(f"Showing {len(records)} evidence items.")

    def _display_timestamp(self, timestamp: str) -> str:
        if timestamp == "Unknown":
            return timestamp
        return timestamp.replace(":", "-", 2)

    def refresh_dashboard(self) -> None:
        stats = self.case_manager.build_stats()
        self.card_total.set_value(str(stats.total_images))
        self.card_gps.set_value(str(stats.gps_enabled))
        self.card_anomalies.set_value(str(stats.anomaly_count))
        self.card_devices.set_value(str(stats.device_count))
        self.card_timeline.set_value(stats.timeline_span)
        self.card_integrity.set_value(stats.integrity_summary)
        self.card_duplicates.set_value(str(stats.duplicates_count))
        self.card_avg_score.set_value(str(stats.avg_score))
        self.integrity_label.setText(f"Integrity: {stats.integrity_summary}")
        self.btn_open_map.setEnabled(stats.gps_enabled > 0)
        self.geo_open_map_btn.setEnabled(stats.gps_enabled > 0)
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
                    record.source_type,
                    record.duplicate_group,
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
            if mode == "Screenshots / Exports" and not (
                "Screenshot" in record.source_type or "Messaging" in record.source_type
            ):
                continue
            if mode == "Camera Photos" and record.source_type != "Camera Photo":
                continue
            if mode == "Edited / Exported" and record.source_type != "Edited / Exported":
                continue
            if mode == "Duplicate Cluster" and not record.duplicate_group:
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
        self.image_preview.clear_source(
            "Select an evidence item to inspect preview, metadata, geolocation, and OSINT leads."
        )
        self.summary_text.clear()
        self.metadata_view.clear()
        self.note_editor.clear()
        self.geo_text.clear()
        self.timeline_text.setPlainText("Timeline output will appear here after evidence is loaded.")

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self.current_preview_pixmap is not None:
            self.image_preview.set_source_pixmap(self.current_preview_pixmap)

    def populate_details(self) -> None:
        record = self.selected_record()
        if record is None:
            self.clear_details()
            return

        self.note_editor.setPlainText(record.note or "")
        pixmap = QPixmap(str(record.file_path))
        self.current_preview_pixmap = pixmap if not pixmap.isNull() else None
        if self.current_preview_pixmap is not None:
            self.image_preview.set_source_pixmap(self.current_preview_pixmap)
        else:
            self.image_preview.clear_source("Preview unavailable for the selected evidence item.")

        self.summary_text.setPlainText(self._build_summary_text(record))
        self.metadata_view.setPlainText(self._build_metadata_text(record))
        self.geo_text.setPlainText(self._build_geo_text(record))

    def _build_summary_text(self, record: EvidenceRecord) -> str:
        lines = [
            "[ EXECUTIVE EVIDENCE SUMMARY ]",
            "=" * 88,
            f"Evidence ID        : {record.evidence_id}",
            f"File               : {record.file_name}",
            f"Path               : {record.file_path}",
            f"Source Type        : {record.source_type}",
            f"Timestamp          : {record.timestamp}",
            f"Timestamp Source   : {record.timestamp_source}",
            f"Device / Camera    : {record.device_model}",
            f"Software Tag       : {record.software}",
            f"Dimensions         : {record.dimensions}",
            f"Format / Mode      : {record.format_name} / {record.color_mode}",
            f"GPS                : {record.gps_display}",
            f"Risk / Score       : {record.risk_level} / {record.suspicion_score}",
            f"Confidence         : {record.confidence_score}",
            f"Integrity          : {record.integrity_status}",
            f"Duplicate Cluster  : {record.duplicate_group or 'None'}",
            "",
            "[ KEY FINDINGS ]",
            "-" * 88,
        ]
        lines.extend([f"- {item}" for item in (record.anomaly_reasons or ["No major metadata anomalies were detected."])])
        lines.extend([
            "",
            "[ FOLLOW-UP LEADS ]",
            "-" * 88,
        ])
        lines.extend([f"- {lead}" for lead in record.osint_leads])
        return "\n".join(lines)

    def _build_metadata_text(self, record: EvidenceRecord) -> str:
        sections = [
            "[ METADATA TERMINAL ]",
            "=" * 100,
            f"File Path              : {record.file_path}",
            f"File Size              : {record.file_size:,} bytes",
            f"Format                 : {record.format_name}",
            f"Dimensions             : {record.dimensions}",
            f"Color Mode             : {record.color_mode}",
            f"Alpha Channel          : {'Yes' if record.has_alpha else 'No'}",
            f"DPI                    : {record.dpi}",
            f"Timestamp              : {record.timestamp}",
            f"Timestamp Source       : {record.timestamp_source}",
            f"Filesystem Created     : {record.created_time}",
            f"Filesystem Modified    : {record.modified_time}",
            f"Source Type            : {record.source_type}",
            f"Camera / Device        : {record.device_model}",
            f"Camera Make            : {record.camera_make}",
            f"Software               : {record.software}",
            f"Orientation            : {record.orientation}",
            f"Lens Model             : {record.lens_model}",
            f"ISO                    : {record.iso}",
            f"Exposure Time          : {record.exposure_time}",
            f"F-Number               : {record.f_number}",
            f"Focal Length           : {record.focal_length}",
            f"Artist                 : {record.artist}",
            f"Copyright              : {record.copyright_notice}",
            f"GPS                    : {record.gps_display}",
            f"GPS Altitude           : {f'{record.gps_altitude:.2f} m' if record.gps_altitude is not None else 'Unavailable'}",
            f"SHA-256                : {record.sha256}",
            f"MD5                    : {record.md5}",
            f"Perceptual Hash        : {record.perceptual_hash}",
            f"Duplicate Cluster      : {record.duplicate_group or 'None'}",
            f"Integrity              : {record.integrity_status}",
        ]
        if record.exif:
            sections.extend(["", "[ EMBEDDED EXIF TAGS ]", "-" * 100])
            for key, value in sorted(record.exif.items()):
                sections.append(f"{key:<26}: {value}")
        return "\n".join(sections)

    def _build_geo_text(self, record: EvidenceRecord) -> str:
        lines = [
            "[ GEOLOCATION & OSINT LEADS ]",
            "=" * 92,
            f"Evidence ID           : {record.evidence_id}",
            f"GPS Coordinates       : {record.gps_display}",
            f"Altitude              : {f'{record.gps_altitude:.2f} m' if record.gps_altitude is not None else 'Unavailable'}",
            f"Map Package           : {'Available' if self.current_map_path else 'Not generated'}",
            f"Source Type           : {record.source_type}",
            f"Timestamp             : {record.timestamp} ({record.timestamp_source})",
            "",
            "[ RECOMMENDED FOLLOW-UP ]",
            "-" * 92,
        ]
        lines.extend([f"- {lead}" for lead in record.osint_leads])
        if record.has_gps:
            lines.extend([
                "",
                "[ MAP WORKFLOW ]",
                "-" * 92,
                "1. Validate recovered coordinates on the interactive map.",
                "2. Compare the point with known venues, transit corridors, or CCTV coverage.",
                "3. Correlate the recovered time with witness, chat, or upload timestamps.",
            ])
        return "\n".join(lines)

    def populate_timeline(self) -> None:
        if not self.case_manager.records:
            self.timeline_text.setPlainText("No evidence loaded yet.")
            return
        ordered = sorted(self.case_manager.records, key=lambda r: (r.timestamp == "Unknown", r.timestamp))
        lines = [
            "[ EVENT TIMELINE ]",
            "=" * 100,
        ]
        for record in ordered:
            lines.append(
                f"{record.timestamp:<19} | {record.evidence_id:<8} | {record.risk_level:<6} | Score {record.suspicion_score:<3} | {record.source_type}"
            )
            lines.append(f"  File      : {record.file_name}")
            lines.append(f"  GPS       : {record.gps_display}")
            lines.append(f"  Device    : {record.device_model}")
            lines.append(f"  Time Src  : {record.timestamp_source}")
            for reason in record.anomaly_reasons[:3]:
                lines.append(f"  Finding   : {reason}")
            if record.duplicate_group:
                lines.append(f"  Duplicate : {record.duplicate_group}")
            lines.append("-" * 100)
        self.timeline_text.setPlainText("\n".join(lines))

    def populate_custody_log(self) -> None:
        log = self.case_manager.export_chain_of_custody()
        self.custody_text.setPlainText("[ CHAIN OF CUSTODY ]\n" + "=" * 92 + "\n" + log)

    def save_note(self) -> None:
        record = self.selected_record()
        if record is None:
            self.show_info("No Selection", "Select an evidence item before saving an investigator note.")
            return
        note = self.note_editor.toPlainText().strip()
        self.case_manager.update_note(record.evidence_id, note)
        record.note = note
        self.show_info("Note Saved", f"Investigator note updated for {record.evidence_id}.")
        self.populate_details()
        self.populate_custody_log()

    def update_charts(self) -> None:
        records = self.case_manager.records
        if not records:
            for card in [self.chart_sources, self.chart_risks, self.chart_duplicates]:
                card.set_chart_pixmap(None, "Load evidence to generate charts.")
                card.caption.setText("")
            return

        source_counts: dict[str, int] = {}
        for record in records:
            source_counts[record.source_type] = source_counts.get(record.source_type, 0) + 1
        self._render_bar_chart(
            self.chart_sources,
            list(source_counts.keys()),
            list(source_counts.values()),
            "Evidence Count",
            "Distribution across screenshots, camera photos, messaging exports, and edited media.",
            self.export_dir / "chart_sources.png",
        )

        risk_order = ["Low", "Medium", "High"]
        risk_counts = [sum(1 for r in records if r.risk_level == risk) for risk in risk_order]
        self._render_bar_chart(
            self.chart_risks,
            risk_order,
            risk_counts,
            "Count",
            "Risk profile after context-aware anomaly scoring.",
            self.export_dir / "chart_risks.png",
        )

        labels = ["GPS Enabled", "No GPS", "Duplicate Clustered", "Unique"]
        values = [
            sum(1 for r in records if r.has_gps),
            sum(1 for r in records if not r.has_gps),
            sum(1 for r in records if r.duplicate_group),
            sum(1 for r in records if not r.duplicate_group),
        ]
        self._render_bar_chart(
            self.chart_duplicates,
            labels,
            values,
            "Count",
            "Coverage of location-enabled media and near-duplicate clustering intelligence.",
            self.export_dir / "chart_duplicate_gps.png",
            rotate_labels=True,
        )

    def _render_bar_chart(
        self,
        card: ChartCard,
        labels: List[str],
        values: List[int],
        ylabel: str,
        caption: str,
        output_path: Path,
        rotate_labels: bool = False,
    ) -> None:
        plt.close("all")
        fig, ax = plt.subplots(figsize=(8.8, 3.8), dpi=170)
        fig.patch.set_facecolor("#06111d")
        ax.set_facecolor("#06111d")
        colors = ["#20beff", "#4bdfff", "#7ed8ff", "#2386d1"]
        bars = ax.bar(range(len(labels)), values, color=colors[: len(labels)], edgecolor="#9ae8ff", linewidth=0.5)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(
            labels,
            rotation=18 if rotate_labels else 0,
            ha="right" if rotate_labels else "center",
            color="#e8f4ff",
            fontsize=9,
        )
        ax.tick_params(axis="y", colors="#cce7ff", labelsize=9)
        ax.set_ylabel(ylabel, color="#cce7ff", fontsize=10)
        ax.margins(x=0.08)
        for spine in ax.spines.values():
            spine.set_color("#2f5c8e")
        ax.grid(axis="y", alpha=0.18, color="#7ecfff")
        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.05,
                str(value),
                ha="center",
                va="bottom",
                color="#ffffff",
                fontsize=9,
                fontweight="bold",
            )
        fig.tight_layout(pad=1.2)
        fig.savefig(output_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close(fig)
        pixmap = QPixmap(str(output_path))
        card.set_chart_pixmap(pixmap, "Chart unavailable")
        card.caption.setText(caption)

    def open_map(self) -> None:
        if self.current_map_path is None:
            self.current_map_path = self.map_service.create_map(self.case_manager.records)
        if self.current_map_path is None:
            self.show_info("No GPS Data", "No GPS-enabled images are available to plot.")
            return
        webbrowser.open(self.current_map_path.as_uri())

    def generate_reports(self) -> None:
        if not self.case_manager.records:
            self.show_info("No Evidence", "Import evidence before generating reports.")
            return
        custody = self.case_manager.export_chain_of_custody()
        html_path = self.report_service.export_html(self.case_manager.records, "GT-2026-001", custody_log=custody)
        pdf_path = self.report_service.export_pdf(self.case_manager.records, "GT-2026-001")
        csv_path = self.report_service.export_csv(self.case_manager.records)
        json_path = self.report_service.export_json(self.case_manager.records)
        self.export_badge.setText("Exports: Generated")
        self.show_info(
            "Reports Generated",
            "Generated report package in the exports folder:\n"
            f"• {html_path.name}\n"
            f"• {pdf_path.name}\n"
            f"• {csv_path.name}\n"
            f"• {json_path.name}",
        )

    def show_info(self, title: str, message: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QMessageBox.Ok)
        box.exec_()
