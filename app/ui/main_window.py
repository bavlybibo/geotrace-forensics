from __future__ import annotations

import webbrowser
from datetime import datetime
from pathlib import Path
from typing import List

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QColor, QDesktopServices, QIcon, QPixmap
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

from app.core.anomalies import parse_timestamp
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
        self.resize(1840, 1120)
        self.setMinimumSize(1500, 920)
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
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        root.addWidget(self._build_header())
        root.addWidget(self._build_stat_cards())
        root.addWidget(self._build_analyst_board())
        root.addWidget(self._build_controls())
        root.addWidget(self._build_workspace(), 1)

        self.setCentralWidget(central)

    def _build_header(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("HeaderFrame")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(18)

        left = QVBoxLayout()
        left.setSpacing(8)
        title = QLabel("GeoTrace Forensics X")
        title.setObjectName("TitleLabel")
        subtitle = QLabel(
            "World-class image intelligence workspace for EXIF extraction, timestamp recovery, geolocation triage, duplicate correlation, analyst-style verdicting, and presentation-ready forensic reporting."
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

        layout.addLayout(left, 4)
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

        self.card_total.clicked.connect(lambda: self._activate_filter("All Evidence"))
        self.card_gps.clicked.connect(lambda: self._activate_filter("Has GPS"))
        self.card_anomalies.clicked.connect(lambda: self.tabs.setCurrentWidget(self.timeline_tab))
        self.card_devices.clicked.connect(lambda: self.tabs.setCurrentWidget(self.metadata_tab))
        self.card_timeline.clicked.connect(lambda: self.tabs.setCurrentWidget(self.timeline_tab))
        self.card_integrity.clicked.connect(lambda: self.tabs.setCurrentWidget(self.custody_tab))
        self.card_duplicates.clicked.connect(lambda: self._activate_filter("Duplicate Cluster"))
        self.card_avg_score.clicked.connect(lambda: self.tabs.setCurrentWidget(self.insights_tab))
        return frame

    def _build_analyst_board(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("PanelFrame")
        layout = QGridLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        self.case_assessment_view = TerminalView("Case-level assessment will appear here after loading evidence.")
        self.selection_verdict_view = TerminalView("Select an evidence item to load the analyst verdict engine.")
        self.priority_view = TerminalView("Case priorities and next best steps will appear here.")

        layout.addWidget(self._shell("Case Assessment", self.case_assessment_view), 0, 0)
        layout.addWidget(self._shell("Selected Evidence Verdict", self.selection_verdict_view), 0, 1)
        layout.addWidget(self._shell("Investigation Priorities", self.priority_view), 0, 2)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)
        return frame

    def _shell(self, title: str, body: QWidget) -> QWidget:
        frame = QFrame()
        frame.setObjectName("PanelFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        lbl = QLabel(title)
        lbl.setObjectName("SectionLabel")
        layout.addWidget(lbl)
        layout.addWidget(body, 1)
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
        self.search_box.setPlaceholderText("Search by evidence ID, filename, source type, device, GPS, software, or verdict signal...")
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

    def _build_workspace(self) -> QWidget:
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_inventory_panel())
        splitter.addWidget(self._build_analysis_panel())
        splitter.setSizes([320, 780])
        return splitter

    def _build_inventory_panel(self) -> QWidget:
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
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        self.table.setSortingEnabled(True)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        layout.addLayout(heading_row)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.table, 1)
        return frame

    def _build_analysis_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("PanelFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.preview_tab = self._build_preview_tab()
        self.metadata_tab = self._build_metadata_tab()
        self.geo_tab = self._build_geo_tab()
        self.timeline_tab = self._build_timeline_tab()
        self.insights_tab = self._build_insights_tab()
        self.custody_tab = self._build_custody_tab()
        self.tabs.addTab(self.preview_tab, "Preview")
        self.tabs.addTab(self.metadata_tab, "Metadata")
        self.tabs.addTab(self.geo_tab, "Geo")
        self.tabs.addTab(self.timeline_tab, "Timeline")
        self.tabs.addTab(self.insights_tab, "Insights")
        self.tabs.addTab(self.custody_tab, "Custody")
        layout.addWidget(self.tabs)
        return frame

    def _build_preview_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        title = QLabel("Active Evidence Preview")
        title.setObjectName("SectionLabel")
        toolbar.addWidget(title)
        toolbar.addStretch(1)

        self.btn_zoom_out = QPushButton("−")
        self.btn_zoom_out.clicked.connect(lambda: self.image_preview.zoom_out())
        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.clicked.connect(lambda: self.image_preview.zoom_in())
        self.btn_zoom_fit = QPushButton("Fit")
        self.btn_zoom_fit.clicked.connect(lambda: self.image_preview.fit_to_window())
        self.btn_zoom_reset = QPushButton("100%")
        self.btn_zoom_reset.clicked.connect(lambda: self.image_preview.reset_zoom())
        self.btn_open_external = QPushButton("Open Original")
        self.btn_open_external.clicked.connect(self.open_selected_file)
        for btn in [self.btn_zoom_out, self.btn_zoom_in, self.btn_zoom_fit, self.btn_zoom_reset, self.btn_open_external]:
            toolbar.addWidget(btn)

        content = QSplitter(Qt.Horizontal)
        content.setChildrenCollapsible(False)

        preview_shell = QFrame()
        preview_shell.setObjectName("PanelFrame")
        preview_layout = QVBoxLayout(preview_shell)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        preview_layout.setSpacing(8)
        self.image_preview = ResizableImageLabel(
            "Select an evidence item to inspect preview, metadata, geolocation, and analyst verdict.",
            min_height=620,
        )
        self.image_preview.setStyleSheet(
            "border: 1px dashed #2b527e; border-radius: 16px; background:#04101b; padding: 12px;"
        )
        preview_layout.addWidget(self.image_preview, 1)

        side_shell = QFrame()
        side_shell.setObjectName("PanelFrame")
        side_layout = QVBoxLayout(side_shell)
        side_layout.setContentsMargins(12, 12, 12, 12)
        side_layout.setSpacing(10)

        badges = QGridLayout()
        badges.setHorizontalSpacing(8)
        badges.setVerticalSpacing(8)
        self.badge_source = self._micro_badge("Source: —")
        self.badge_time = self._micro_badge("Time Source: —")
        self.badge_risk = self._micro_badge("Risk: —")
        self.badge_conf = self._micro_badge("Confidence: —")
        self.badge_dup = self._micro_badge("Duplicate: —")
        self.badge_format = self._micro_badge("Format: —")
        for idx, badge in enumerate([self.badge_source, self.badge_time, self.badge_risk, self.badge_conf, self.badge_dup, self.badge_format]):
            badges.addWidget(badge, idx // 2, idx % 2)

        verdict_label = QLabel("Analyst Verdict Terminal")
        verdict_label.setObjectName("SectionLabel")
        self.summary_text = TerminalView("The selected evidence will be summarized here with analyst-style reasoning.")
        side_layout.addLayout(badges)
        side_layout.addWidget(verdict_label)
        side_layout.addWidget(self.summary_text, 1)

        content.addWidget(preview_shell)
        content.addWidget(side_shell)
        content.setSizes([980, 560])

        layout.addLayout(toolbar)
        layout.addWidget(content, 1)
        return widget

    def _micro_badge(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("MicroBadge")
        lbl.setWordWrap(True)
        return lbl

    def _build_metadata_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        split = QSplitter(Qt.Vertical)
        split.setChildrenCollapsible(False)

        self.metadata_view = TerminalView("Metadata extraction details will appear here.")
        metadata_shell = self._shell("Metadata Terminal", self.metadata_view)

        notes_shell = QFrame()
        notes_shell.setObjectName("PanelFrame")
        notes_layout = QVBoxLayout(notes_shell)
        notes_layout.setContentsMargins(12, 12, 12, 12)
        notes_layout.setSpacing(8)
        notes_label = QLabel("Investigator Notes")
        notes_label.setObjectName("SectionLabel")
        self.note_editor = QTextEdit()
        self.note_editor.setPlaceholderText("Add analyst observations, significance, correlation ideas, or follow-up questions for the selected evidence item...")
        save_button = QPushButton("Save Investigator Note")
        save_button.clicked.connect(self.save_note)
        notes_layout.addWidget(notes_label)
        notes_layout.addWidget(self.note_editor, 1)
        notes_layout.addWidget(save_button)

        split.addWidget(metadata_shell)
        split.addWidget(notes_shell)
        split.setSizes([520, 210])
        layout.addWidget(split, 1)
        return widget

    def _build_geo_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        badge_row = QGridLayout()
        badge_row.setHorizontalSpacing(8)
        badge_row.setVerticalSpacing(8)
        self.geo_badge_status = self._micro_badge("GPS State: —")
        self.geo_badge_coords = self._micro_badge("Coordinates: —")
        self.geo_badge_altitude = self._micro_badge("Altitude: —")
        self.geo_badge_map = self._micro_badge("Map Package: —")
        for idx, badge in enumerate([self.geo_badge_status, self.geo_badge_coords, self.geo_badge_altitude, self.geo_badge_map]):
            badge_row.addWidget(badge, 0, idx)

        top_row = QHBoxLayout()
        top_row.addLayout(badge_row, 1)
        self.geo_open_map_btn = QPushButton("Open Current Map in Browser")
        self.geo_open_map_btn.clicked.connect(self.open_map)
        self.geo_open_map_btn.setEnabled(False)
        top_row.addWidget(self.geo_open_map_btn)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        self.geo_text = TerminalView("GPS findings and coordinate intelligence will appear here.")
        self.geo_leads_text = TerminalView("OSINT follow-up ideas and location pivots will appear here.")
        split.addWidget(self._shell("Geo Terminal", self.geo_text))
        split.addWidget(self._shell("Location Investigation Leads", self.geo_leads_text))
        split.setSizes([760, 520])

        layout.addLayout(top_row)
        layout.addWidget(split, 1)
        return widget

    def _build_timeline_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        split = QSplitter(Qt.Vertical)
        split.setChildrenCollapsible(False)
        self.timeline_chart = ChartCard(
            "Timeline Reconstruction",
            "Recovered timestamps are plotted chronologically to expose burst activity, gaps, and ordering confidence.",
        )
        self.timeline_text = TerminalView("Timeline analysis will appear here after evidence is loaded.")
        split.addWidget(self.timeline_chart)
        split.addWidget(self._shell("Timeline Analyst Terminal", self.timeline_text))
        split.setSizes([360, 260])

        layout.addWidget(split, 1)
        return widget

    def _build_insights_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        top = QGridLayout()
        top.setHorizontalSpacing(12)
        top.setVerticalSpacing(12)
        self.chart_sources = ChartCard("Source-Type Distribution", "How the case media splits between screenshots, camera photos, exports, and edited files.")
        self.chart_risks = ChartCard("Risk Distribution", "How low, medium, and high-risk findings are distributed after context-aware scoring.")
        self.chart_geo = ChartCard("GPS & Duplication Coverage", "Coverage of location-bearing evidence and near-duplicate clustering.")
        top.addWidget(self.chart_sources, 0, 0)
        top.addWidget(self.chart_risks, 0, 1)
        top.addWidget(self.chart_geo, 1, 0)
        self.duplicate_terminal = TerminalView("Duplicate-cluster analysis will appear here.")
        top.addWidget(self._shell("Duplicate Cluster Overview", self.duplicate_terminal), 1, 1)
        top.setColumnStretch(0, 1)
        top.setColumnStretch(1, 1)
        layout.addLayout(top, 1)
        return widget

    def _build_custody_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Evidence acquisition and chain-of-custody activity"))
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
        self.progress_bar.setValue(45)
        self.filtered_records = list(self.records)
        self.populate_table(self.filtered_records)
        self.refresh_dashboard()
        self.current_map_path = self.map_service.create_map(self.records)
        self.btn_open_map.setEnabled(self.current_map_path is not None)
        self.geo_open_map_btn.setEnabled(self.current_map_path is not None)
        self.update_charts()
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
            self.table.setRowHeight(row, 38)

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
        self.case_assessment_view.setPlainText(self._build_case_assessment_text())
        self.priority_view.setPlainText(self._build_priority_text())

    def _activate_filter(self, label: str) -> None:
        self.filter_combo.setCurrentText(label)
        self.tabs.setCurrentWidget(self.insights_tab if label == "Duplicate Cluster" else self.preview_tab)
        self.apply_filters()

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
                    record.analyst_verdict,
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
            "Select an evidence item to inspect preview, metadata, geolocation, timeline, and analyst verdict."
        )
        self.summary_text.clear()
        self.metadata_view.clear()
        self.note_editor.clear()
        self.geo_text.clear()
        self.geo_leads_text.clear()
        self.timeline_text.setPlainText("Timeline analysis will appear here after evidence is loaded.")
        self.selection_verdict_view.setPlainText("Select an evidence item to load the analyst verdict engine.")
        self._set_badge_defaults()
        self._set_geo_defaults()
        self._set_preview_controls(False)

    def _set_preview_controls(self, enabled: bool) -> None:
        for btn in [self.btn_zoom_out, self.btn_zoom_in, self.btn_zoom_fit, self.btn_zoom_reset, self.btn_open_external]:
            btn.setEnabled(enabled)

    def _set_badge_defaults(self) -> None:
        self.badge_source.setText("Source: —")
        self.badge_time.setText("Time Source: —")
        self.badge_risk.setText("Risk: —")
        self.badge_conf.setText("Confidence: —")
        self.badge_dup.setText("Duplicate: —")
        self.badge_format.setText("Format: —")

    def _set_geo_defaults(self) -> None:
        self.geo_badge_status.setText("GPS State: —")
        self.geo_badge_coords.setText("Coordinates: —")
        self.geo_badge_altitude.setText("Altitude: —")
        self.geo_badge_map.setText("Map Package: —")

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
            self._set_preview_controls(True)
        else:
            self.image_preview.clear_source("Preview unavailable for the selected evidence item.")
            self._set_preview_controls(False)

        self.badge_source.setText(f"Source: {record.source_type}")
        self.badge_time.setText(f"Time Source: {record.timestamp_source}")
        self.badge_risk.setText(f"Risk: {record.risk_level} / {record.suspicion_score}")
        self.badge_conf.setText(f"Confidence: {record.confidence_score}%")
        self.badge_dup.setText(f"Duplicate: {record.duplicate_group or 'None'}")
        self.badge_format.setText(f"Format: {record.format_name} • {record.dimensions}")

        self.geo_badge_status.setText(f"GPS State: {'Recovered' if record.has_gps else 'Unavailable'}")
        self.geo_badge_coords.setText(f"Coordinates: {record.gps_display}")
        self.geo_badge_altitude.setText(
            f"Altitude: {f'{record.gps_altitude:.2f} m' if record.gps_altitude is not None else 'Unavailable'}"
        )
        self.geo_badge_map.setText(f"Map Package: {'Ready' if self.current_map_path else 'Not Generated'}")

        self.summary_text.setPlainText(self._build_summary_text(record))
        self.metadata_view.setPlainText(self._build_metadata_text(record))
        self.geo_text.setPlainText(self._build_geo_text(record))
        self.geo_leads_text.setPlainText(self._build_geo_leads_text(record))
        self.selection_verdict_view.setPlainText(self._build_verdict_panel_text(record))

    def open_selected_file(self) -> None:
        record = self.selected_record()
        if record is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(record.file_path)))

    def _build_summary_text(self, record: EvidenceRecord) -> str:
        lines = [
            "[ ANALYST VERDICT ENGINE ]",
            "=" * 96,
            f"Evidence ID        : {record.evidence_id}",
            f"File               : {record.file_name}",
            f"Source Profile     : {record.source_type}",
            f"Recovered Time     : {record.timestamp}",
            f"Time Confidence    : {record.timestamp_source}",
            f"Device Signature   : {record.device_model}",
            f"Format / Mode      : {record.format_name} / {record.color_mode}",
            f"Dimensions         : {record.dimensions} ({record.megapixels:.2f} MP)",
            f"GPS                : {record.gps_display}",
            f"Risk / Confidence  : {record.risk_level} / {record.confidence_score}%",
            f"Duplicate Cluster  : {record.duplicate_group or 'None'}",
            "",
            "[ PROFESSIONAL INTERPRETATION ]",
            "-" * 96,
            record.analyst_verdict or "No analyst verdict is available for the selected evidence item.",
            "",
            "[ KEY FLAGS ]",
            "-" * 96,
        ]
        lines.extend([f"- {item}" for item in (record.anomaly_reasons or ["No major metadata anomalies were detected."])])
        return "\n".join(lines)

    def _build_metadata_text(self, record: EvidenceRecord) -> str:
        sections = [
            "[ METADATA TERMINAL ]",
            "=" * 104,
            f"File Path              : {record.file_path}",
            f"File Size              : {record.file_size:,} bytes",
            f"Format                 : {record.format_name}",
            f"Dimensions             : {record.dimensions}",
            f"Megapixels             : {record.megapixels:.2f}",
            f"Aspect Ratio           : {record.aspect_ratio}",
            f"Brightness Mean        : {record.brightness_mean:.2f}",
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
            sections.extend(["", "[ EMBEDDED EXIF TAGS ]", "-" * 104])
            for key, value in sorted(record.exif.items()):
                sections.append(f"{key:<30}: {value}")
        return "\n".join(sections)

    def _build_geo_text(self, record: EvidenceRecord) -> str:
        lines = [
            "[ GEOLOCATION TERMINAL ]",
            "=" * 96,
            f"Evidence ID           : {record.evidence_id}",
            f"Coordinates           : {record.gps_display}",
            f"Altitude              : {f'{record.gps_altitude:.2f} m' if record.gps_altitude is not None else 'Unavailable'}",
            f"Map Package           : {'Available' if self.current_map_path else 'Not generated'}",
            f"Time Anchor           : {record.timestamp} ({record.timestamp_source})",
            f"Source Profile        : {record.source_type}",
            "",
            "[ LOCATION INTELLIGENCE ]",
            "-" * 96,
        ]
        if record.has_gps:
            lines.extend(
                [
                    "- Native GPS values were recovered, so the file can support map-based scene correlation.",
                    "- Validate the coordinate in the exported map and compare it with venue, street, and CCTV coverage.",
                    "- Compare the point against timeline evidence, posting times, and known travel routes.",
                ]
            )
        else:
            lines.extend(
                [
                    "- No location coordinate was embedded in the file.",
                    "- Treat time, source profile, filenames, chat context, and device continuity as the primary pivots.",
                    "- If the file came from messaging or screenshot workflows, lack of GPS is often normal rather than suspicious.",
                ]
            )
        return "\n".join(lines)

    def _build_geo_leads_text(self, record: EvidenceRecord) -> str:
        lines = [
            "[ LOCATION / OSINT LEADS ]",
            "=" * 96,
        ]
        lines.extend([f"- {lead}" for lead in record.osint_leads])
        return "\n".join(lines)

    def populate_timeline(self) -> None:
        records = self.case_manager.records
        if not records:
            self.timeline_text.setPlainText("No evidence loaded yet.")
            self.timeline_chart.set_chart_pixmap(None, "Load evidence to generate a visual timeline.")
            return

        ordered = sorted(records, key=lambda r: (r.timestamp == "Unknown", r.timestamp, r.evidence_id))
        lines = ["[ TIMELINE ANALYST OUTPUT ]", "=" * 96]
        for idx, record in enumerate(ordered, start=1):
            lines.append(
                f"#{idx:02d}  {record.timestamp:<19} | {record.evidence_id:<8} | {record.risk_level:<6} | Score {record.suspicion_score:<3} | {record.source_type}"
            )
            lines.append(f"      File        : {record.file_name}")
            lines.append(f"      GPS         : {record.gps_display}")
            lines.append(f"      Time Source : {record.timestamp_source}")
            if record.duplicate_group:
                lines.append(f"      Duplicate   : {record.duplicate_group}")
            if record.anomaly_reasons:
                lines.append(f"      Lead        : {record.anomaly_reasons[0]}")
            lines.append("-" * 96)
        self.timeline_text.setPlainText("\n".join(lines))
        self._render_timeline_chart(ordered)

    def _render_timeline_chart(self, ordered: List[EvidenceRecord]) -> None:
        parsed = [(record, parse_timestamp(record.timestamp)) for record in ordered]
        dated = [(record, dt) for record, dt in parsed if dt is not None]
        output_path = self.export_dir / "chart_timeline.png"
        if not dated:
            self.timeline_chart.set_chart_pixmap(None, "No recoverable timestamps were available for a visual timeline.")
            return

        plt.close("all")
        fig, ax = plt.subplots(figsize=(12.5, 3.9), dpi=170)
        fig.patch.set_facecolor("#04101b")
        ax.set_facecolor("#04101b")

        x_values = [dt for _, dt in dated]
        y_values = list(range(1, len(dated) + 1))
        ax.plot(x_values, y_values, color="#4bdfff", linewidth=1.8, alpha=0.8)
        ax.scatter(x_values, y_values, s=90, color="#20beff", edgecolors="#dff8ff", linewidths=0.8, zorder=5)
        for (record, dt), y in zip(dated, y_values):
            ax.annotate(
                f"{record.evidence_id}\n{record.risk_level}",
                (dt, y),
                textcoords="offset points",
                xytext=(0, 10),
                ha="center",
                color="#eef8ff",
                fontsize=8,
                weight="bold",
            )
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d\n%H:%M"))
        ax.tick_params(axis="x", colors="#dcefff", labelsize=8)
        ax.tick_params(axis="y", colors="#dcefff", labelsize=8)
        ax.set_yticks(y_values)
        ax.set_yticklabels([record.evidence_id for record, _ in dated])
        ax.set_ylabel("Evidence order", color="#dcefff")
        ax.grid(axis="both", alpha=0.16, color="#78cfff")
        for spine in ax.spines.values():
            spine.set_color("#2f5c8e")
        fig.tight_layout(pad=1.2)
        fig.savefig(output_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close(fig)
        self.timeline_chart.set_chart_pixmap(QPixmap(str(output_path)), "Timeline chart unavailable")

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
            for card in [self.chart_sources, self.chart_risks, self.chart_geo]:
                card.set_chart_pixmap(None, "Load evidence to generate charts.")
            self.duplicate_terminal.setPlainText("Load evidence to generate duplicate-cluster analysis.")
            return

        source_counts: dict[str, int] = {}
        for record in records:
            source_counts[record.source_type] = source_counts.get(record.source_type, 0) + 1
        self._render_bar_chart(
            self.chart_sources,
            list(source_counts.keys()),
            list(source_counts.values()),
            self.export_dir / "chart_sources.png",
            horizontal=True,
        )

        risk_order = ["Low", "Medium", "High"]
        risk_counts = [sum(1 for r in records if r.risk_level == risk) for risk in risk_order]
        self._render_bar_chart(
            self.chart_risks,
            risk_order,
            risk_counts,
            self.export_dir / "chart_risks.png",
        )

        labels = ["GPS Enabled", "No GPS", "Clustered", "Unique"]
        values = [
            sum(1 for r in records if r.has_gps),
            sum(1 for r in records if not r.has_gps),
            sum(1 for r in records if r.duplicate_group),
            sum(1 for r in records if not r.duplicate_group),
        ]
        self._render_bar_chart(
            self.chart_geo,
            labels,
            values,
            self.export_dir / "chart_geo_duplicate.png",
        )
        self.duplicate_terminal.setPlainText(self._build_duplicate_terminal_text())

    def _render_bar_chart(
        self,
        card: ChartCard,
        labels: List[str],
        values: List[int],
        output_path: Path,
        horizontal: bool = False,
    ) -> None:
        plt.close("all")
        fig, ax = plt.subplots(figsize=(8.8, 3.9), dpi=180)
        fig.patch.set_facecolor("#04101b")
        ax.set_facecolor("#04101b")
        colors = ["#20beff", "#4bdfff", "#72ccff", "#2a86d1"]
        positions = range(len(labels))
        if horizontal:
            bars = ax.barh(list(positions), values, color=colors[: len(labels)], edgecolor="#dff6ff", linewidth=0.5)
            ax.set_yticks(list(positions))
            ax.set_yticklabels(labels, color="#eef8ff", fontsize=9)
            ax.tick_params(axis="x", colors="#dcefff", labelsize=8)
            for bar, value in zip(bars, values):
                ax.text(value + 0.05, bar.get_y() + bar.get_height() / 2, str(value), va="center", color="#ffffff", fontsize=9, weight="bold")
        else:
            bars = ax.bar(list(positions), values, color=colors[: len(labels)], edgecolor="#dff6ff", linewidth=0.5)
            ax.set_xticks(list(positions))
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
        pixmap = QPixmap(str(output_path))
        card.set_chart_pixmap(pixmap, "Chart unavailable")

    def _build_duplicate_terminal_text(self) -> str:
        clusters: dict[str, list[str]] = {}
        for record in self.case_manager.records:
            if record.duplicate_group:
                clusters.setdefault(record.duplicate_group, []).append(record.evidence_id + " — " + record.file_name)
        lines = ["[ DUPLICATE CLUSTER OVERVIEW ]", "=" * 96]
        if not clusters:
            lines.append("No duplicate clusters were detected from perceptual hashing in the current evidence set.")
            return "\n".join(lines)
        for cluster, items in sorted(clusters.items()):
            lines.append(f"{cluster} ({len(items)} file(s))")
            lines.append("-" * 96)
            lines.extend([f"  • {item}" for item in items])
            lines.append("")
        return "\n".join(lines)

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

    def _build_case_assessment_text(self) -> str:
        records = self.case_manager.records
        if not records:
            return "Load evidence to generate a case-wide assessment."
        total = len(records)
        gps = sum(1 for r in records if r.has_gps)
        high = sum(1 for r in records if r.risk_level == "High")
        medium = sum(1 for r in records if r.risk_level == "Medium")
        screenshots = sum(1 for r in records if "Screenshot" in r.source_type or "Messaging" in r.source_type)
        duplicates = len({r.duplicate_group for r in records if r.duplicate_group})
        dominant_source = max({r.source_type for r in records}, key=lambda s: sum(1 for r in records if r.source_type == s))
        lines = [
            "[ CASE ASSESSMENT ]",
            "=" * 96,
            f"Total evidence items     : {total}",
            f"Dominant source profile  : {dominant_source}",
            f"GPS-bearing media        : {gps}",
            f"High / Medium risk files : {high} / {medium}",
            f"Screenshot / export bias : {screenshots}",
            f"Duplicate clusters       : {duplicates}",
            "",
            "Interpretation:",
        ]
        if screenshots == total:
            lines.append("- The case is dominated by screenshots or messaging exports, so native EXIF depth will be limited and filename/time correlation becomes more important.")
        elif gps > 0:
            lines.append("- At least part of the evidence set supports map-based correlation, which strengthens timeline reconstruction.")
        else:
            lines.append("- This batch behaves primarily as non-location media, so provenance, timestamps, and source continuity should drive analysis.")
        if high > 0:
            lines.append("- One or more files carry high-risk metadata signals and should be reviewed first.")
        else:
            lines.append("- No high-risk outliers were flagged by the current rule-based analyst engine.")
        return "\n".join(lines)

    def _build_priority_text(self) -> str:
        records = self.case_manager.records
        if not records:
            return "Case priorities will appear here after evidence is loaded."
        ordered = sorted(records, key=lambda r: (-r.suspicion_score, r.evidence_id))[:5]
        lines = ["[ PRIORITY QUEUE ]", "=" * 96]
        for idx, record in enumerate(ordered, start=1):
            lines.append(f"{idx}. {record.evidence_id} — {record.risk_level} / Score {record.suspicion_score} / {record.source_type}")
            lines.append(f"   Why: {record.anomaly_reasons[0] if record.anomaly_reasons else 'No explicit anomaly note.'}")
        lines.extend([
            "",
            "Recommended next steps:",
            "- Validate time anchors against chat logs, upload records, or witness timelines.",
            "- Use duplicate clusters to reduce redundant review and isolate derivative media.",
            "- Prioritize GPS-enabled files for scene or movement correlation.",
        ])
        return "\n".join(lines)

    def _build_verdict_panel_text(self, record: EvidenceRecord) -> str:
        lines = [
            "[ SELECTED EVIDENCE VERDICT ]",
            "=" * 96,
            f"Record                 : {record.evidence_id}",
            f"Likely profile         : {record.source_type}",
            f"Authenticity posture   : {record.risk_level}",
            f"Confidence             : {record.confidence_score}%",
            f"Timestamp anchor       : {record.timestamp_source}",
            f"Location signal        : {'Present' if record.has_gps else 'Missing'}",
            f"Duplicate relation     : {record.duplicate_group or 'None'}",
            "",
            record.analyst_verdict or "No analyst verdict is available.",
        ]
        return "\n".join(lines)

    def show_info(self, title: str, message: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QMessageBox.Ok)
        box.exec_()
