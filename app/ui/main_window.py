from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import List

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QColor, QDesktopServices, QIcon, QImage, QPixmap
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
    QScrollArea,
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
from PIL import Image, ImageSequence
from app.core.case_manager import CaseManager
from app.core.map_service import MapService
from app.core.models import EvidenceRecord
from app.core.report_service import ReportService
from .styles import APP_STYLESHEET
from .widgets import (
    AutoHeightNarrativeView,
    ChartCard,
    NarrativeView,
    ResizableImageLabel,
    ScoreRing,
    SmoothScrollArea,
    StatCard,
    TerminalView,
)


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
        self.resize(1680, 980)
        self.setMinimumSize(1200, 740)
        self.setStyleSheet(APP_STYLESHEET)
        icon_path = self.assets_dir / "app_icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self._build_ui()
        self.refresh_dashboard()
        self.clear_details()

    def _build_ui(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = SmoothScrollArea()
        scroll.setObjectName("MainScrollArea")

        canvas = QWidget()
        root = QVBoxLayout(canvas)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        root.addWidget(self._build_header())
        root.addWidget(self._build_stat_cards())
        root.addWidget(self._build_briefing_row())
        root.addWidget(self._build_workspace(), 1)

        scroll.setWidget(canvas)
        outer.addWidget(scroll)
        self.setCentralWidget(central)

    def _build_header(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("HeaderFrame")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(18)

        left = QVBoxLayout()
        left.setSpacing(8)
        title = QLabel("GeoTrace Forensics X")
        title.setObjectName("TitleLabel")
        subtitle = QLabel(
            "Investigation command center for EXIF extraction, geolocation triage, visual timeline reconstruction, duplicate correlation, analyst verdicting, and courtroom-ready reporting."
        )
        subtitle.setObjectName("SubtitleLabel")
        subtitle.setWordWrap(True)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        self.case_badge = QLabel("Case GT-2026-001")
        self.case_badge.setObjectName("BadgeLabel")
        self.mode_badge = QLabel("Investigation Mode")
        self.mode_badge.setObjectName("BadgeLabel")
        self.export_badge = QLabel("Reports Ready")
        self.export_badge.setObjectName("BadgeLabel")
        self.formats_badge = QLabel("JPG • PNG • TIFF • WEBP • BMP • GIF • HEIC")
        self.formats_badge.setObjectName("BadgeLabel")
        for badge in [self.case_badge, self.mode_badge, self.export_badge, self.formats_badge]:
            badge_row.addWidget(badge)
        badge_row.addStretch(1)

        left.addWidget(title)
        left.addWidget(subtitle)
        left.addLayout(badge_row)

        right = QGridLayout()
        right.setHorizontalSpacing(8)
        right.setVerticalSpacing(8)
        self.case_label = self._info_badge("Case ID", "GT-2026-001")
        self.status_label = self._info_badge("Status", "Awaiting evidence")
        self.integrity_label = self._info_badge("Integrity", "0/0 Verified")
        self.method_label = self._info_badge("Workflow", "Acquire → Verify → Extract → Correlate → Score → Report")
        right.addWidget(self.case_label, 0, 0)
        right.addWidget(self.status_label, 0, 1)
        right.addWidget(self.integrity_label, 1, 0)
        right.addWidget(self.method_label, 1, 1)
        right.setColumnStretch(0, 1)
        right.setColumnStretch(1, 1)

        layout.addLayout(left, 4)
        layout.addLayout(right, 3)
        return frame

    def _info_badge(self, title: str, value: str) -> QLabel:
        label = QLabel(f"<div><span style='color:#7da4c4;font-size:9pt;'>{title}</span><br><span style='font-weight:800;color:#f5fbff;'>{value}</span></div>")
        label.setObjectName("InfoBadge")
        label.setTextFormat(Qt.RichText)
        return label

    def _build_stat_cards(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("PanelFrame")
        layout = QGridLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        self.card_total = StatCard("Images Loaded", chip="Inventory")
        self.card_gps = StatCard("GPS Enabled", chip="Geo")
        self.card_anomalies = StatCard("Anomalies Detected", chip="Review")
        self.card_devices = StatCard("Devices Identified", chip="Source")
        self.card_timeline = StatCard("Timeline Span", chip="Timeline")
        self.card_integrity = StatCard("Evidence Integrity", chip="Custody")
        self.card_duplicates = StatCard("Duplicate Clusters", chip="Correlation")
        self.card_avg_score = StatCard("Average Score", chip="Risk Engine")

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

    def _build_briefing_row(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("PanelFrame")
        layout = QGridLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        self.case_assessment_view = AutoHeightNarrativeView("Load evidence to generate a case-wide assessment.", max_auto_height=170)
        self.priority_view = AutoHeightNarrativeView("Case priorities and next best steps will appear here.", max_auto_height=170)

        layout.addWidget(self._shell("Case Assessment", self.case_assessment_view, "What the current case mix suggests."), 0, 0)
        layout.addWidget(self._shell("Priority Queue", self.priority_view, "Which artifacts deserve immediate review."), 0, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        return frame

    def _shell(self, title: str, body: QWidget, subtitle: str = "") -> QWidget:
        frame = QFrame()
        frame.setObjectName("CompactPanel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        lbl = QLabel(title)
        lbl.setObjectName("SectionLabel")
        layout.addWidget(lbl)
        if subtitle:
            meta = QLabel(subtitle)
            meta.setObjectName("SectionMetaLabel")
            meta.setWordWrap(True)
            layout.addWidget(meta)
        layout.addWidget(body, 1)
        return frame

    def _build_workspace(self) -> QWidget:
        frame = QWidget()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self._build_analysis_panel(), 3)
        layout.addWidget(self._build_inventory_panel(), 2)
        return frame

    def _build_inventory_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("PanelFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        title = QLabel("Evidence Inventory")
        title.setObjectName("SectionLabel")
        self.inventory_meta = QLabel("Load image evidence to begin forensic analysis.")
        self.inventory_meta.setObjectName("MutedLabel")
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(self.inventory_meta)

        controls = QGridLayout()
        controls.setHorizontalSpacing(8)
        controls.setVerticalSpacing(8)

        self.btn_load_images = QPushButton("Import Image Files")
        self.btn_load_images.setObjectName("PrimaryButton")
        self.btn_load_images.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btn_load_images.clicked.connect(self.import_images)

        self.btn_load_folder = QPushButton("Import Folder")
        self.btn_load_folder.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.btn_load_folder.clicked.connect(self.import_folder)

        self.btn_generate_report = QPushButton("Generate Report Package")
        self.btn_generate_report.setIcon(self.style().standardIcon(QStyle.SP_DriveFDIcon))
        self.btn_generate_report.clicked.connect(self.generate_reports)

        self.btn_open_map = QPushButton("Open Geo Map")
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
                "Parser Issues",
            ]
        )
        self.filter_combo.currentTextChanged.connect(self.apply_filters)

        controls.addWidget(self.btn_load_images, 0, 0)
        controls.addWidget(self.btn_load_folder, 0, 1)
        controls.addWidget(self.btn_generate_report, 1, 0)
        controls.addWidget(self.btn_open_map, 1, 1)
        controls.addWidget(self.search_box, 2, 0, 1, 2)
        controls.addWidget(self.filter_combo, 3, 0, 1, 2)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Ready")

        self.table = QTableWidget(0, 10)
        self.table.setMinimumHeight(360)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setHorizontalHeaderLabels(
            ["Thumb", "Evidence", "File Name", "Timestamp", "Source", "Parser", "GPS", "Score", "Risk", "Integrity"]
        )
        self.table.itemSelectionChanged.connect(self.populate_details)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeToContents)
        self.table.setIconSize(QPixmap(56, 42).size())
        self.table.setSortingEnabled(True)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.verticalScrollBar().setSingleStep(26)
        self.table.horizontalScrollBar().setSingleStep(26)

        layout.addLayout(title_row)
        layout.addLayout(controls)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.table, 1)
        return frame

    def _build_analysis_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("PanelFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Evidence Analysis Workspace")
        title.setObjectName("SectionLabel")
        meta = QLabel("Preview, analyst verdict, metadata, geo, timeline, and custody details for the selected item.")
        meta.setObjectName("SectionMetaLabel")
        title_box.addWidget(title)
        title_box.addWidget(meta)
        header_row.addLayout(title_box)
        header_row.addStretch(1)
        layout.addLayout(header_row)

        top_split = QSplitter(Qt.Horizontal)
        top_split.setChildrenCollapsible(False)
        top_split.setOpaqueResize(False)
        top_split.addWidget(self._build_preview_shell())
        top_split.addWidget(self._build_inspector_column())
        top_split.setSizes([1040, 420])

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.metadata_tab = self._build_metadata_tab()
        self.geo_tab = self._build_geo_tab()
        self.timeline_tab = self._build_timeline_tab()
        self.insights_tab = self._build_insights_tab()
        self.custody_tab = self._build_custody_tab()
        self.tabs.addTab(self.metadata_tab, "Metadata")
        self.tabs.addTab(self.geo_tab, "Geo")
        self.tabs.addTab(self.timeline_tab, "Timeline")
        self.tabs.addTab(self.insights_tab, "Insights")
        self.tabs.addTab(self.custody_tab, "Custody")

        layout.addWidget(top_split, 3)
        layout.addWidget(self.tabs, 2)
        return frame

    def _build_preview_shell(self) -> QWidget:
        preview_shell = QFrame()
        preview_shell.setObjectName("HeroPreviewPanel")
        layout = QVBoxLayout(preview_shell)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        title = QLabel("Live Evidence Preview")
        title.setObjectName("SectionLabel")
        subtitle = QLabel("Zoom, inspect, validate frame decoding, and review what the analyst engine is scoring.")
        subtitle.setObjectName("SectionMetaLabel")
        left = QVBoxLayout()
        left.setSpacing(2)
        left.addWidget(title)
        left.addWidget(subtitle)
        toolbar.addLayout(left)
        toolbar.addStretch(1)
        self.preview_zoom_pill = QLabel("Zoom 100%")
        self.preview_zoom_pill.setObjectName("PreviewZoomPill")
        toolbar.addWidget(self.preview_zoom_pill)
        self.btn_zoom_out = QPushButton("−")
        self.btn_zoom_out.setObjectName("SmallGhostButton")
        self.btn_zoom_out.clicked.connect(self._zoom_preview_out)
        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setObjectName("SmallGhostButton")
        self.btn_zoom_in.clicked.connect(self._zoom_preview_in)
        self.btn_zoom_fit = QPushButton("Fit")
        self.btn_zoom_fit.setObjectName("SmallGhostButton")
        self.btn_zoom_fit.clicked.connect(self._zoom_preview_fit)
        self.btn_zoom_reset = QPushButton("100%")
        self.btn_zoom_reset.setObjectName("SmallGhostButton")
        self.btn_zoom_reset.clicked.connect(self._zoom_preview_reset)
        self.btn_open_external = QPushButton("Open Original")
        self.btn_open_external.setObjectName("SmallGhostButton")
        self.btn_open_external.clicked.connect(self.open_selected_file)
        for btn in [self.btn_zoom_out, self.btn_zoom_in, self.btn_zoom_fit, self.btn_zoom_reset, self.btn_open_external]:
            toolbar.addWidget(btn)

        state_row = QGridLayout()
        state_row.setHorizontalSpacing(8)
        state_row.setVerticalSpacing(8)
        self.preview_state_badge = QLabel("Preview State: Awaiting selection")
        self.preview_state_badge.setObjectName("PreviewStateBadge")
        self.preview_parser_badge = QLabel("Parser: —")
        self.preview_parser_badge.setObjectName("PreviewStateBadge")
        self.preview_trust_badge = QLabel("Format Trust: —")
        self.preview_trust_badge.setObjectName("PreviewStateBadge")
        self.preview_animation_badge = QLabel("Frames: —")
        self.preview_animation_badge.setObjectName("PreviewStateBadge")
        for idx, badge in enumerate([self.preview_state_badge, self.preview_parser_badge, self.preview_trust_badge, self.preview_animation_badge]):
            state_row.addWidget(badge, 0, idx)

        preview_frame = QFrame()
        preview_frame.setObjectName("PreviewCanvasFrame")
        preview_frame_layout = QVBoxLayout(preview_frame)
        preview_frame_layout.setContentsMargins(10, 10, 10, 10)
        preview_frame_layout.setSpacing(0)
        self.image_preview = ResizableImageLabel("Select evidence from the inventory to inspect preview, metadata, geolocation, timeline, and analyst verdict.", min_height=320)
        self.preview_scroll = SmoothScrollArea()
        self.preview_scroll.setObjectName("PreviewScrollArea")
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setMinimumHeight(340)
        self.preview_scroll.setFrameShape(QFrame.NoFrame)
        self.preview_scroll.setWidget(self.image_preview)
        self.preview_scroll.verticalScrollBar().setSingleStep(22)
        self.preview_scroll.horizontalScrollBar().setSingleStep(22)
        preview_frame_layout.addWidget(self.preview_scroll)

        meta_grid = QGridLayout()
        meta_grid.setHorizontalSpacing(10)
        meta_grid.setVerticalSpacing(8)
        self.preview_file_meta = self._preview_meta_block("Evidence", "—")
        self.preview_source_meta = self._preview_meta_block("Source Profile", "—")
        self.preview_time_meta = self._preview_meta_block("Recovered Time", "—")
        self.preview_geo_meta = self._preview_meta_block("GPS / Geo", "—")
        meta_grid.addWidget(self.preview_file_meta, 0, 0)
        meta_grid.addWidget(self.preview_source_meta, 0, 1)
        meta_grid.addWidget(self.preview_time_meta, 1, 0)
        meta_grid.addWidget(self.preview_geo_meta, 1, 1)

        layout.addLayout(toolbar)
        layout.addLayout(state_row)
        layout.addWidget(preview_frame, 1)
        layout.addLayout(meta_grid)
        return preview_shell

    def _preview_meta_block(self, title: str, value: str) -> QWidget:
        frame = QFrame()
        frame.setObjectName("SecondaryPanel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("PreviewMetaTitle")
        value_label = QLabel(value)
        value_label.setObjectName("PreviewMetaValue")
        value_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        frame.value_label = value_label  # type: ignore[attr-defined]
        return frame

    def _build_inspector_column(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        top_card = QFrame()
        top_card.setObjectName("VerdictPanel")
        top_layout = QVBoxLayout(top_card)
        top_layout.setContentsMargins(14, 14, 14, 14)
        top_layout.setSpacing(12)
        header = QVBoxLayout()
        label = QLabel("Selected Evidence Verdict")
        label.setObjectName("SectionLabel")
        meta = QLabel("Context-aware scoring with parser health, format trust, and forensic provenance reasoning.")
        meta.setObjectName("SectionMetaLabel")
        self.score_ring = ScoreRing(126)
        header.addWidget(label)
        header.addWidget(meta)
        header.addWidget(self.score_ring, alignment=Qt.AlignHCenter)
        confidence_meta = QLabel("Analyst Confidence")
        confidence_meta.setObjectName("MutedLabel")
        self.confidence_bar = QProgressBar()
        self.confidence_bar.setObjectName("ConfidenceBar")
        self.confidence_bar.setRange(0, 100)
        self.confidence_bar.setValue(0)
        self.confidence_bar.setTextVisible(False)
        self.confidence_bar_label = QLabel("0% confidence")
        self.confidence_bar_label.setObjectName("MutedLabel")
        badges = QGridLayout()
        badges.setHorizontalSpacing(8)
        badges.setVerticalSpacing(8)
        self.badge_source = self._micro_badge("Source: —")
        self.badge_time = self._micro_badge("Time Source: —")
        self.badge_risk = self._risk_badge("Risk: —", "Low")
        self.badge_conf = self._micro_badge("Parser: —")
        self.badge_dup = self._micro_badge("Trust: —")
        self.badge_format = self._micro_badge("Format: —")
        for idx, badge in enumerate([self.badge_source, self.badge_time, self.badge_risk, self.badge_conf, self.badge_dup, self.badge_format]):
            badges.addWidget(badge, idx // 2, idx % 2)
        score_row = QGridLayout()
        score_row.setHorizontalSpacing(8)
        score_row.setVerticalSpacing(8)
        self.score_auth_badge = QLabel("Authenticity 0")
        self.score_auth_badge.setObjectName("ScoreBreakdownBadge")
        self.score_meta_badge = QLabel("Metadata 0")
        self.score_meta_badge.setObjectName("ScoreBreakdownBadge")
        self.score_tech_badge = QLabel("Technical 0")
        self.score_tech_badge.setObjectName("ScoreBreakdownBadge")
        score_row.addWidget(self.score_auth_badge, 0, 0)
        score_row.addWidget(self.score_meta_badge, 0, 1)
        score_row.addWidget(self.score_tech_badge, 0, 2)
        self.selection_verdict_view = AutoHeightNarrativeView("Select an evidence item to load the analyst verdict engine.", max_auto_height=250)
        top_layout.addLayout(header)
        top_layout.addWidget(confidence_meta)
        top_layout.addWidget(self.confidence_bar)
        top_layout.addWidget(self.confidence_bar_label)
        top_layout.addLayout(badges)
        top_layout.addLayout(score_row)
        top_layout.addWidget(self.selection_verdict_view)

        lower_card = QFrame()
        lower_card.setObjectName("CompactPanel")
        lower_layout = QVBoxLayout(lower_card)
        lower_layout.setContentsMargins(14, 14, 14, 14)
        lower_layout.setSpacing(10)
        lower_title = QLabel("Immediate Investigation Leads")
        lower_title.setObjectName("SectionLabel")
        lower_meta = QLabel("What to do next for the currently selected item.")
        lower_meta.setObjectName("SectionMetaLabel")
        self.summary_text = AutoHeightNarrativeView("The selected evidence will be summarized here with analyst-style reasoning.", max_auto_height=220)
        lower_layout.addWidget(lower_title)
        lower_layout.addWidget(lower_meta)
        lower_layout.addWidget(self.summary_text)
        layout.addWidget(top_card, 3)
        layout.addWidget(lower_card, 2)
        return widget

    def _timeline_badge(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("TimelineBadge")
        lbl.setWordWrap(True)
        return lbl

    def _micro_badge(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("MicroBadge")
        lbl.setWordWrap(True)
        return lbl

    def _risk_badge(self, text: str, level: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        self._apply_risk_badge_style(lbl, level)
        return lbl

    def _apply_risk_badge_style(self, label: QLabel, level: str) -> None:
        object_name = {
            "High": "RiskBadgeHigh",
            "Medium": "RiskBadgeMedium",
            "Low": "RiskBadgeLow",
        }.get(level, "RiskBadgeLow")
        label.setObjectName(object_name)
        label.style().unpolish(label)
        label.style().polish(label)
        label.update()

    def _build_metadata_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        split = QSplitter(Qt.Vertical)
        split.setChildrenCollapsible(False)
        split.setOpaqueResize(False)

        self.metadata_view = TerminalView("Metadata extraction details will appear here.")
        metadata_shell = self._shell("Metadata Terminal", self.metadata_view, "Full technical values, hashes, and embedded tags.")

        notes_shell = QFrame()
        notes_shell.setObjectName("CompactPanel")
        notes_layout = QVBoxLayout(notes_shell)
        notes_layout.setContentsMargins(12, 12, 12, 12)
        notes_layout.setSpacing(8)
        notes_label = QLabel("Investigator Notes")
        notes_label.setObjectName("SectionLabel")
        notes_meta = QLabel("Record your own observations, correlation ideas, and courtroom notes.")
        notes_meta.setObjectName("SectionMetaLabel")
        self.note_editor = QTextEdit()
        self.note_editor.setPlaceholderText("Add analyst observations, significance, correlation ideas, or follow-up questions for the selected evidence item...")
        save_button = QPushButton("Save Investigator Note")
        save_button.clicked.connect(self.save_note)
        notes_layout.addWidget(notes_label)
        notes_layout.addWidget(notes_meta)
        notes_layout.addWidget(self.note_editor, 1)
        notes_layout.addWidget(save_button)

        split.addWidget(metadata_shell)
        split.addWidget(notes_shell)
        split.setSizes([430, 220])
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
        split.setOpaqueResize(False)
        self.geo_text = TerminalView("GPS findings and coordinate intelligence will appear here.")
        self.geo_leads_text = TerminalView("OSINT follow-up ideas and location pivots will appear here.")
        split.addWidget(self._shell("Geo Terminal", self.geo_text, "Native location signals and interpretation."))
        split.addWidget(self._shell("Location Investigation Leads", self.geo_leads_text, "OSINT pivots, venue checks, and next-step suggestions."))
        split.setSizes([760, 520])

        layout.addLayout(top_row)
        layout.addWidget(split, 1)
        return widget

    def _build_timeline_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        badge_row = QGridLayout()
        badge_row.setHorizontalSpacing(8)
        badge_row.setVerticalSpacing(8)
        self.timeline_badge_start = self._timeline_badge("Earliest: —")
        self.timeline_badge_end = self._timeline_badge("Latest: —")
        self.timeline_badge_span = self._timeline_badge("Span: —")
        self.timeline_badge_order = self._timeline_badge("Ordering: —")
        for idx, badge in enumerate([self.timeline_badge_start, self.timeline_badge_end, self.timeline_badge_span, self.timeline_badge_order]):
            badge_row.addWidget(badge, 0, idx)

        split = QSplitter(Qt.Vertical)
        split.setChildrenCollapsible(False)
        split.setOpaqueResize(False)
        self.timeline_chart = ChartCard(
            "Timeline Reconstruction",
            "Recovered timestamps are plotted chronologically to expose burst activity, gaps, and ordering confidence.",
        )
        self.timeline_text = TerminalView("Timeline analysis will appear here after evidence is loaded.")
        split.addWidget(self.timeline_chart)
        split.addWidget(self._shell("Timeline Analyst Terminal", self.timeline_text, "Machine-assisted narrative of the reconstructed event order."))
        split.setSizes([370, 250])

        layout.addLayout(badge_row)
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
        top.addWidget(self._shell("Duplicate Cluster Overview", self.duplicate_terminal, "Perceptual hash matches and review reduction opportunities."), 1, 1)
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
        label_box = QVBoxLayout()
        label = QLabel("Chain of Custody")
        label.setObjectName("SectionLabel")
        meta = QLabel("Acquisition, analysis, note, and reporting actions captured for evidentiary continuity.")
        meta.setObjectName("SectionMetaLabel")
        label_box.addWidget(label)
        label_box.addWidget(meta)
        controls.addLayout(label_box)
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
        self._set_info_badge(self.status_label, "Status", f"{len(self.records)} evidence items analyzed")
        self.inventory_meta.setText(f"Loaded {len(self.records)} evidence items.")

    def populate_table(self, records: List[EvidenceRecord]) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        placeholder = QPixmap(56, 42)
        placeholder.fill(QColor("#0a1728"))
        for record in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            thumb_item = QTableWidgetItem()
            thumb = self._load_pixmap_from_record(record)
            if thumb is None or thumb.isNull():
                thumb = placeholder
            else:
                thumb = thumb.scaled(56, 42, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            thumb_item.setIcon(QIcon(thumb))
            thumb_item.setText("")
            thumb_item.setToolTip(record.file_name)
            self.table.setItem(row, 0, thumb_item)
            values = [
                record.evidence_id,
                record.file_name,
                self._display_timestamp(record.timestamp),
                record.source_type,
                record.parser_status,
                record.gps_display,
                str(record.suspicion_score),
                record.risk_level,
                record.integrity_status,
            ]
            for offset, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if offset in {1, 7, 8, 9}:
                    item.setTextAlignment(Qt.AlignCenter)
                if offset == 5:
                    color = "#9fe8ff" if value == "Valid" else "#ffd480"
                    if value == "Failed":
                        color = "#ff9aad"
                    item.setForeground(QColor(color))
                if offset == 8:
                    item.setForeground(QColor("#ff9aad" if value == "High" else "#ffd480" if value == "Medium" else "#96f0c2"))
                if offset == 9:
                    item.setForeground(QColor("#9fe8ff"))
                self.table.setItem(row, offset, item)
            self.table.setRowHeight(row, 54)
        self.table.setColumnWidth(0, 64)
        self.table.setSortingEnabled(True)
        self.inventory_meta.setText("No results match the current filter." if self.table.rowCount() == 0 else f"Showing {len(records)} evidence items.")

    def _display_timestamp(self, timestamp: str) -> str:
        if timestamp == "Unknown":
            return timestamp
        return timestamp.replace(":", "-", 2)

    def refresh_dashboard(self) -> None:
        stats = self.case_manager.build_stats()
        self.card_total.set_value(str(stats.total_images))
        self.card_total.set_subtitle("Total imported evidence items in the current case.")
        self.card_gps.set_value(str(stats.gps_enabled))
        self.card_gps.set_subtitle("Files with native coordinates available for map correlation.")
        self.card_anomalies.set_value(str(stats.anomaly_count))
        self.card_anomalies.set_subtitle("Artifacts requiring medium or high-confidence review.")
        self.card_devices.set_value(str(stats.device_count))
        self.card_devices.set_subtitle("Distinct camera or device signatures extracted from metadata.")
        self.card_timeline.set_value(stats.timeline_span)
        self.card_timeline.set_subtitle("Recovered chronological span across the loaded evidence.")
        self.card_integrity.set_value(stats.integrity_summary)
        self.card_integrity.set_subtitle("Files hashed and preserved in verified custody state.")
        self.card_duplicates.set_value(str(stats.duplicates_count))
        self.card_duplicates.set_subtitle("Perceptual hash clusters that may represent copies or edits.")
        self.card_avg_score.set_value(str(stats.avg_score))
        self.card_avg_score.set_subtitle("Average suspicion score assigned by the analyst engine.")
        self._set_info_badge(self.integrity_label, "Integrity", stats.integrity_summary)
        self.btn_open_map.setEnabled(stats.gps_enabled > 0)
        self.geo_open_map_btn.setEnabled(stats.gps_enabled > 0)
        self.btn_generate_report.setEnabled(stats.total_images > 0)
        self.case_assessment_view.setPlainText(self._build_case_assessment_text())
        self.priority_view.setPlainText(self._build_priority_text())

    def _set_info_badge(self, label: QLabel, title: str, value: str) -> None:
        label.setText(f"<div><span style='color:#7da4c4;font-size:9pt;'>{title}</span><br><span style='font-weight:800;color:#f5fbff;'>{value}</span></div>")

    def _activate_filter(self, label: str) -> None:
        self.filter_combo.setCurrentText(label)
        if label == "Duplicate Cluster":
            self.tabs.setCurrentWidget(self.insights_tab)
        elif label == "Has GPS":
            self.tabs.setCurrentWidget(self.geo_tab)
        elif label in {"High Risk", "Medium Risk", "Low Risk"}:
            self.tabs.setCurrentWidget(self.timeline_tab)
        else:
            self.tabs.setCurrentWidget(self.metadata_tab)
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
                    record.parser_status,
                    record.format_trust,
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
            if mode == "Parser Issues" and record.parser_status == "Valid" and record.format_trust == "Verified":
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
        evidence_id_item = self.table.item(row, 1)
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
            "Select evidence from the inventory to inspect preview, metadata, geolocation, timeline, and analyst verdict."
        )
        self.summary_text.clear()
        self.metadata_view.clear()
        self.note_editor.clear()
        self.geo_text.clear()
        self.geo_leads_text.clear()
        self.timeline_text.setPlainText("Timeline analysis will appear here after evidence is loaded.")
        self.selection_verdict_view.setPlainText("Select an evidence item to load the analyst verdict engine.")
        self.preview_file_meta.value_label.setText("—")  # type: ignore[attr-defined]
        self.preview_source_meta.value_label.setText("—")  # type: ignore[attr-defined]
        self.preview_time_meta.value_label.setText("—")  # type: ignore[attr-defined]
        self.preview_geo_meta.value_label.setText("—")  # type: ignore[attr-defined]
        self.score_ring.set_value(0)
        self.score_ring.set_caption("Evidence Score", "Awaiting selection")
        self.confidence_bar.setValue(0)
        self.confidence_bar_label.setText("0% confidence")
        self.preview_zoom_pill.setText("Zoom 100%")
        self.preview_state_badge.setText("Preview State: Awaiting selection")
        self.preview_parser_badge.setText("Parser: —")
        self.preview_trust_badge.setText("Trust / Signature: —")
        self.preview_animation_badge.setText("Frames: —")
        self._set_badge_defaults()
        self._set_geo_defaults()
        self._set_timeline_defaults()
        self._set_preview_controls(False)

    def _set_preview_controls(self, enabled: bool) -> None:
        for btn in [self.btn_zoom_out, self.btn_zoom_in, self.btn_zoom_fit, self.btn_zoom_reset, self.btn_open_external]:
            btn.setEnabled(enabled)

    def _set_badge_defaults(self) -> None:
        self.badge_source.setText("Source: —")
        self.badge_time.setText("Time Source: —")
        self.badge_risk.setText("Risk: —")
        self.badge_conf.setText("Parser: —")
        self.confidence_bar.setValue(0)
        self.confidence_bar_label.setText("0% confidence")
        self.badge_dup.setText("Trust: —")
        self.badge_format.setText("Format: —")
        self.score_auth_badge.setText("Authenticity 0")
        self.score_meta_badge.setText("Metadata 0")
        self.score_tech_badge.setText("Technical 0")
        self._apply_risk_badge_style(self.badge_risk, "Low")

    def _set_geo_defaults(self) -> None:
        self.geo_badge_status.setText("GPS State: —")
        self.geo_badge_coords.setText("Coordinates: —")
        self.geo_badge_altitude.setText("Altitude: —")
        self.geo_badge_map.setText("Map Package: —")

    def _set_timeline_defaults(self) -> None:
        self.timeline_badge_start.setText("Earliest: —")
        self.timeline_badge_end.setText("Latest: —")
        self.timeline_badge_span.setText("Span: —")
        self.timeline_badge_order.setText("Ordering: —")

    def populate_details(self) -> None:
        record = self.selected_record()
        if record is None:
            self.clear_details()
            return
        self.note_editor.setPlainText(record.note or "")
        self.current_preview_pixmap = self._load_pixmap_from_record(record)
        if self.current_preview_pixmap is not None:
            self.image_preview.set_source_pixmap(self.current_preview_pixmap)
            self._set_preview_controls(True)
        else:
            preview_reason = record.parse_error or "Preview unavailable for the selected evidence item."
            self.image_preview.clear_source(f"Preview unavailable.\n\n{preview_reason}\n\nParser Status: {record.parser_status} • Format Trust: {record.format_trust}")
            self._set_preview_controls(False)
        self.preview_file_meta.value_label.setText(f"{record.evidence_id} • {record.file_name}")  # type: ignore[attr-defined]
        self.preview_source_meta.value_label.setText(record.source_type)  # type: ignore[attr-defined]
        self.preview_time_meta.value_label.setText(f"{record.timestamp} ({record.timestamp_source})")  # type: ignore[attr-defined]
        self.preview_geo_meta.value_label.setText(record.gps_display)  # type: ignore[attr-defined]
        self.preview_state_badge.setText(f"Preview State: {record.preview_status}")
        self.preview_parser_badge.setText(f"Parser: {record.parser_status}")
        self.preview_trust_badge.setText(f"Trust / Signature: {record.format_trust} • {record.detected_format} • {record.format_signature}")
        frame_label = f"Frames: {record.frame_count}"
        if record.is_animated and record.animation_duration_ms:
            frame_label += f" • ~{record.animation_duration_ms} ms"
        self.preview_animation_badge.setText(frame_label)
        self.badge_source.setText(f"Source: {record.source_type}")
        self.badge_time.setText(f"Time Source: {record.timestamp_source}")
        self.badge_risk.setText(f"Risk: {record.risk_level} / Score {record.suspicion_score}")
        self.badge_conf.setText(f"Parser: {record.parser_status}")
        self.badge_dup.setText(f"Trust: {record.format_trust} • {record.detected_format}")
        self.confidence_bar.setValue(record.confidence_score)
        self.confidence_bar_label.setText(f"{record.confidence_score}% analyst confidence")
        fmt_extra = f" • {record.frame_count} frame(s)" if record.is_animated else ""
        self.badge_format.setText(f"Format: {record.declared_format} → {record.detected_format} • {record.dimensions}{fmt_extra}")
        self.score_auth_badge.setText(f"Authenticity {record.authenticity_score}")
        self.score_meta_badge.setText(f"Metadata {record.metadata_score}")
        self.score_tech_badge.setText(f"Technical {record.technical_score}")
        self._apply_risk_badge_style(self.badge_risk, record.risk_level)
        self.geo_badge_status.setText(f"GPS State: {'Recovered' if record.has_gps else 'Unavailable'}")
        self.geo_badge_coords.setText(f"Coordinates: {record.gps_display}")
        self.geo_badge_altitude.setText(f"Altitude: {f'{record.gps_altitude:.2f} m' if record.gps_altitude is not None else 'Unavailable'}")
        self.geo_badge_map.setText(f"Map Package: {'Ready' if self.current_map_path else 'Not Generated'}")
        self.score_ring.set_value(record.suspicion_score)
        self.score_ring.set_caption("Evidence Score", record.risk_level)
        self.preview_zoom_pill.setText(f"Zoom {self.image_preview.zoom_percent()}%")
        self.summary_text.setPlainText(self._build_summary_text(record))
        self.metadata_view.setPlainText(self._build_metadata_text(record))
        self.geo_text.setPlainText(self._build_geo_text(record))
        self.geo_leads_text.setPlainText(self._build_geo_leads_text(record))
        self.selection_verdict_view.setPlainText(self._build_verdict_panel_text(record))

    def _refresh_zoom_pill(self) -> None:
        self.preview_zoom_pill.setText(f"Zoom {self.image_preview.zoom_percent()}%")

    def _zoom_preview_in(self) -> None:
        self.image_preview.zoom_in()
        self._refresh_zoom_pill()

    def _zoom_preview_out(self) -> None:
        self.image_preview.zoom_out()
        self._refresh_zoom_pill()

    def _zoom_preview_fit(self) -> None:
        self.image_preview.fit_to_window()
        self._refresh_zoom_pill()

    def _zoom_preview_reset(self) -> None:
        self.image_preview.reset_zoom()
        self._refresh_zoom_pill()

    def open_selected_file(self) -> None:
        record = self.selected_record()
        if record is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(record.file_path)))

    def _load_pixmap_from_record(self, record: EvidenceRecord) -> QPixmap | None:
        pixmap = QPixmap(str(record.file_path))
        if not pixmap.isNull():
            return pixmap
        try:
            with Image.open(record.file_path) as image:
                frame = next(iter(ImageSequence.Iterator(image))).copy() if getattr(image, "is_animated", False) else image.copy()
                rgba = frame.convert("RGBA")
                data = rgba.tobytes("raw", "RGBA")
                qimg = QImage(data, rgba.width, rgba.height, QImage.Format_RGBA8888)
                pixmap = QPixmap.fromImage(qimg.copy())
                if not pixmap.isNull():
                    return pixmap
        except Exception:
            pass
        detected = (record.detected_format or "Unknown").upper()
        if detected == "PNG":
            try:
                qimg = QImage()
                qimg.loadFromData(record.file_path.read_bytes(), b"PNG")
                if not qimg.isNull():
                    return QPixmap.fromImage(qimg)
            except Exception:
                pass
        return None

    def _build_summary_text(self, record: EvidenceRecord) -> str:
        lead = record.anomaly_reasons[0] if record.anomaly_reasons else "No major metadata anomalies were detected."
        handling = "Preserve the item exactly as acquired, validate the strongest time anchor, and compare it against surrounding evidence before drawing narrative conclusions."
        if record.parser_status != "Valid":
            handling = "Use a secondary parser and do not rely on the preview alone. Treat the file as structurally sensitive until independent decoding confirms what it contains."
        elif record.has_gps:
            handling = "Map correlation should be prioritized because native coordinates are available and can strengthen scene reconstruction."
        notes = [
            f"{record.evidence_id} is currently profiled as {record.source_type.lower()} with an overall {record.risk_level.lower()} review posture.",
            f"Recovered time anchor: {record.timestamp} via {record.timestamp_source}. Parser state: {record.parser_status}. Declared format: {record.declared_format}. Detected format: {record.detected_format}. Trust: {record.format_trust}.",
            f"Score mix → authenticity {record.authenticity_score}, metadata {record.metadata_score}, technical {record.technical_score}. GPS status: {record.gps_display}.",
            f"Primary review flag: {lead}",
            f"Recommended handling: {handling}",
        ]
        return "\n\n".join(notes)
    def _build_metadata_text(self, record: EvidenceRecord) -> str:
        sections = [
            "[ METADATA TERMINAL ]",
            "=" * 104,
            f"File Path              : {record.file_path}",
            f"File Size              : {record.file_size:,} bytes",
            f"Format (resolved)      : {record.format_name}",
            f"Declared Format        : {record.declared_format}",
            f"Detected Format        : {record.detected_format}",
            f"Format Signature       : {record.format_signature}",
            f"Format Trust           : {record.format_trust}",
            f"Parser Status          : {record.parser_status}",
            f"Structure Status       : {record.structure_status}",
            f"Preview Status         : {record.preview_status}",
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
            f"Perceptual Hash        : {record.perceptual_hash if record.perceptual_hash not in ("", "Unavailable", "0" * 16) else "Unavailable"}",
            f"Duplicate Cluster      : {record.duplicate_group or 'None'}",
            f"Frames / Animation     : {record.frame_count} / {'Animated' if record.is_animated else 'Static'}",
            f"Animation Duration     : {record.animation_duration_ms if record.animation_duration_ms else 'N/A'}",
            f"Integrity              : {record.integrity_status}",
            f"Authenticity Score     : {record.authenticity_score}",
            f"Metadata Score         : {record.metadata_score}",
            f"Technical Score        : {record.technical_score}",
        ]
        if record.parse_error:
            sections.extend(["", "[ PARSER DIAGNOSTICS ]", "-" * 104, record.parse_error])
        if record.score_breakdown:
            sections.extend(["", "[ SCORE BREAKDOWN ]", "-" * 104])
            sections.extend(record.score_breakdown)
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
            f"Parser / Trust        : {record.parser_status} / {record.format_trust} ({record.declared_format} → {record.detected_format})",
            "",
            "[ LOCATION INTELLIGENCE ]",
            "-" * 96,
        ]
        if record.has_gps:
            lines.extend([
                "- Native GPS values were recovered, so the file can support map-based scene correlation.",
                "- Validate the coordinate in the exported map and compare it with venue, street, and CCTV coverage.",
                "- Compare the point against timeline evidence, posting times, and known travel routes.",
            ])
        else:
            lines.extend([
                "- No location coordinate was embedded in the file.",
                "- Treat time, source profile, filenames, chat context, and device continuity as the primary pivots.",
                "- If the file came from messaging or screenshot workflows, lack of GPS is often normal rather than suspicious.",
            ])
        if record.parser_status != "Valid":
            lines.extend([
                "",
                "[ STRUCTURE WARNING ]",
                "-" * 96,
                "- Decoder failure means geolocation conclusions should be anchored to external evidence, not to the preview surface alone.",
            ])
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
            lines.append(f"      GPS         : {record.gps_display}")
            lines.append(f"      Time Source : {record.timestamp_source}")
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
            ordered_count = len(parsed_points)
            self.timeline_badge_start.setText(f"Earliest: {first_dt.strftime('%Y-%m-%d %H:%M')}")
            self.timeline_badge_end.setText(f"Latest: {last_dt.strftime('%Y-%m-%d %H:%M')}")
            self.timeline_badge_span.setText(f"Span: {str(span).split('.')[0]}")
            self.timeline_badge_order.setText(f"Ordering: {ordered_count} anchored item(s)")
        else:
            self._set_timeline_defaults()

        self._render_timeline_chart(ordered)

    def _render_timeline_chart(self, ordered: List[EvidenceRecord]) -> None:
        parsed = [(record, parse_timestamp(record.timestamp)) for record in ordered]
        dated = [(record, dt) for record, dt in parsed if dt is not None]
        output_path = self.export_dir / "chart_timeline.png"
        if not dated:
            self.timeline_chart.set_chart_pixmap(None, "No recoverable timestamps were available for a visual timeline.")
            return

        plt.close("all")
        fig, ax = plt.subplots(figsize=(12.8, 4.5), dpi=180)
        fig.patch.set_facecolor("#07111a")
        ax.set_facecolor("#07111a")

        x_values = [dt for _, dt in dated]
        y_values = list(range(len(dated), 0, -1))
        ax.plot(x_values, y_values, color="#2ecfff", linewidth=1.8, alpha=0.55, zorder=2)

        risk_edge = {"High": "#ff8fa4", "Medium": "#ffd166", "Low": "#61e3a8"}
        source_fill = {
            "Embedded EXIF": "#1ca8ff",
            "Filename Pattern": "#ffd166",
            "Filesystem Modified Time": "#f7a35c",
            "Filesystem Created Time": "#f7a35c",
            "Unavailable": "#8c6cff",
        }
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
            if record.parser_status != "Valid" or record.format_trust != "Verified":
                ax.text(dt, y - 0.95, "parser/trust review", color="#ffcf7a", fontsize=6.8, ha="center", zorder=6)

        for (_, prev_dt), (_, curr_dt) in zip(dated, dated[1:]):
            gap = curr_dt - prev_dt
            if gap.total_seconds() >= 4 * 3600:
                midpoint = prev_dt + gap / 2
                ax.axvspan(prev_dt, curr_dt, color="#10314d", alpha=0.12, zorder=1)
                ax.text(midpoint, min(y_values) - 0.58, f"Gap {str(gap).split('.')[0]}", color="#89b9d9", fontsize=7, ha="center")

        ax.text(0.99, 1.02, "Marker fill = time source | Border = risk level", transform=ax.transAxes, ha="right", va="bottom", color="#8fb7d6", fontsize=8)
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
        fig.patch.set_facecolor("#07111a")
        ax.set_facecolor("#07111a")
        colors = ["#69d6ff", "#7ff0d2", "#9ba9ff", "#ffd479"]
        positions = range(len(labels))
        if horizontal:
            bars = ax.barh(list(positions), values, color=colors[: len(labels)], edgecolor="#f2fbff", linewidth=0.5)
            ax.set_yticks(list(positions))
            ax.set_yticklabels(labels, color="#eef8ff", fontsize=9)
            ax.tick_params(axis="x", colors="#dcefff", labelsize=8)
            for bar, value in zip(bars, values):
                ax.text(value + 0.05, bar.get_y() + bar.get_height() / 2, str(value), va="center", color="#ffffff", fontsize=9, weight="bold")
        else:
            bars = ax.bar(list(positions), values, color=colors[: len(labels)], edgecolor="#f2fbff", linewidth=0.5)
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
        self.export_badge.setText("Report Package Generated")
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
        parser_issues = sum(1 for r in records if r.parser_status != "Valid" or r.format_trust != "Verified")
        dominant_source = max({r.source_type for r in records}, key=lambda s: sum(1 for r in records if r.source_type == s))
        blocks = [
            f"Total evidence items: {total}",
            f"Dominant source profile: {dominant_source}",
            f"GPS-bearing media: {gps} | Duplicate clusters: {duplicates}",
            f"Risk distribution: {high} high / {medium} medium review items",
            f"Parser / trust alerts: {parser_issues}",
        ]
        if screenshots == total:
            blocks.append("Interpretation: the case is dominated by screenshots or messaging exports, so native EXIF depth will be limited and filename/time correlation becomes more important.")
        elif gps > 0:
            blocks.append("Interpretation: part of the evidence set supports map-based correlation, which strengthens movement and scene reconstruction.")
        else:
            blocks.append("Interpretation: this batch behaves primarily as non-location media, so provenance, timestamps, and source continuity should drive the narrative.")
        blocks.append("Review posture: prioritize files with parser failures, trust mismatches, or editor/export indicators before reviewing low-risk artifacts.")
        return "\n\n".join(blocks)
    def _build_priority_text(self) -> str:
        records = self.case_manager.records
        if not records:
            return "Case priorities will appear here after evidence is loaded."
        ordered = sorted(records, key=lambda r: (-r.suspicion_score, r.evidence_id))[:5]
        lines = []
        for idx, record in enumerate(ordered, start=1):
            why = record.anomaly_reasons[0] if record.anomaly_reasons else "No explicit anomaly note."
            lines.append(
                f"{idx}. {record.evidence_id} — {record.risk_level} / Score {record.suspicion_score} / {record.source_type}\n"
                f"   Parser: {record.parser_status} • Trust: {record.format_trust}\n"
                f"   Why it matters: {why}"
            )
        lines.extend([
            "",
            "Recommended next steps:",
            "Validate time anchors against chats, uploads, or witness timelines.",
            "Use duplicate clusters to collapse redundant review and isolate derivative media.",
            "Prioritize parser failures, trust mismatches, and GPS-enabled files first.",
        ])
        return "\n\n".join(lines)
    def _build_verdict_panel_text(self, record: EvidenceRecord) -> str:
        lines = [
            f"Record: {record.evidence_id}",
            f"Likely profile: {record.source_type}",
            f"Overall posture: {record.risk_level}",
            f"Confidence: {record.confidence_score}%",
            f"Timestamp anchor: {record.timestamp_source}",
            f"Parser / Structure: {record.parser_status} / {record.structure_status}",
            f"Format trust: {record.format_trust} ({record.format_signature})",
            f"Location signal: {'Present' if record.has_gps else 'Missing'}",
            f"Duplicate relation: {record.duplicate_group or 'None'}",
            "",
            "Score breakdown:",
            f"• Authenticity: {record.authenticity_score}",
            f"• Metadata depth: {record.metadata_score}",
            f"• Technical / parser risk: {record.technical_score}",
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
