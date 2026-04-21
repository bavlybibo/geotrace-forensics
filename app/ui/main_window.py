from __future__ import annotations

import logging
import os
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from PyQt5.QtCore import QObject, QSettings, QSize, Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QColor, QDesktopServices, QIcon, QImage, QKeySequence, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QShortcut,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from PIL import Image, ImageSequence

from app.core.anomalies import parse_timestamp
from app.core.case_manager import AnalysisCancelled, CaseManager
from app.core.map_service import MapService
from app.core.models import EvidenceRecord
from app.core.report_service import ReportService
from app.config import APP_NAME, APP_ORGANIZATION, APP_VERSION, APP_BUILD_CHANNEL, DEFAULT_ANALYST_NAME
from .styles import APP_STYLESHEET
from .dialogs import CompareDialog, DuplicateReviewDialog, OnboardingDialog, RecentCasesDialog, SettingsDialog, ToastPopup
from .widgets import AutoHeightNarrativeView, CaseListCard, ChartCard, EvidenceListCard, ResizableImageLabel, ScoreRing, SmoothScrollArea, StatCard, TerminalView


class AnalysisWorker(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, manager: CaseManager, paths: List[Path]) -> None:
        super().__init__()
        self.manager = manager
        self.paths = paths
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            records = self.manager.load_images(
                self.paths,
                progress_callback=lambda value, text: self.progress.emit(value, text),
                cancel_callback=lambda: self._cancelled,
            )
        except AnalysisCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.error.emit(str(exc))
        else:
            self.finished.emit(records)


class ReportWorker(QObject):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, report_service: ReportService, records: List[EvidenceRecord], case_id: str, case_name: str, custody_log: str) -> None:
        super().__init__()
        self.report_service = report_service
        self.records = records
        self.case_id = case_id
        self.case_name = case_name
        self.custody_log = custody_log

    def run(self) -> None:
        try:
            html_path = self.report_service.export_html(self.records, self.case_id, self.case_name, custody_log=self.custody_log)
            pdf_path = self.report_service.export_pdf(self.records, self.case_id, self.case_name)
            csv_path = self.report_service.export_csv(self.records)
            json_path = self.report_service.export_json(self.records)
            courtroom_path = self.report_service.export_courtroom_summary(self.records, self.case_id, self.case_name)
            self.finished.emit(
                {
                    "html": str(html_path),
                    "pdf": str(pdf_path),
                    "csv": str(csv_path),
                    "json": str(json_path),
                    "courtroom": str(courtroom_path),
                }
            )
        except Exception as exc:
            self.error.emit(str(exc))


class GeoTraceMainWindow(QMainWindow):
    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.project_root = project_root
        self.settings = QSettings(APP_ORGANIZATION, APP_NAME)
        self.logger = self._build_logger()
        self.case_manager = CaseManager(project_root)
        self.records: List[EvidenceRecord] = list(self.case_manager.records)
        self.filtered_records: List[EvidenceRecord] = list(self.records)
        self.pending_batches: List[List[Path]] = []
        self.current_batch_manifest: List[Path] = []
        self.last_export_payload: Dict[str, str] = {}
        self.last_error_message: str = ''
        self.current_preview_pixmap: Optional[QPixmap] = None
        self.current_map_path: Optional[Path] = None
        self.assets_dir = project_root / "assets"
        self.export_dir = self._case_export_dir()
        self.map_service = MapService(self.export_dir)
        self.report_service = ReportService(self.export_dir)
        self.analysis_thread: Optional[QThread] = None
        self.analysis_worker: Optional[AnalysisWorker] = None
        self.report_thread: Optional[QThread] = None
        self.report_worker: Optional[ReportWorker] = None
        self.thumbnail_cache: Dict[str, QPixmap] = {}
        self.preview_cache: Dict[str, Optional[QPixmap]] = {}
        self.frame_cache: Dict[str, List[QPixmap]] = {}
        self.current_frames: List[QPixmap] = []
        self.current_frame_index = 0
        self.current_frame_record: Optional[str] = None
        self.note_templates = {
            "Initial triage": "Initial review summary:\nObserved:\nInferred:\nNeeds confirmation:\n",
            "Timeline anchor": "Timeline anchor note:\nRecovered time source:\nExternal corroboration needed:\n",
            "Courtroom caveat": "Courtroom caveat:\nLimitations:\nSecondary validation required before courtroom use:\n",
            "OSINT follow-up": "OSINT / next pivots:\n1)\n2)\n3)\n",
            "Duplicate workflow": "Duplicate / derivative review:\nCluster relation:\nPrimary source candidate:\nNeed compare with:\n",
        }

        self.setAcceptDrops(True)
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION} — Image Metadata & Geolocation Analysis")
        self.resize(1720, 1020)
        self.setMinimumSize(1280, 780)
        self.setStyleSheet(APP_STYLESHEET)
        icon_path = self.assets_dir / "app_icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self._build_ui()
        self._setup_shortcuts()
        self._apply_startup_settings()
        self._refresh_case_badges()
        self.refresh_dashboard()
        self.update_charts()
        self.populate_timeline()
        self.populate_custody_log()
        self._refresh_batch_queue_view()
        self._refresh_cases_page()
        self.clear_details()
        QTimer.singleShot(120, self._show_onboarding_if_needed)

    def _build_logger(self) -> logging.Logger:
        logs_dir = self.project_root / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger(f"geotrace-ui-{id(self)}")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        handler = logging.FileHandler(logs_dir / "app_errors.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        logger.addHandler(handler)
        return logger

    def _startup_settings(self) -> Dict[str, object]:
        return {
            "analyst_name": self.settings.value("analyst_name", DEFAULT_ANALYST_NAME),
            "default_page": self.settings.value("default_page", "Dashboard"),
            "default_sort": self.settings.value("default_sort", "Score ↓"),
            "auto_reopen_last_case": self.settings.value("auto_reopen_last_case", True, type=bool),
            "open_reports_after_export": self.settings.value("open_reports_after_export", True, type=bool),
            "show_toasts": self.settings.value("show_toasts", True, type=bool),
            "confirm_before_new_case": self.settings.value("confirm_before_new_case", True, type=bool),
            "show_onboarding": self.settings.value("show_onboarding", True, type=bool),
        }

    def _apply_startup_settings(self) -> None:
        values = self._startup_settings()
        self.analyst_name = str(values["analyst_name"])
        if hasattr(self, "sort_combo"):
            self.sort_combo.setCurrentText(str(values["default_sort"]))
        self._set_workspace_page(str(values["default_page"]))

    def _show_onboarding_if_needed(self) -> None:
        if not bool(self._startup_settings().get("show_onboarding", True)):
            return
        if self.settings.value("onboarding_seen_once", False, type=bool):
            return
        dialog = OnboardingDialog(self)
        if dialog.exec_():
            self.settings.setValue("onboarding_seen_once", True)
            self.settings.setValue("show_onboarding", not dialog.hide_future.isChecked())
            if dialog.selected_action == "demo":
                demo_dir = self.project_root / "demo_evidence"
                if demo_dir.exists():
                    self._start_analysis([demo_dir])
            elif dialog.selected_action == "import":
                self.import_images()
            elif dialog.selected_action == "cases":
                self._set_workspace_page("Cases")

    def _setup_shortcuts(self) -> None:
        shortcuts = {
            "Ctrl+N": self.start_new_case,
            "Ctrl+O": self.import_images,
            "Ctrl+Shift+O": self.import_folder,
            "Ctrl+R": self.generate_reports,
            "Ctrl+F": lambda: self.search_box.setFocus(),
            "Ctrl+S": self.save_note_and_tags,
            "Ctrl+,": self.open_settings,
            "Ctrl+Shift+C": self.open_compare_mode,
            "Ctrl+Shift+D": self.open_duplicate_review,
            "Ctrl+1": lambda: self._set_workspace_page("Dashboard"),
            "Ctrl+2": lambda: self._set_workspace_page("Review"),
            "Ctrl+3": lambda: self._set_workspace_page("Geo"),
            "Ctrl+4": lambda: self._set_workspace_page("Timeline"),
            "Ctrl+5": lambda: self._set_workspace_page("Custody"),
            "Ctrl+6": lambda: self._set_workspace_page("Reports"),
            "Ctrl+7": lambda: self._set_workspace_page("Cases"),
        }
        self._shortcuts = []
        for key, callback in shortcuts.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def _show_toast(self, title: str, message: str, tone: str = "info") -> None:
        if not self.settings.value("show_toasts", True, type=bool):
            return
        toast = ToastPopup(self, title, message, tone=tone)
        toast.show_top_right()

    def _log_error(self, context: str, message: str) -> None:
        self.last_error_message = f"{context}: {message}"
        self.logger.error(self.last_error_message)
        if hasattr(self, "error_log_view"):
            existing = self.error_log_view.toPlainText().strip()
            combined = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {self.last_error_message}"
            self.error_log_view.setPlainText(((combined + "\n\n" + existing) if existing else combined).strip())
        self._show_toast("Error logged", context, tone="error")

    def _refresh_batch_queue_view(self) -> None:
        if not hasattr(self, "batch_queue_view"):
            return
        lines = []
        if self.current_batch_manifest:
            lines.append("Current batch:")
            lines.append(f"- {len(self.current_batch_manifest)} path(s) in active analysis")
            for path in self.current_batch_manifest[:5]:
                lines.append(f"  • {path.name}")
        else:
            lines.append("No active analysis batch.")
        lines.append("")
        lines.append(f"Queued batches: {len(self.pending_batches)}")
        for idx, batch in enumerate(self.pending_batches[:6], start=1):
            names = ", ".join(path.name for path in batch[:3])
            if len(batch) > 3:
                names += f" … (+{len(batch) - 3} more)"
            lines.append(f"{idx}. {len(batch)} path(s) — {names}")
        self.batch_queue_view.setPlainText("\n".join(lines).strip())

    def _queue_or_start_analysis(self, paths: List[Path]) -> None:
        if self.analysis_thread is not None:
            self.pending_batches.append(paths)
            self.command_progress.setText(f"Batch queued ({len(self.pending_batches)} waiting)")
            self._refresh_batch_queue_view()
            self._show_toast("Batch queued", f"Queued {len(paths)} path(s) to start after the current batch.", tone="info")
            return
        self._start_analysis(paths)

    def _consume_next_batch(self) -> None:
        if self.analysis_thread is not None or not self.pending_batches:
            return
        next_batch = self.pending_batches.pop(0)
        self._refresh_batch_queue_view()
        self._start_analysis(next_batch)

    def _refresh_cases_page(self) -> None:
        if not hasattr(self, "cases_summary"):
            return
        cases = self.case_manager.list_cases()
        lines = [f"Total cases in library: {len(cases)}", f"Active case: {self.case_manager.active_case_id} — {self.case_manager.active_case_name}", "", "Recent cases:"]
        for case in cases[:10]:
            lines.append(f"- {case.case_name} | {case.case_id} | {case.item_count} item(s) | updated {case.updated_at}")
        self.cases_summary.setPlainText("\n".join(lines))
        self.cases_list.clear()
        for case in cases:
            item = QListWidgetItem(f"{case.case_name} — {case.case_id} — {case.item_count} item(s)")
            item.setData(Qt.UserRole, case.case_id)
            self.cases_list.addItem(item)
            if case.case_id == self.case_manager.active_case_id:
                self.cases_list.setCurrentItem(item)

    def _case_export_dir(self) -> Path:
        path = self.project_root / "exports" / self.case_manager.active_case_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _build_ui(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(10)

        outer.addWidget(self._build_header())
        outer.addWidget(self._build_command_bar())
        outer.addWidget(self._build_page_bar())
        outer.addWidget(self._build_content_pages(), 1)
        self.setCentralWidget(central)

    def _build_header(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("HeaderFrame")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(6)
        title = QLabel("GeoTrace Forensics X")
        title.setObjectName("TitleLabel")
        subtitle = QLabel(
            "Case-based forensic workspace with preview-first review, cleaner page separation, and isolated custody by design."
        )
        subtitle.setObjectName("SubtitleLabel")
        subtitle.setWordWrap(True)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        self.case_badge = QLabel()
        self.case_badge.setObjectName("BadgeLabel")
        self.mode_badge = QLabel("Preview-first review")
        self.mode_badge.setObjectName("BadgeLabel")
        self.export_badge = QLabel("Export hub idle")
        self.export_badge.setObjectName("BadgeLabel")
        for badge in [self.case_badge, self.mode_badge, self.export_badge]:
            badge_row.addWidget(badge)
        badge_row.addStretch(1)

        left.addWidget(title)
        left.addWidget(subtitle)
        left.addLayout(badge_row)

        right = QGridLayout()
        right.setHorizontalSpacing(10)
        right.setVerticalSpacing(10)
        self.case_label = self._info_badge("Case ID", "—")
        self.status_label = self._info_badge("Status", "Awaiting evidence")
        self.integrity_label = self._info_badge("Case Integrity", "0/0 Verified")
        self.method_label = self._info_badge("Workflow", "Page-based investigation")
        right.addWidget(self.case_label, 0, 0)
        right.addWidget(self.status_label, 0, 1)
        right.addWidget(self.integrity_label, 1, 0)
        right.addWidget(self.method_label, 1, 1)

        layout.addLayout(left, 6)
        layout.addLayout(right, 4)
        return frame

    def _build_command_bar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("PanelFrame")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(8)

        row_top = QHBoxLayout()
        row_top.setSpacing(6)
        row_bottom = QHBoxLayout()
        row_bottom.setSpacing(8)

        self.btn_new_case = QPushButton("New Case")
        self.btn_new_case.setObjectName("PrimaryButton")
        self.btn_new_case.clicked.connect(self.start_new_case)

        self.btn_load_images = QPushButton("Files")
        self.btn_load_images.clicked.connect(self.import_images)
        self.btn_load_images.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))

        self.btn_load_folder = QPushButton("Folder")
        self.btn_load_folder.clicked.connect(self.import_folder)
        self.btn_load_folder.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))

        self.btn_cancel_analysis = QPushButton("Cancel")
        self.btn_cancel_analysis.clicked.connect(self.cancel_analysis)
        self.btn_cancel_analysis.setEnabled(False)

        self.btn_generate_report = QPushButton("Report")
        self.btn_generate_report.clicked.connect(self.generate_reports)
        self.btn_generate_report.setEnabled(False)

        self.btn_courtroom = QPushButton("Courtroom")
        self.btn_courtroom.clicked.connect(self.generate_reports)
        self.btn_courtroom.setEnabled(False)

        self.btn_open_map = QPushButton("Map")
        self.btn_open_map.clicked.connect(self.open_map)
        self.btn_open_map.setEnabled(False)
        self.btn_open_map.setObjectName("GhostButton")

        self.btn_open_exports = QPushButton("Exports")
        self.btn_open_exports.clicked.connect(lambda: self._set_workspace_page("Reports"))

        self.btn_compare = QPushButton("Compare")
        self.btn_compare.clicked.connect(self.open_compare_mode)
        self.btn_compare.setEnabled(False)

        self.btn_recent_cases = QPushButton("Recent")
        self.btn_recent_cases.clicked.connect(self.open_recent_cases_dialog)

        self.btn_settings = QPushButton("Prefs")
        self.btn_settings.clicked.connect(self.open_settings)

        self.command_progress = QLabel("Ready")
        self.command_progress.setObjectName("PreviewStateBadge")

        self.case_switch_combo = QComboBox()
        self.case_switch_combo.setMinimumWidth(320)
        self.case_switch_combo.currentIndexChanged.connect(self._switch_case_from_combo)

        for btn in [
            self.btn_new_case,
            self.btn_load_images,
            self.btn_load_folder,
            self.btn_cancel_analysis,
            self.btn_generate_report,
            self.btn_courtroom,
            self.btn_open_map,
            self.btn_open_exports,
            self.btn_compare,
            self.btn_recent_cases,
            self.btn_settings,
        ]:
            row_top.addWidget(btn)
        row_top.addStretch(1)

        switch_label = QLabel("Case Switcher")
        switch_label.setObjectName("MutedLabel")
        self.command_hint = QLabel("Ctrl+2 Review • Ctrl+Shift+C Compare • Ctrl+R Report")
        self.command_hint.setObjectName("MutedLabel")
        row_bottom.addWidget(switch_label)
        row_bottom.addWidget(self.case_switch_combo, 1)
        row_bottom.addStretch(1)
        row_bottom.addWidget(self.command_hint)
        row_bottom.addWidget(self.command_progress)

        outer.addLayout(row_top)
        outer.addLayout(row_bottom)
        return frame

    def _build_page_bar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("CompactPanel")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        self.page_buttons = {}
        for key in ["Dashboard", "Review", "Geo", "Timeline", "Custody", "Reports", "Cases"]:
            btn = QPushButton(key)
            btn.setObjectName("PageButton")
            btn.clicked.connect(lambda checked=False, page=key: self._set_workspace_page(page))
            layout.addWidget(btn)
            self.page_buttons[key] = btn
        layout.addStretch(1)
        hint = QLabel(f"{APP_NAME} {APP_VERSION} • page-based investigation")
        hint.setObjectName("MutedLabel")
        layout.addWidget(hint)
        return frame

    def _info_badge(self, title: str, value: str) -> QLabel:
        label = QLabel(f"<div><span style='color:#86a8c2;font-size:8.8pt;'>{title}</span><br><span style='font-weight:800;color:#f5fbff;'>{value}</span></div>")
        label.setObjectName("InfoBadge")
        label.setTextFormat(Qt.RichText)
        return label

    def _build_content_pages(self) -> QWidget:
        self.workspace_stack = QStackedWidget()
        self.dashboard_page = self._wrap_page(self._build_dashboard_page(), scrollable=True)
        self.review_page = self._build_review_page()
        self.geo_page = self._wrap_page(self._build_geo_page(), scrollable=True)
        self.timeline_page = self._wrap_page(self._build_timeline_page(), scrollable=True)
        self.custody_page = self._wrap_page(self._build_custody_page(), scrollable=True)
        self.reports_page = self._wrap_page(self._build_reports_page(), scrollable=True)
        self.cases_page = self._wrap_page(self._build_cases_page(), scrollable=True)
        self.workspace_pages = {
            "Dashboard": self.dashboard_page,
            "Review": self.review_page,
            "Geo": self.geo_page,
            "Timeline": self.timeline_page,
            "Custody": self.custody_page,
            "Reports": self.reports_page,
            "Cases": self.cases_page,
        }
        for key in ["Dashboard", "Review", "Geo", "Timeline", "Custody", "Reports", "Cases"]:
            self.workspace_stack.addWidget(self.workspace_pages[key])
        self._set_workspace_page("Dashboard")
        return self.workspace_stack

    def _wrap_page(self, widget: QWidget, scrollable: bool = False) -> QWidget:
        if not scrollable:
            return widget
        scroll = SmoothScrollArea()
        scroll.setWidget(widget)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        return scroll

    def _build_dashboard_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._build_stat_cards())

        top_split = QSplitter(Qt.Horizontal)
        top_split.setChildrenCollapsible(False)
        top_split.addWidget(self._shell(
            "Case Snapshot",
            self._build_dashboard_summary_body(),
            "Executive orientation first. This page exists to tell you what kind of case you opened before you dive into evidence.",
        ))
        charts = QWidget()
        charts_layout = QGridLayout(charts)
        charts_layout.setContentsMargins(0, 0, 0, 0)
        charts_layout.setHorizontalSpacing(12)
        charts_layout.setVerticalSpacing(12)
        self.chart_sources = ChartCard("Source Profile Mix", "Adaptive view for small or empty cases.")
        self.chart_risks = ChartCard("Risk Mix", "Distribution overview without crowding the review screen.")
        self.chart_geo = ChartCard("GPS & Duplicate Coverage", "Counters or charts depending on case size.")
        self.chart_relationships = ChartCard("Relationship Graph", "Appears only when meaningful links exist.")
        charts_layout.addWidget(self.chart_sources, 0, 0)
        charts_layout.addWidget(self.chart_risks, 0, 1)
        charts_layout.addWidget(self.chart_geo, 1, 0)
        charts_layout.addWidget(self.chart_relationships, 1, 1)
        charts_layout.setColumnStretch(0, 1)
        charts_layout.setColumnStretch(1, 1)
        top_split.addWidget(charts)
        top_split.setSizes([420, 940])

        self.duplicate_terminal = AutoHeightNarrativeView("Visual diff and duplicate reuse notes will appear here.", max_auto_height=260)
        layout.addWidget(top_split, 1)
        layout.addWidget(self._shell(
            "Visual Diff & Reuse Review",
            self.duplicate_terminal,
            "No duplicate clusters becomes a designed state instead of a stretched empty chart.",
        ))
        return widget

    def _build_dashboard_summary_body(self) -> QWidget:
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.summary_text = AutoHeightNarrativeView("Load evidence to generate a case-wide assessment.", max_auto_height=220)
        self.dashboard_priority_text = AutoHeightNarrativeView("Priority queue will appear here after evidence is loaded.", max_auto_height=240)
        layout.addWidget(self.summary_text)
        layout.addWidget(self.dashboard_priority_text)
        return body

    def _build_stat_cards(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("PanelFrame")
        layout = QGridLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(10)

        self.card_total = StatCard("Total", chip="Inventory")
        self.card_high = StatCard("High Risk", chip="Priority")
        self.card_gps = StatCard("GPS", chip="Geo")
        self.card_duplicates = StatCard("Duplicates", chip="Correlation")
        self.card_timeline = StatCard("Timeline", chip="Span")
        self.card_integrity = StatCard("Integrity", chip="Custody")

        cards = [self.card_total, self.card_high, self.card_gps, self.card_duplicates, self.card_timeline, self.card_integrity]
        for idx, card in enumerate(cards):
            layout.addWidget(card, 0, idx)
            layout.setColumnStretch(idx, 1)

        self.card_total.clicked.connect(lambda: self._activate_filter("All Evidence"))
        self.card_high.clicked.connect(lambda: self._activate_filter("High Risk"))
        self.card_gps.clicked.connect(lambda: self._activate_filter("Has GPS"))
        self.card_duplicates.clicked.connect(lambda: self._activate_filter("Duplicate Cluster"))
        self.card_timeline.clicked.connect(lambda: self._set_workspace_page("Timeline"))
        self.card_integrity.clicked.connect(lambda: self._set_workspace_page("Custody"))
        return frame

    def _build_review_page(self) -> QWidget:
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setOpaqueResize(False)
        splitter.addWidget(self._build_inventory_panel())
        splitter.addWidget(self._build_review_center())
        splitter.addWidget(self._build_review_sidebar())
        splitter.setSizes([310, 980, 330])
        return splitter

    def _build_inventory_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("PanelFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Evidence")
        title.setObjectName("SectionLabel")
        meta = QLabel("Compact triage list with premium cards, one vertical scroll, and no giant table wall.")
        meta.setObjectName("SectionMetaLabel")

        self.inventory_meta = QLabel("No evidence loaded in the current case.")
        self.inventory_meta.setObjectName("MutedLabel")

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search all fields… try gps:yes risk:high parser:failed hidden:yes url:yes tag:foo note:bar")
        self.search_box.textChanged.connect(self.apply_filters)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
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
            "Bookmarked",
        ])
        self.filter_combo.currentTextChanged.connect(self.apply_filters)
        filter_row.addWidget(self.filter_combo)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Score ↓", "Time ↑", "Time ↓", "Filename A→Z", "Filename Z→A", "Confidence ↓", "Bookmarked First"])
        self.sort_combo.currentTextChanged.connect(self.apply_filters)
        filter_row.addWidget(self.sort_combo)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Ready")

        self.inventory_list = QListWidget()
        self.inventory_list.setObjectName("EvidenceList")
        self.inventory_list.setSpacing(8)
        self.inventory_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.inventory_list.currentItemChanged.connect(self.populate_details)

        layout.addWidget(title)
        layout.addWidget(meta)
        layout.addWidget(self.inventory_meta)
        layout.addWidget(self.search_box)
        layout.addLayout(filter_row)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.inventory_list, 1)
        return frame

    def _build_review_center(self) -> QWidget:
        self.review_tabs = QTabWidget()
        self.review_tabs.setObjectName("ReviewTabs")

        self.review_tab_preview = self._build_preview_shell()
        self.review_tab_overview = self._build_overview_tab()
        self.review_tab_metadata = self._build_metadata_panel()
        self.review_tab_hidden = self._build_hidden_content_tab()
        self.review_tab_notes = self._build_notes_tab()
        self.review_tab_audit = self._build_review_audit_tab()

        self.review_tabs.addTab(self.review_tab_preview, "Preview")
        self.review_tabs.addTab(self.review_tab_overview, "Overview")
        self.review_tabs.addTab(self.review_tab_metadata, "Metadata")
        self.review_tabs.addTab(self.review_tab_hidden, "Hidden / Code")
        self.review_tabs.addTab(self.review_tab_notes, "Notes")
        self.review_tabs.addTab(self.review_tab_audit, "Audit")
        return self.review_tabs

    def _build_overview_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.review_time_shell = self._preview_meta_block("Recovered Time", "—")
        self.review_file_shell = self._preview_meta_block("Evidence", "—")
        self.review_profile_shell = self._preview_meta_block("Source Profile", "—")
        top_grid = QGridLayout()
        top_grid.setHorizontalSpacing(10)
        top_grid.setVerticalSpacing(10)
        top_grid.addWidget(self.review_time_shell, 0, 0, 1, 2)
        top_grid.addWidget(self.review_file_shell, 1, 0)
        top_grid.addWidget(self.review_profile_shell, 1, 1)
        layout.addLayout(top_grid)

        self.metadata_overview = AutoHeightNarrativeView("Metadata overview will appear here.", max_auto_height=340)
        layout.addWidget(self._shell("Metadata Overview", self.metadata_overview, "Readable summary first. Technical dumps stay hidden until requested."))

        quick = QHBoxLayout()
        quick.setSpacing(8)
        self.btn_review_export = QPushButton("Export This Case")
        self.btn_review_export.setObjectName("SmallGhostButton")
        self.btn_review_export.clicked.connect(self.generate_reports)
        self.btn_review_compare = QPushButton("Compare Selected")
        self.btn_review_compare.setObjectName("SmallGhostButton")
        self.btn_review_compare.clicked.connect(self.open_compare_mode)
        quick.addWidget(self.btn_review_export)
        quick.addWidget(self.btn_review_compare)
        quick.addStretch(1)
        self.review_hint_label = QLabel("Quick actions: F fullscreen • +/- zoom • Ctrl+S save note")
        self.review_hint_label.setObjectName("MutedLabel")
        quick.addWidget(self.review_hint_label)
        layout.addLayout(quick)
        layout.addStretch(1)
        return widget

    def _build_notes_tab(self) -> QWidget:
        notes_shell = QFrame()
        notes_shell.setObjectName("CompactPanel")
        notes_layout = QVBoxLayout(notes_shell)
        notes_layout.setContentsMargins(12, 12, 12, 12)
        notes_layout.setSpacing(8)
        notes_label = QLabel("Case Notes, Tags & Bookmarks")
        notes_label.setObjectName("SectionLabel")
        notes_meta = QLabel("Keep analyst notes on their own tab so the preview stage stays clean and readable.")
        notes_meta.setObjectName("SectionMetaLabel")
        template_row = QHBoxLayout()
        template_row.setSpacing(8)
        self.note_template_combo = QComboBox()
        self.note_template_combo.addItems(["Choose template…", *self.note_templates.keys()])
        apply_template_button = QPushButton("Insert Template")
        apply_template_button.clicked.connect(self.insert_note_template)
        template_row.addWidget(self.note_template_combo)
        template_row.addWidget(apply_template_button)
        self.note_editor = QTextEdit()
        self.note_editor.setPlaceholderText("Add analyst observations, correlation ideas, or courtroom caveats for the selected evidence item…")
        self.note_editor.setMinimumHeight(180)
        self.tags_editor = QLineEdit()
        self.tags_editor.setPlaceholderText("Tags (comma-separated), e.g. malformed, timeline-anchor, priority-review")
        self.bookmark_checkbox = QCheckBox("Pin / bookmark selected evidence")
        save_button = QPushButton("Save Notes & Tags")
        save_button.clicked.connect(self.save_note_and_tags)
        notes_layout.addWidget(notes_label)
        notes_layout.addWidget(notes_meta)
        notes_layout.addLayout(template_row)
        notes_layout.addWidget(self.note_editor)
        notes_layout.addWidget(self.tags_editor)
        notes_layout.addWidget(self.bookmark_checkbox)
        notes_layout.addWidget(save_button, alignment=Qt.AlignLeft)
        return notes_shell

    def _build_hidden_content_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.hidden_overview_view = AutoHeightNarrativeView("Hidden-content scan results will appear here.", max_auto_height=220)
        self.hidden_code_view = TerminalView("Code-like markers, URLs, and embedded strings will appear here when detected.")
        layout.addWidget(self._shell("Embedded Text & Code Scan", self.hidden_overview_view, "Byte-level heuristics look for readable strings, URLs, and obvious script or credential markers hidden inside the container."))
        layout.addWidget(self._shell("Recovered Markers", self.hidden_code_view, "Heuristic view only: readable payloads do not automatically prove exploitability."), 1)
        return widget

    def _build_review_audit_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.review_audit_view = TerminalView("Select an evidence item to load its case-scoped audit activity.")
        layout.addWidget(self._shell("Evidence Audit Trail", self.review_audit_view, "Case-scoped events filtered to the selected evidence item so note, import, and analysis activity stay visible during review."), 1)
        return widget

    def _build_review_sidebar(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        verdict = QFrame()
        verdict.setObjectName("VerdictPanel")
        verdict_layout = QVBoxLayout(verdict)
        verdict_layout.setContentsMargins(14, 14, 14, 14)
        verdict_layout.setSpacing(10)
        top_title = QLabel("Decision Rail")
        top_title.setObjectName("SectionLabel")
        top_meta = QLabel("Score, confidence, four priority facts, one verdict block, then concise next steps.")
        top_meta.setObjectName("SectionMetaLabel")
        self.score_ring = ScoreRing(104)
        self.confidence_bar = QProgressBar()
        self.confidence_bar.setObjectName("ConfidenceBar")
        self.confidence_bar.setRange(0, 100)
        self.confidence_bar.setTextVisible(False)
        self.confidence_bar_label = QLabel("0% analyst confidence")
        self.confidence_bar_label.setObjectName("MutedLabel")

        facts = QGridLayout()
        facts.setHorizontalSpacing(8)
        facts.setVerticalSpacing(8)
        self.badge_parser = self._micro_badge("Parser / Trust: —")
        self.badge_time = self._micro_badge("Time Anchor: —")
        self.badge_source = self._micro_badge("Source Profile: —")
        self.badge_gps = self._micro_badge("GPS: —")
        for idx, badge in enumerate([self.badge_parser, self.badge_time, self.badge_source, self.badge_gps]):
            facts.addWidget(badge, idx // 2, idx % 2)

        self.badge_signature = self._micro_badge("Signature: —")
        self.badge_trust = self._micro_badge("Trust: —")
        self.badge_risk = self._risk_badge("Risk: —", "Low")
        self.badge_format = self._micro_badge("Format: —")

        self.score_auth_badge = QLabel("Authenticity 0")
        self.score_auth_badge.setObjectName("ScoreBreakdownBadge")
        self.score_meta_badge = QLabel("Metadata 0")
        self.score_meta_badge.setObjectName("ScoreBreakdownBadge")
        self.score_tech_badge = QLabel("Technical 0")
        self.score_tech_badge.setObjectName("ScoreBreakdownBadge")
        scores_row = QHBoxLayout()
        scores_row.setSpacing(8)
        scores_row.addWidget(self.score_auth_badge)
        scores_row.addWidget(self.score_meta_badge)
        scores_row.addWidget(self.score_tech_badge)

        self.selection_verdict_view = AutoHeightNarrativeView("Select an item to load a focused verdict summary.", max_auto_height=150)
        self.review_pivots_text = AutoHeightNarrativeView("Select evidence to load next-step pivots.", max_auto_height=170)
        verdict_layout.addWidget(top_title)
        verdict_layout.addWidget(top_meta)
        verdict_layout.addWidget(self.score_ring, alignment=Qt.AlignHCenter)
        verdict_layout.addWidget(self.confidence_bar)
        verdict_layout.addWidget(self.confidence_bar_label)
        verdict_layout.addLayout(facts)
        verdict_layout.addLayout(scores_row)
        verdict_layout.addWidget(self._shell("Analyst Verdict", self.selection_verdict_view, "Observed posture first, then what still needs confirmation."))
        verdict_layout.addWidget(self._shell("Next Steps", self.review_pivots_text, "Concise pivots only — no repeated narrative blocks."))

        layout.addWidget(verdict)
        layout.addStretch(1)
        return widget

    def _build_preview_shell(self) -> QWidget:
        preview_shell = QFrame()
        preview_shell.setObjectName("HeroPreviewPanel")
        layout = QVBoxLayout(preview_shell)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        title = QLabel("Evidence Stage")
        title.setObjectName("SectionLabel")
        subtitle = QLabel("Preview stays in front. Use tabs for overview, metadata, hidden-content scan, notes, and audit history.")
        subtitle.setObjectName("SectionMetaLabel")
        left = QVBoxLayout()
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
        self.btn_prev_frame = QPushButton("◀ Frame")
        self.btn_prev_frame.setObjectName("SmallGhostButton")
        self.btn_prev_frame.clicked.connect(self._show_previous_frame)
        self.btn_next_frame = QPushButton("Frame ▶")
        self.btn_next_frame.setObjectName("SmallGhostButton")
        self.btn_next_frame.clicked.connect(self._show_next_frame)
        self.frame_index_badge = QLabel("Frame 0/0")
        self.frame_index_badge.setObjectName("PreviewZoomPill")
        self.btn_fullscreen_preview = QPushButton("Fullscreen")
        self.btn_fullscreen_preview.setObjectName("SmallGhostButton")
        self.btn_fullscreen_preview.clicked.connect(self._open_preview_fullscreen)
        self.btn_open_external = QPushButton("Open Original")
        self.btn_open_external.setObjectName("SmallGhostButton")
        self.btn_open_external.clicked.connect(self.open_selected_file)
        self.btn_export_from_review = QPushButton("Export")
        self.btn_export_from_review.setObjectName("SmallGhostButton")
        self.btn_export_from_review.clicked.connect(self.generate_reports)
        for btn in [self.btn_zoom_out, self.btn_zoom_in, self.btn_zoom_fit, self.btn_zoom_reset, self.btn_prev_frame, self.btn_next_frame]:
            toolbar.addWidget(btn)
        toolbar.addWidget(self.frame_index_badge)
        toolbar.addWidget(self.btn_fullscreen_preview)
        toolbar.addWidget(self.btn_open_external)
        toolbar.addWidget(self.btn_export_from_review)

        state_row = QGridLayout()
        state_row.setHorizontalSpacing(8)
        state_row.setVerticalSpacing(8)
        self.preview_state_badge = QLabel("Preview State: Awaiting selection")
        self.preview_state_badge.setObjectName("PreviewStateBadge")
        self.preview_parser_badge = QLabel("Parser: —")
        self.preview_parser_badge.setObjectName("PreviewStateBadge")
        self.preview_signature_badge = QLabel("Signature: —")
        self.preview_signature_badge.setObjectName("PreviewStateBadge")
        self.preview_trust_badge = QLabel("Trust: —")
        self.preview_trust_badge.setObjectName("PreviewStateBadge")
        for idx, badge in enumerate([self.preview_state_badge, self.preview_parser_badge, self.preview_signature_badge, self.preview_trust_badge]):
            state_row.addWidget(badge, 0, idx)

        hint = QLabel("Keyboard: Ctrl+2 review • F fullscreen • +/- zoom • Ctrl+Shift+C compare")
        hint.setObjectName("MutedLabel")

        preview_frame = QFrame()
        preview_frame.setObjectName("PreviewCanvasFrame")
        preview_frame_layout = QVBoxLayout(preview_frame)
        preview_frame_layout.setContentsMargins(10, 10, 10, 10)
        self.image_preview = ResizableImageLabel("Choose an evidence item to start review. No-selection mode keeps the workspace calm instead of filling the screen with dead panels.", min_height=620)
        self.image_preview.setMinimumHeight(620)
        preview_frame_layout.addWidget(self.image_preview, 1)

        self.preview_file_meta = self._preview_meta_block("Evidence", "—")
        self.preview_source_meta = self._preview_meta_block("Source Profile", "—")
        self.preview_time_meta = self._preview_meta_block("Recovered Time", "—")
        self.preview_geo_meta = self._preview_meta_block("GPS / Geo", "—")

        layout.addLayout(toolbar)
        layout.addLayout(state_row)
        layout.addWidget(hint)
        layout.addWidget(preview_frame, 1)
        return preview_shell

    def _preview_meta_block(self, title: str, value: str) -> QWidget:
        frame = QFrame()
        frame.setObjectName("SecondaryPanel")
        block = QVBoxLayout(frame)
        block.setContentsMargins(12, 10, 12, 10)
        block.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("PreviewMetaTitle")
        value_label = QLabel(value)
        value_label.setObjectName("PreviewMetaValue")
        value_label.setWordWrap(True)
        block.addWidget(title_label)
        block.addWidget(value_label)
        frame.value_label = value_label  # type: ignore[attr-defined]
        return frame

    def _build_metadata_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        meta_intro = QLabel("Technical depth lives here so the preview tab stays clean. Open normalized or raw views only when needed.")
        meta_intro.setObjectName("SectionMetaLabel")
        layout.addWidget(meta_intro)

        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(8)
        self.btn_toggle_normalized = QPushButton("Show Normalized Dump")
        self.btn_toggle_normalized.setObjectName("GhostButton")
        self.btn_toggle_normalized.clicked.connect(lambda: self._toggle_metadata_panel(self.normalized_shell, self.btn_toggle_normalized, "Show Normalized Dump", "Hide Normalized Dump"))
        self.btn_toggle_raw = QPushButton("Show Raw Tags")
        self.btn_toggle_raw.setObjectName("GhostButton")
        self.btn_toggle_raw.clicked.connect(lambda: self._toggle_metadata_panel(self.raw_shell, self.btn_toggle_raw, "Show Raw Tags", "Hide Raw Tags"))
        toggle_row.addWidget(self.btn_toggle_normalized)
        toggle_row.addWidget(self.btn_toggle_raw)
        toggle_row.addStretch(1)
        layout.addLayout(toggle_row)

        self.metadata_view = TerminalView("Normalized metadata will appear here.")
        self.raw_exif_view = TerminalView("Raw EXIF tag view will appear here.")
        self.normalized_shell = self._shell("Normalized Metadata Dump", self.metadata_view, "Structured normalized values for technical review.")
        self.raw_shell = self._shell("Raw EXIF vs Embedded Tags", self.raw_exif_view, "Deep tag-level comparison only when you explicitly need it.")
        self.normalized_shell.hide()
        self.raw_shell.hide()
        layout.addWidget(self.normalized_shell)
        layout.addWidget(self.raw_shell)
        layout.addStretch(1)
        return widget

    def _build_geo_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        hero = QFrame()
        hero.setObjectName("PanelFrame")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(14, 14, 14, 14)
        hero_layout.setSpacing(8)
        title = QLabel("Geo Review")
        title.setObjectName("SectionLabel")
        meta = QLabel("GPS, venue pivots, and map logic live on their own page so they do not crowd the review stage.")
        meta.setObjectName("SectionMetaLabel")
        hero_layout.addWidget(title)
        hero_layout.addWidget(meta)
        layout.addWidget(hero)

        badge_row = QGridLayout()
        badge_row.setHorizontalSpacing(8)
        badge_row.setVerticalSpacing(8)
        self.geo_badge_status = self._micro_badge("GPS State: —")
        self.geo_badge_coords = self._micro_badge("Coordinates: —")
        self.geo_badge_altitude = self._micro_badge("Altitude: —")
        self.geo_badge_map = self._micro_badge("Map Package: —")
        for idx, badge in enumerate([self.geo_badge_status, self.geo_badge_coords, self.geo_badge_altitude, self.geo_badge_map]):
            badge_row.addWidget(badge, 0, idx)
        layout.addLayout(badge_row)

        self.geo_text = AutoHeightNarrativeView("No GPS evidence selected yet.", max_auto_height=240)
        self.geo_leads_text = AutoHeightNarrativeView("Location pivots and next-step suggestions will appear here.", max_auto_height=240)
        layout.addWidget(self._shell("Geo Intelligence", self.geo_text, "Native coordinates when available, or a strong explanation when GPS is absent."))
        layout.addWidget(self._shell("Next Pivots", self.geo_leads_text, "Timestamp, source workflow, upload context, and venue reasoning when native GPS is missing."))
        layout.addStretch(1)
        return widget

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
        self.timeline_narrative = AutoHeightNarrativeView("Timeline narrative generation will appear here after evidence is loaded.", max_auto_height=220)
        self.timeline_text = AutoHeightNarrativeView("Timeline analysis will appear here after evidence is loaded.", max_auto_height=240)
        layout.addWidget(self.timeline_chart, 1)
        layout.addWidget(self._shell("Timeline Narrative", self.timeline_narrative, "Readable chronological story generated from the available anchors and parser context."))
        layout.addWidget(self._shell("Timeline Analyst Notes", self.timeline_text, "Chronological interpretation with parser, signature, and trust context."))
        layout.addStretch(1)
        return widget

    def _build_custody_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        hero = QFrame()
        hero.setObjectName("PanelFrame")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(14, 14, 14, 14)
        hero_layout.setSpacing(8)
        title = QLabel("Chain of Custody")
        title.setObjectName("SectionLabel")
        meta = QLabel("Current case only. Previous sessions are excluded by design.")
        meta.setObjectName("SectionMetaLabel")
        hero_layout.addWidget(title)
        hero_layout.addWidget(meta)
        layout.addWidget(hero)
        audit_row = QHBoxLayout()
        audit_row.setSpacing(8)
        self.audit_search = QLineEdit()
        self.audit_search.setPlaceholderText("Filter audit trail by action, evidence ID, or keyword…")
        self.audit_search.textChanged.connect(self.populate_custody_log)
        self.btn_copy_audit = QPushButton("Copy Audit")
        self.btn_copy_audit.clicked.connect(self.copy_audit_log)
        audit_row.addWidget(self.audit_search)
        audit_row.addWidget(self.btn_copy_audit)
        self.audit_summary = AutoHeightNarrativeView("Audit summary appears here.", max_auto_height=140)
        self.custody_text = TerminalView("No chain-of-custody activity logged yet.")
        layout.addWidget(self._shell("Audit Summary", self.audit_summary, "Quick reading layer before the full event stream."))
        layout.addLayout(audit_row)
        layout.addWidget(self._shell("Current Case Log", self.custody_text, "Event stream for the active isolated case."), 1)
        return widget

    def _build_reports_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        hero = QFrame()
        hero.setObjectName("PanelFrame")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(14, 14, 14, 14)
        hero_layout.setSpacing(8)
        title = QLabel("Reports & Export Hub")
        title.setObjectName("SectionLabel")
        meta = QLabel("One dedicated page for packages, courtroom output, and generated files instead of squeezing export state into the review rail.")
        meta.setObjectName("SectionMetaLabel")
        hero_layout.addWidget(title)
        hero_layout.addWidget(meta)
        layout.addWidget(hero)

        self.export_summary = AutoHeightNarrativeView("No export package generated for the current case yet.", max_auto_height=260)
        self.report_notes_view = AutoHeightNarrativeView("Generate reports to populate courtroom-ready output notes here.", max_auto_height=220)
        self.batch_queue_view = AutoHeightNarrativeView("No active or queued import batches.", max_auto_height=240)
        self.error_log_view = TerminalView("Graceful error logs will appear here for user-visible troubleshooting.")
        layout.addWidget(self._shell("Package Status", self.export_summary, "HTML, PDF, CSV, JSON, and courtroom summary are generated here."))
        layout.addWidget(self._shell("Batch Queue & Intake Progress", self.batch_queue_view, "Drag-and-drop or import multiple sets; queued batches start automatically."))
        layout.addWidget(self._shell("Courtroom Output Notes", self.report_notes_view, "Use this page as the document hub after generation."))
        layout.addWidget(self._shell("Graceful Error Log", self.error_log_view, "User-visible runtime issues are stored here and mirrored to logs/app_errors.log."))
        layout.addStretch(1)
        return widget

    def _build_cases_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        hero = QFrame()
        hero.setObjectName("PanelFrame")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(14, 14, 14, 14)
        hero_layout.setSpacing(8)
        title = QLabel("Cases & Reopen")
        title.setObjectName("SectionLabel")
        meta = QLabel("Stronger case save/load/reopen flow with snapshots, quick switching, and a dedicated page instead of a hidden combo only.")
        meta.setObjectName("SectionMetaLabel")
        hero_layout.addWidget(title)
        hero_layout.addWidget(meta)
        layout.addWidget(hero)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.btn_cases_open = QPushButton("Open Selected Case")
        self.btn_cases_open.clicked.connect(self.open_selected_case_from_page)
        self.btn_cases_snapshot = QPushButton("Open Snapshot Folder")
        self.btn_cases_snapshot.clicked.connect(self.open_case_snapshot_folder)
        self.btn_cases_rename = QPushButton("Rename Active Case")
        self.btn_cases_rename.clicked.connect(self.rename_active_case)
        self.btn_cases_refresh = QPushButton("Refresh")
        self.btn_cases_refresh.clicked.connect(self._refresh_cases_page)
        for btn in [self.btn_cases_open, self.btn_cases_snapshot, self.btn_cases_rename, self.btn_cases_refresh]:
            action_row.addWidget(btn)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        self.cases_summary = AutoHeightNarrativeView("Case library summary will appear here.", max_auto_height=240)
        self.cases_list = QListWidget()
        self.cases_list.setObjectName("EvidenceList")
        self.cases_list.itemDoubleClicked.connect(lambda item: self.open_selected_case_from_page())
        layout.addWidget(self._shell("Case Library", self.cases_summary, "Active case identity, snapshot coverage, and recent case history."))
        layout.addWidget(self.cases_list, 1)
        return widget

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

    def _toggle_metadata_panel(self, panel: QWidget, button: QPushButton, closed_text: str, open_text: str) -> None:
        panel.setVisible(not panel.isVisible())
        button.setText(open_text if panel.isVisible() else closed_text)

    def _set_workspace_page(self, page: str) -> None:
        alias_map = {"Overview": "Review", "Insights": "Dashboard"}
        resolved = alias_map.get(page, page)
        widget = self.workspace_pages.get(resolved)
        if widget is None:
            return
        self.workspace_stack.setCurrentWidget(widget)
        self._update_page_buttons(resolved)

    def _update_page_buttons(self, active: str) -> None:
        for page, button in self.page_buttons.items():
            button.setObjectName("PageButtonActive" if page == active else "PageButton")
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def _switch_case_from_combo(self, index: int) -> None:
        if index < 0:
            return
        case_id = self.case_switch_combo.itemData(index)
        if not case_id or case_id == self.case_manager.active_case_id:
            return
        switched = self.case_manager.switch_case(case_id)
        if switched is None:
            return
        self.records = list(self.case_manager.records)
        self.filtered_records = list(self.records)
        self.export_dir = self._case_export_dir()
        self.map_service = MapService(self.export_dir)
        self.report_service = ReportService(self.export_dir)
        self.current_map_path = None
        self.thumbnail_cache.clear()
        self.preview_cache.clear()
        self.frame_cache.clear()
        self.populate_table(self.filtered_records)
        self.refresh_dashboard()
        self.update_charts()
        self.populate_timeline()
        self.populate_custody_log()
        self.clear_details()
        self._refresh_case_badges()
        self._refresh_cases_page()
        self._show_toast("Case reopened", f"Loaded {self.case_manager.active_case_name}", tone="success")

    def _refresh_case_switcher(self) -> None:
        if not hasattr(self, "case_switch_combo"):
            return
        self.case_switch_combo.blockSignals(True)
        self.case_switch_combo.clear()
        for case in self.case_manager.list_cases():
            label = f"{case.case_name} • {case.item_count} item(s)"
            self.case_switch_combo.addItem(label, case.case_id)
            if case.case_id == self.case_manager.active_case_id:
                self.case_switch_combo.setCurrentIndex(self.case_switch_combo.count() - 1)
        self.case_switch_combo.blockSignals(False)

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
        object_name = {"High": "RiskBadgeHigh", "Medium": "RiskBadgeMedium", "Low": "RiskBadgeLow"}.get(level, "RiskBadgeLow")
        label.setObjectName(object_name)
        label.style().unpolish(label)
        label.style().polish(label)
        label.update()

    def start_new_case(self) -> None:
        if self.settings.value("confirm_before_new_case", True, type=bool) and self.records:
            answer = QMessageBox.question(self, "Start New Case", "Create a new active case and clear the current review context? Existing cases remain saved.")
            if answer != QMessageBox.Yes:
                return
        name, ok = QInputDialog.getText(self, "New Case", "Case name:", text=f"Case {self.case_manager.active_case_name}")
        if not ok:
            return
        case = self.case_manager.new_case(name.strip() or None)
        self.records = []
        self.filtered_records = []
        self.thumbnail_cache.clear()
        self.preview_cache.clear()
        self.frame_cache.clear()
        self.current_frames = []
        self.current_frame_index = 0
        self.current_frame_record = None
        self.export_dir = self._case_export_dir()
        self.map_service = MapService(self.export_dir)
        self.report_service = ReportService(self.export_dir)
        self.inventory_list.clear()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Ready")
        self.command_progress.setText("New isolated case created")
        self.current_map_path = None
        self._refresh_case_badges()
        self.refresh_dashboard()
        self.clear_details()
        self.populate_custody_log()
        self.export_summary.setPlainText(f"Active case changed to {case.case_id}. Previous case logs remain isolated.")
        self._refresh_cases_page()
        self._show_toast("New case created", case.case_id, tone="success")

    def _refresh_case_badges(self) -> None:
        self.case_badge.setText(f"{self.case_manager.active_case_id} — {self.case_manager.active_case_name}")
        self._set_info_badge(self.case_label, "Case ID", self.case_manager.active_case_id)
        self._set_info_badge(self.status_label, "Status", "Awaiting evidence" if not self.records else f"{len(self.records)} evidence item(s) analyzed")

    def import_images(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Evidence Images",
            str(self.project_root),
            "Images (*.jpg *.jpeg *.png *.tif *.tiff *.webp *.bmp *.gif *.heic *.heif)",
        )
        if files:
            self._queue_or_start_analysis([Path(file) for file in files])

    def import_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Evidence Folder", str(self.project_root))
        if folder:
            self._queue_or_start_analysis([Path(folder)])

    def _start_analysis(self, paths: List[Path]) -> None:
        if self.analysis_thread is not None:
            self.show_info("Analysis Running", "Wait for the current batch to finish or cancel it before starting another one.")
            return
        self.current_batch_manifest = list(paths)
        self.thumbnail_cache.clear()
        self.preview_cache.clear()
        self.frame_cache.clear()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Queued")
        self.command_progress.setText("Launching background analysis worker…")
        self.btn_cancel_analysis.setEnabled(True)
        self.btn_load_images.setEnabled(False)
        self.btn_load_folder.setEnabled(False)
        self.btn_generate_report.setEnabled(False)
        self.btn_courtroom.setEnabled(False)
        self.btn_compare.setEnabled(False)
        self._refresh_batch_queue_view()

        self.analysis_thread = QThread(self)
        self.analysis_worker = AnalysisWorker(self.case_manager, paths)
        self.analysis_worker.moveToThread(self.analysis_thread)
        self.analysis_thread.started.connect(self.analysis_worker.run)
        self.analysis_worker.progress.connect(self._on_analysis_progress)
        self.analysis_worker.finished.connect(self._on_analysis_finished)
        self.analysis_worker.error.connect(self._on_analysis_error)
        self.analysis_worker.cancelled.connect(self._on_analysis_cancelled)
        self.analysis_worker.finished.connect(self.analysis_thread.quit)
        self.analysis_worker.error.connect(self.analysis_thread.quit)
        self.analysis_worker.cancelled.connect(self.analysis_thread.quit)
        self.analysis_thread.finished.connect(self._cleanup_analysis_thread)
        self.analysis_thread.start()

    def cancel_analysis(self) -> None:
        if self.analysis_worker is not None:
            self.analysis_worker.cancel()
            self.command_progress.setText("Cancellation requested…")

    def _on_analysis_progress(self, value: int, text: str) -> None:
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(text)
        self.command_progress.setText(text)

    def _on_analysis_finished(self, records: object) -> None:
        self.records = list(records) if isinstance(records, list) else []
        self.filtered_records = list(self.records)
        self.current_map_path = self.map_service.create_map(self.records)
        self.populate_table(self.filtered_records)
        self.refresh_dashboard()
        self.update_charts()
        self.populate_timeline()
        self.populate_custody_log()
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Analysis complete")
        self.command_progress.setText("Analysis complete")
        self.inventory_meta.setText(f"Loaded {len(self.records)} evidence item(s) into {self.case_manager.active_case_id}.")
        self._set_info_badge(self.status_label, "Status", f"{len(self.records)} evidence item(s) analyzed")
        self.btn_open_map.setEnabled(self.current_map_path is not None)
        self.btn_generate_report.setEnabled(bool(self.records))
        self.btn_courtroom.setEnabled(bool(self.records))
        self.btn_compare.setEnabled(len(self.records) >= 2)
        if self.filtered_records:
            self.inventory_list.setCurrentRow(0)
        else:
            self.clear_details()
        self._refresh_batch_queue_view()
        self._refresh_cases_page()
        self._show_toast("Analysis complete", f"Processed {len(self.records)} evidence item(s).", tone="success")

    def _on_analysis_error(self, message: str) -> None:
        self.progress_bar.setFormat("Analysis failed")
        self.command_progress.setText("Analysis failed")
        self._log_error("Analysis Error", message)
        self.show_info("Analysis Error", message)
        self._refresh_batch_queue_view()

    def _on_analysis_cancelled(self) -> None:
        self.progress_bar.setFormat("Analysis cancelled")
        self.command_progress.setText("Analysis cancelled")
        self.show_info("Cancelled", "Background analysis was cancelled before completion.")
        self._show_toast("Analysis cancelled", "The active batch was cancelled.", tone="warning")
        self._refresh_batch_queue_view()

    def _cleanup_analysis_thread(self) -> None:
        self.btn_cancel_analysis.setEnabled(False)
        self.btn_load_images.setEnabled(True)
        self.btn_load_folder.setEnabled(True)
        if self.analysis_worker is not None:
            self.analysis_worker.deleteLater()
        if self.analysis_thread is not None:
            self.analysis_thread.deleteLater()
        self.analysis_worker = None
        self.analysis_thread = None
        self.current_batch_manifest = []
        self._refresh_batch_queue_view()
        self._consume_next_batch()

    def populate_table(self, records: List[EvidenceRecord]) -> None:
        self.inventory_list.clear()
        for record in records:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, record.evidence_id)
            item.setSizeHint(QSize(0, 88))
            card = EvidenceListCard()
            card.set_content(
                self._thumbnail_for_record(record),
                f"{record.evidence_id} — {record.file_name}",
                f"{self._display_timestamp(record.timestamp)} • {record.source_type}",
                f"{record.risk_level} • Score {record.suspicion_score} • Parser {record.parser_status} • GPS {'Yes' if record.has_gps else 'No'}{' • ★' if record.bookmarked else ''}",
            )
            self.inventory_list.addItem(item)
            self.inventory_list.setItemWidget(item, card)
        self.inventory_meta.setText("No results match the current filter." if self.inventory_list.count() == 0 else f"Showing {len(records)} evidence item(s) from the active case.")

    def _thumbnail_for_record(self, record: EvidenceRecord) -> QPixmap:
        cached = self.thumbnail_cache.get(record.evidence_id)
        if cached is not None:
            return cached
        placeholder = QPixmap(56, 42)
        placeholder.fill(QColor("#0a1728"))
        pixmap = self._load_pixmap_from_record(record)
        thumb = placeholder if pixmap is None or pixmap.isNull() else pixmap.scaled(56, 42, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.thumbnail_cache[record.evidence_id] = thumb
        return thumb

    def _display_timestamp(self, timestamp: str) -> str:
        if timestamp == "Unknown":
            return timestamp
        return timestamp.replace(":", "-", 2)

    def refresh_dashboard(self) -> None:
        stats = self.case_manager.build_stats()
        high = sum(1 for record in self.case_manager.records if record.risk_level == "High")
        self.card_total.set_value(str(stats.total_images))
        self.card_total.set_subtitle("Total evidence items in the active isolated case.")
        self.card_high.set_value(str(high))
        self.card_high.set_subtitle("Items that should be reviewed first during demo and validation.")
        self.card_gps.set_value(str(stats.gps_enabled))
        self.card_gps.set_subtitle("Files with native GPS available for map correlation.")
        self.card_duplicates.set_value(str(stats.duplicates_count))
        self.card_duplicates.set_subtitle("Near-duplicate groups that can collapse redundant review.")
        self.card_timeline.set_value(stats.timeline_span)
        self.card_timeline.set_subtitle("Recovered chronological span across the active case.")
        self.card_integrity.set_value(stats.integrity_summary)
        self.card_integrity.set_subtitle("Case-level integrity and custody isolation summary.")
        self._set_info_badge(self.integrity_label, "Case Integrity", stats.integrity_summary)
        self.btn_open_map.setEnabled(stats.gps_enabled > 0 and self.current_map_path is not None)
        self.btn_generate_report.setEnabled(stats.total_images > 0 and self.analysis_thread is None)
        self.btn_courtroom.setEnabled(stats.total_images > 0 and self.analysis_thread is None)
        self.btn_compare.setEnabled(len(self.records) >= 2)
        assessment = self._build_case_assessment_text()
        priority = self._build_priority_text()
        self.export_summary.setPlainText(self.export_summary.toPlainText() if self.export_summary.toPlainText().strip() else "No export package generated for the current case yet.")
        if hasattr(self, "summary_text"):
            self.summary_text.setPlainText(assessment)
        if hasattr(self, "dashboard_priority_text"):
            self.dashboard_priority_text.setPlainText(priority)
        self.command_progress.setText("Ready" if not self.records else f"Active case: {self.case_manager.active_case_id}")
        self.inventory_meta.setText("No evidence loaded in the current case." if not self.records else self.inventory_meta.text())
        self._refresh_case_switcher()

    def _set_info_badge(self, label: QLabel, title: str, value: str) -> None:
        label.setText(f"<div><span style='color:#7da4c4;font-size:9pt;'>{title}</span><br><span style='font-weight:800;color:#f5fbff;'>{value}</span></div>")

    def _activate_filter(self, label: str) -> None:
        self.filter_combo.setCurrentText(label)
        if label == "Has GPS":
            self._set_workspace_page("Geo")
        elif label == "Duplicate Cluster":
            self._set_workspace_page("Dashboard")
        else:
            self._set_workspace_page("Review")
        self.apply_filters()

    def apply_filters(self) -> None:
        query = self.search_box.text().strip()
        mode = self.filter_combo.currentText()
        filtered: List[EvidenceRecord] = []
        tokens = [token for token in query.lower().split() if token]
        for record in self.case_manager.records:
            if not self._record_matches_query(record, tokens):
                continue
            if mode == "Has GPS" and not record.has_gps:
                continue
            if mode == "High Risk" and record.risk_level != "High":
                continue
            if mode == "Medium Risk" and record.risk_level != "Medium":
                continue
            if mode == "Low Risk" and record.risk_level != "Low":
                continue
            if mode == "Screenshots / Exports" and not ("Screenshot" in record.source_type or "Messaging" in record.source_type):
                continue
            if mode == "Camera Photos" and record.source_type != "Camera Photo":
                continue
            if mode == "Edited / Exported" and record.source_type != "Edited / Exported":
                continue
            if mode == "Duplicate Cluster" and not record.duplicate_group:
                continue
            if mode == "Parser Issues" and record.parser_status == "Valid" and record.signature_status != "Mismatch":
                continue
            if mode == "Bookmarked" and not record.bookmarked:
                continue
            filtered.append(record)

        sort_mode = self.sort_combo.currentText() if hasattr(self, "sort_combo") else "Score ↓"
        filtered = self._sort_records(filtered, sort_mode)
        self.filtered_records = filtered
        self.populate_table(filtered)
        if filtered:
            self.inventory_list.setCurrentRow(0)
        else:
            self.clear_details()

    def _record_search_haystack(self, record: EvidenceRecord) -> str:
        parts = [
            record.evidence_id, record.file_name, str(record.file_path), record.device_model, record.gps_display,
            record.timestamp, record.timestamp_source, record.software, record.source_type, record.parser_status,
            record.signature_status, record.format_trust, record.duplicate_group, record.analyst_verdict, record.tags, record.note,
            record.parse_error, record.hidden_code_summary, record.hidden_content_overview, record.format_name, record.dimensions,
            " ".join(record.anomaly_reasons), " ".join(record.osint_leads), " ".join(record.extracted_strings),
            " ".join(record.hidden_code_indicators), " ".join(record.urls_found),
        ]
        return " ".join(part for part in parts if part).lower()

    def _record_matches_query(self, record: EvidenceRecord, tokens: List[str]) -> bool:
        if not tokens:
            return True
        haystack = self._record_search_haystack(record)
        for token in tokens:
            if ':' in token:
                key, value = token.split(':', 1)
                value = value.strip()
                if key == 'gps':
                    expected = value in {'yes', 'true', '1', 'on'}
                    if record.has_gps != expected:
                        return False
                    continue
                if key == 'risk' and record.risk_level.lower() != value:
                    return False
                elif key == 'parser' and value not in record.parser_status.lower():
                    return False
                elif key == 'source' and value not in record.source_type.lower():
                    return False
                elif key == 'tag' and value not in (record.tags or '').lower():
                    return False
                elif key == 'note' and value not in (record.note or '').lower():
                    return False
                elif key in {'hidden', 'code'}:
                    expected = value in {'yes', 'true', '1', 'on'}
                    if bool(record.hidden_code_indicators) != expected:
                        return False
                    continue
                elif key == 'url':
                    expected = value in {'yes', 'true', '1', 'on'}
                    if bool(record.urls_found) != expected:
                        return False
                    continue
                elif token not in haystack:
                    return False
            elif token not in haystack:
                return False
        return True

    def _sort_records(self, records: List[EvidenceRecord], mode: str) -> List[EvidenceRecord]:
        def ts(record: EvidenceRecord):
            parsed = parse_timestamp(record.timestamp)
            return parsed or datetime.max

        if mode == "Time ↑":
            return sorted(records, key=lambda r: (ts(r), r.evidence_id))
        if mode == "Time ↓":
            return sorted(records, key=lambda r: (ts(r), r.evidence_id), reverse=True)
        if mode == "Filename A→Z":
            return sorted(records, key=lambda r: (r.file_name.lower(), r.evidence_id))
        if mode == "Filename Z→A":
            return sorted(records, key=lambda r: (r.file_name.lower(), r.evidence_id), reverse=True)
        if mode == "Confidence ↓":
            return sorted(records, key=lambda r: (-r.confidence_score, -r.suspicion_score, r.evidence_id))
        if mode == "Bookmarked First":
            return sorted(records, key=lambda r: (not r.bookmarked, -r.suspicion_score, r.evidence_id))
        return sorted(records, key=lambda r: (-r.suspicion_score, -r.confidence_score, r.evidence_id))

    def selected_records(self) -> List[EvidenceRecord]:
        selected: List[EvidenceRecord] = []
        for item in self.inventory_list.selectedItems():
            evidence_id = item.data(Qt.UserRole)
            record = self.case_manager.get_record(str(evidence_id)) if evidence_id else None
            if record is not None:
                selected.append(record)
        return selected

    def selected_record(self) -> Optional[EvidenceRecord]:
        item = self.inventory_list.currentItem()
        if item is None:
            return None
        evidence_id = item.data(Qt.UserRole)
        if not evidence_id:
            return None
        return self.case_manager.get_record(str(evidence_id))

    def clear_details(self) -> None:
        self.current_preview_pixmap = None
        self.current_frames = []
        self.current_frame_index = 0
        self.current_frame_record = None
        self.image_preview.clear_source("Select evidence to open the hero preview stage. No-selection mode keeps the workspace calm until you choose an item.")
        self.metadata_overview.setPlainText("Choose an evidence item to see a calm metadata overview instead of a raw dump wall.")
        self.hidden_overview_view.setPlainText("Hidden-content scan results will appear here.")
        self.hidden_code_view.setPlainText("Code-like markers, URLs, and embedded strings will appear here when detected.")
        self.review_audit_view.setPlainText("Select an evidence item to load its case-scoped audit activity.")
        self.metadata_view.clear()
        self.raw_exif_view.clear()
        self.normalized_shell.hide()
        self.raw_shell.hide()
        self.btn_toggle_normalized.setText("Show Normalized Dump")
        self.btn_toggle_raw.setText("Show Raw Tags")
        self.note_editor.clear()
        self.tags_editor.clear()
        self.bookmark_checkbox.setChecked(False)
        self.geo_text.setPlainText("No GPS selected yet. When an item is chosen, this page explains whether missing GPS is normal for its workflow.")
        self.geo_leads_text.setPlainText("Location pivots and next-step suggestions will appear here.")
        self.timeline_text.setPlainText("Timeline analysis will appear here after evidence is loaded.")
        if hasattr(self, "timeline_narrative"):
            self.timeline_narrative.setPlainText("Timeline narrative generation will appear here after evidence is loaded.")
        self.selection_verdict_view.setPlainText("Select an item to load a shorter, calmer verdict narrative.")
        self.review_pivots_text.setPlainText("Choose evidence to see next pivots, or stay on Dashboard for case-wide triage.")
        if hasattr(self, "review_tabs"):
            self.review_tabs.setCurrentIndex(0)
        self.preview_file_meta.value_label.setText("—")  # type: ignore[attr-defined]
        self.preview_source_meta.value_label.setText("—")  # type: ignore[attr-defined]
        self.preview_time_meta.value_label.setText("—")  # type: ignore[attr-defined]
        self.preview_geo_meta.value_label.setText("—")  # type: ignore[attr-defined]
        self.review_time_shell.value_label.setText("—")  # type: ignore[attr-defined]
        self.review_file_shell.value_label.setText("—")  # type: ignore[attr-defined]
        self.review_profile_shell.value_label.setText("—")  # type: ignore[attr-defined]
        self.score_ring.set_value(0)
        self.score_ring.set_caption("Evidence Score", "Awaiting selection")
        self.confidence_bar.setValue(0)
        self.confidence_bar_label.setText("0% analyst confidence")
        self.preview_zoom_pill.setText("Zoom 100%")
        self.frame_index_badge.setText("Frame 0/0")
        self.preview_state_badge.setText("Preview State: Awaiting selection")
        self.preview_parser_badge.setText("Parser: —")
        self.preview_signature_badge.setText("Signature: —")
        self.preview_trust_badge.setText("Trust: —")
        self._set_badge_defaults()
        self._set_geo_defaults()
        self._set_timeline_defaults()
        self._set_preview_controls(False)
        if hasattr(self, "summary_text"):
            self.summary_text.setPlainText(self._build_case_assessment_text())
        if hasattr(self, "dashboard_priority_text"):
            self.dashboard_priority_text.setPlainText(self._build_priority_text())
        self._set_workspace_page("Dashboard" if not self.records else "Review")

    def _set_preview_controls(self, enabled: bool) -> None:
        for btn in [self.btn_zoom_out, self.btn_zoom_in, self.btn_zoom_fit, self.btn_zoom_reset, self.btn_prev_frame, self.btn_next_frame, self.btn_open_external, self.btn_fullscreen_preview]:
            btn.setEnabled(enabled)
        animated = enabled and len(self.current_frames) > 1
        self.btn_prev_frame.setEnabled(animated)
        self.btn_next_frame.setEnabled(animated)

    def _set_badge_defaults(self) -> None:
        self.badge_source.setText("Source Profile: —")
        self.badge_time.setText("Time Anchor: —")
        self.badge_parser.setText("Parser / Trust: —")
        self.badge_signature.setText("Signature: —")
        self.badge_trust.setText("Trust: —")
        self.badge_gps.setText("GPS: —")
        self.badge_format.setText("Format: —")
        self.badge_risk.setText("Risk: —")
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
        self.tags_editor.setText(record.tags or "")
        self.bookmark_checkbox.setChecked(record.bookmarked)
        self._prepare_frames(record)
        if self.current_frames:
            self.current_preview_pixmap = self.current_frames[self.current_frame_index]
            self.image_preview.set_source_pixmap(self.current_preview_pixmap)
            self._set_preview_controls(True)
        else:
            fallback = self._build_parser_fallback_text(record)
            self.current_preview_pixmap = None
            self.image_preview.clear_source(fallback)
            self._set_preview_controls(False)

        self.preview_file_meta.value_label.setText(f"{record.evidence_id} — {record.file_name}")  # type: ignore[attr-defined]
        self.preview_source_meta.value_label.setText(record.source_type)  # type: ignore[attr-defined]
        self.preview_time_meta.value_label.setText(f"{record.timestamp} ({record.timestamp_source})")  # type: ignore[attr-defined]
        self.preview_geo_meta.value_label.setText(record.gps_display)  # type: ignore[attr-defined]
        self.review_time_shell.value_label.setText(f"{record.timestamp} ({record.timestamp_source})")  # type: ignore[attr-defined]
        self.review_file_shell.value_label.setText(f"{record.evidence_id} — {record.file_name}")  # type: ignore[attr-defined]
        self.review_profile_shell.value_label.setText(f"{record.source_type} • {record.risk_level} • Score {record.suspicion_score}")  # type: ignore[attr-defined]
        self.preview_state_badge.setText(f"Preview State: {record.preview_status}")
        self.preview_parser_badge.setText(f"Parser: {record.parser_status}")
        self.preview_signature_badge.setText(f"Signature: {record.signature_status} • {record.format_signature}")
        self.preview_trust_badge.setText(f"Trust: {record.format_trust}")
        self.frame_index_badge.setText(f"Frame {self.current_frame_index + 1}/{max(1, len(self.current_frames))}")
        self.badge_source.setText(f"Source Profile: {record.source_type}")
        self.badge_time.setText(f"Time Anchor: {record.timestamp_source}")
        self.badge_parser.setText(f"Parser / Trust: {record.parser_status} • {record.format_trust}")
        self.badge_signature.setText(f"Signature: {record.signature_status}")
        self.badge_trust.setText(f"Trust: {record.format_trust}")
        self.badge_gps.setText(f"GPS: {'Recovered' if record.has_gps else 'Unavailable'}")
        self.badge_risk.setText(f"Risk: {record.risk_level} / Score {record.suspicion_score}")
        self.badge_format.setText(f"Format: {record.format_name} • {record.dimensions}")
        self.confidence_bar.setValue(record.confidence_score)
        self.confidence_bar_label.setText(f"{record.confidence_score}% analyst confidence")
        self.score_auth_badge.setText(f"Authenticity {record.authenticity_score}")
        self.score_meta_badge.setText(f"Metadata {record.metadata_score}")
        self.score_tech_badge.setText(f"Technical {record.technical_score}")
        self._apply_risk_badge_style(self.badge_risk, record.risk_level)
        self.geo_badge_status.setText(f"GPS State: {'Recovered' if record.has_gps else 'Unavailable'}")
        self.geo_badge_coords.setText(f"Coordinates: {record.gps_display}")
        self.geo_badge_altitude.setText(f"Altitude: {f'{record.gps_altitude:.2f} m' if record.gps_altitude is not None else 'Unavailable'}")
        self.geo_badge_map.setText(f"Map Package: {'Ready' if self.current_map_path else 'Unavailable'}")
        self.score_ring.set_value(record.suspicion_score)
        self.score_ring.set_caption("Evidence Score", record.risk_level)
        self.preview_zoom_pill.setText(f"Zoom {self.image_preview.zoom_percent()}%")
        self.summary_text.setPlainText(self._build_case_assessment_text())
        self.dashboard_priority_text.setPlainText(self._build_priority_text())
        self.review_pivots_text.setPlainText(self._build_summary_text(record))
        self.metadata_overview.setPlainText(self._build_metadata_overview_text(record))
        self.metadata_view.setPlainText(self._build_metadata_text(record))
        self.raw_exif_view.setPlainText(self._build_raw_exif_text(record))
        self.hidden_overview_view.setPlainText(self._build_hidden_content_text(record))
        self.hidden_code_view.setPlainText(self._build_hidden_content_dump(record))
        self.review_audit_view.setPlainText(self._build_review_audit_text(record))
        self.geo_text.setPlainText(self._build_geo_text(record))
        self.geo_leads_text.setPlainText(self._build_geo_leads_text(record))
        self.selection_verdict_view.setPlainText(self._build_verdict_panel_text(record))
        self.review_pivots_text.setPlainText(self._build_summary_text(record))
        self._select_default_tab(record)
        self._highlight_selected_inventory_card()

    def _prepare_frames(self, record: EvidenceRecord) -> None:
        self.current_frame_record = record.evidence_id
        self.current_frame_index = 0
        cached = self.frame_cache.get(record.evidence_id)
        if cached is not None:
            self.current_frames = cached
            return
        frames: List[QPixmap] = []
        if record.parser_status == "Valid":
            try:
                with Image.open(record.file_path) as image:
                    if getattr(image, "is_animated", False):
                        for frame in ImageSequence.Iterator(image):
                            rgba = frame.copy().convert("RGBA")
                            data = rgba.tobytes("raw", "RGBA")
                            qimg = QImage(data, rgba.width, rgba.height, QImage.Format_RGBA8888)
                            frames.append(QPixmap.fromImage(qimg.copy()))
                            if len(frames) >= 20:
                                break
                    else:
                        pixmap = self._load_pixmap_from_record(record)
                        if pixmap is not None:
                            frames.append(pixmap)
            except Exception:
                frames = []
        if not frames:
            pixmap = self._load_pixmap_from_record(record)
            if pixmap is not None:
                frames.append(pixmap)
        self.frame_cache[record.evidence_id] = frames
        self.current_frames = frames

    def _show_previous_frame(self) -> None:
        if len(self.current_frames) <= 1:
            return
        self.current_frame_index = (self.current_frame_index - 1) % len(self.current_frames)
        self.image_preview.set_source_pixmap(self.current_frames[self.current_frame_index])
        self.frame_index_badge.setText(f"Frame {self.current_frame_index + 1}/{len(self.current_frames)}")
        self._refresh_zoom_pill()

    def _show_next_frame(self) -> None:
        if len(self.current_frames) <= 1:
            return
        self.current_frame_index = (self.current_frame_index + 1) % len(self.current_frames)
        self.image_preview.set_source_pixmap(self.current_frames[self.current_frame_index])
        self.frame_index_badge.setText(f"Frame {self.current_frame_index + 1}/{len(self.current_frames)}")
        self._refresh_zoom_pill()

    def _build_parser_fallback_text(self, record: EvidenceRecord) -> str:
        return (
            "Forensic Fallback View\n\n"
            f"Parser: {record.parser_status}\n"
            f"Signature: {record.signature_status} ({record.format_signature})\n"
            f"Trust: {record.format_trust}\n"
            f"File Size: {record.file_size:,} bytes\n"
            f"SHA-256: {record.sha256}\n"
            f"MD5: {record.md5}\n"
            f"Reason: {record.parse_error or 'Preview unavailable.'}\n\n"
            "Recommended validation workflow:\n"
            "1) Preserve hashes and original path.\n"
            "2) Confirm header signature separately from decoder output.\n"
            "3) Validate timeline anchors externally before relying on preview content."
        )

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

    def _open_preview_fullscreen(self) -> None:
        record = self.selected_record()
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Fullscreen Evidence Stage — {record.evidence_id if record else 'Preview'}")
        dialog.resize(1380, 900)
        dialog.setStyleSheet(APP_STYLESHEET)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        title = QLabel(f"{record.evidence_id if record else 'Preview'} • fullscreen review")
        title.setObjectName("SectionLabel")
        toolbar.addWidget(title)
        toolbar.addStretch(1)
        zoom_label = QLabel("Zoom 100%")
        zoom_label.setObjectName("PreviewZoomPill")
        toolbar.addWidget(zoom_label)

        viewer = ResizableImageLabel("Preview unavailable.", min_height=760)
        if self.current_preview_pixmap is not None:
            viewer.set_source_pixmap(self.current_preview_pixmap)
        else:
            viewer.clear_source(self.image_preview.text())

        def sync_zoom() -> None:
            zoom_label.setText(f"Zoom {viewer.zoom_percent()}%")

        controls = []
        for label, callback in [("−", viewer.zoom_out), ("+", viewer.zoom_in), ("Fit", viewer.fit_to_window), ("100%", viewer.reset_zoom)]:
            btn = QPushButton(label)
            btn.setObjectName("SmallGhostButton")
            btn.clicked.connect(lambda checked=False, cb=callback: (cb(), sync_zoom()))
            toolbar.addWidget(btn)
            controls.append(btn)
        close_btn = QPushButton("Close")
        close_btn.setObjectName("SmallGhostButton")
        close_btn.clicked.connect(dialog.accept)
        toolbar.addWidget(close_btn)

        hint = QLabel("Esc close • +/- zoom • F fit")
        hint.setObjectName("MutedLabel")
        layout.addLayout(toolbar)
        layout.addWidget(hint)
        layout.addWidget(viewer, 1)

        QShortcut(QKeySequence(Qt.Key_Escape), dialog, activated=dialog.reject)
        QShortcut(QKeySequence(Qt.Key_Plus), dialog, activated=lambda: (viewer.zoom_in(), sync_zoom()))
        QShortcut(QKeySequence(Qt.Key_Minus), dialog, activated=lambda: (viewer.zoom_out(), sync_zoom()))
        QShortcut(QKeySequence("F"), dialog, activated=lambda: (viewer.fit_to_window(), sync_zoom()))
        dialog.exec_()

    def open_selected_file(self) -> None:
        record = self.selected_record()
        if record is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(record.file_path)))

    def _load_pixmap_from_record(self, record: EvidenceRecord) -> Optional[QPixmap]:
        if record.evidence_id in self.preview_cache:
            return self.preview_cache[record.evidence_id]
        pixmap = QPixmap(str(record.file_path))
        if not pixmap.isNull():
            self.preview_cache[record.evidence_id] = pixmap
            return pixmap
        try:
            with Image.open(record.file_path) as image:
                frame = next(iter(ImageSequence.Iterator(image))).copy() if getattr(image, "is_animated", False) else image.copy()
                rgba = frame.convert("RGBA")
                data = rgba.tobytes("raw", "RGBA")
                qimg = QImage(data, rgba.width, rgba.height, QImage.Format_RGBA8888)
                pixmap = QPixmap.fromImage(qimg.copy())
                self.preview_cache[record.evidence_id] = pixmap
                return pixmap
        except Exception:
            self.preview_cache[record.evidence_id] = None
            return None

    def _select_default_tab(self, record: EvidenceRecord) -> None:
        if hasattr(self, "review_tabs"):
            if record.parser_status != "Valid":
                self.review_tabs.setCurrentIndex(0)
            elif record.hidden_code_indicators:
                self.review_tabs.setCurrentIndex(3)
            elif record.note:
                self.review_tabs.setCurrentIndex(4)
            else:
                self.review_tabs.setCurrentIndex(0)
        self._set_workspace_page("Review")

    def _highlight_selected_inventory_card(self) -> None:
        for index in range(self.inventory_list.count()):
            item = self.inventory_list.item(index)
            widget = self.inventory_list.itemWidget(item)
            if widget is not None:
                widget.setProperty("selected", item is self.inventory_list.currentItem())
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()

    def _build_metadata_overview_text(self, record: EvidenceRecord) -> str:
        lines = [
            f"{record.evidence_id} — {record.file_name}",
            "",
            f"Format: {record.format_name} • Signature {record.signature_status} ({record.format_signature}) • Trust {record.format_trust}",
            f"Parser: {record.parser_status} • Structure: {record.structure_status} • Preview: {record.preview_status}",
            f"Dimensions: {record.dimensions} • Frames: {record.frame_count} • Animated: {'Yes' if record.is_animated else 'No'}",
            f"Timestamp: {record.timestamp} ({record.timestamp_source})",
            f"Source profile: {record.source_type}",
            f"Device / software: {record.device_model} / {record.software}",
            f"GPS: {record.gps_display}",
            f"Hidden-content scan: {len(record.hidden_code_indicators)} code marker(s) / {len(record.extracted_strings)} string(s)",
            "",
            "Why this matters:",
            record.analyst_verdict or "No analyst verdict is available.",
        ]
        return "\n".join(lines)

    def _build_summary_text(self, record: EvidenceRecord) -> str:
        if record.parser_status != "Valid":
            return (
                f"{record.evidence_id} requires a forensic fallback workflow because the decoder did not render the file safely.\n\n"
                f"No GPS: {'Yes' if not record.has_gps else 'No'} — next pivot is {record.timestamp_source.lower()} and surrounding chat/upload context.\n\n"
                f"Primary lead: {record.anomaly_reasons[0] if record.anomaly_reasons else 'Parser review is required.'}\n\n"
                "Next steps: confirm header signature, preserve original hashes, and use an external parser before making content claims."
            )
        if record.has_gps:
            return (
                f"{record.evidence_id} carries native GPS and should move immediately into map correlation.\n\n"
                f"Recovered coordinate: {record.gps_display}. Timestamp anchor: {record.timestamp} via {record.timestamp_source}.\n\n"
                "Next steps: verify venue, route logic, and timeline continuity across nearby evidence."
            )
        if record.duplicate_group:
            return (
                f"{record.evidence_id} belongs to {record.duplicate_group}, so review should compare it against peer items before treating it as unique evidence.\n\n"
                f"No visual reuse? {'No — duplicate peer found.' if record.duplicate_group else 'Yes'}\n\n"
                "Next steps: compare timestamps, dimensions, and source workflow to distinguish original from derivative media."
            )
        return (
            f"{record.evidence_id} is a standalone item with {record.risk_level.lower()} review posture.\n\n"
            f"No GPS → explain with source profile: {record.source_type}. Timestamp anchor: {record.timestamp_source}.\n\n"
            "Next steps: validate time anchor, preserve custody notes, and compare it against surrounding case context."
        )

    def _build_metadata_text(self, record: EvidenceRecord) -> str:
        lines = [
            "[ NORMALIZED METADATA ]",
            "=" * 96,
            f"Case ID                : {record.case_id}",
            f"Evidence ID            : {record.evidence_id}",
            f"File Path              : {record.file_path}",
            f"File Size              : {record.file_size:,} bytes",
            f"Format                 : {record.format_name}",
            f"Signature Status       : {record.signature_status}",
            f"Format Signature       : {record.format_signature}",
            f"Container Trust        : {record.format_trust}",
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
            f"GPS                    : {record.gps_display}",
            f"GPS Altitude           : {f'{record.gps_altitude:.2f} m' if record.gps_altitude is not None else 'Unavailable'}",
            f"SHA-256                : {record.sha256}",
            f"MD5                    : {record.md5}",
            f"Perceptual Hash        : {record.perceptual_hash}",
            f"Duplicate Cluster      : {record.duplicate_group or 'None'}",
            f"Frames / Animation     : {record.frame_count} / {'Animated' if record.is_animated else 'Static'}",
            f"Animation Duration     : {record.animation_duration_ms if record.animation_duration_ms else 'N/A'}",
            f"Integrity              : {record.integrity_status}",
            f"Tags                   : {record.tags or 'None'}",
            f"Bookmarked             : {'Yes' if record.bookmarked else 'No'}",
            "",
            "[ SCORE BREAKDOWN ]",
            "-" * 96,
        ]
        lines.extend(record.score_breakdown or ["No score breakdown available."])
        if record.parse_error:
            lines.extend(["", "[ PARSER DIAGNOSTICS ]", "-" * 96, record.parse_error])
        return "\n".join(lines)

    def _build_raw_exif_text(self, record: EvidenceRecord) -> str:
        lines = ["[ RAW EXIF / EMBEDDED TAGS ]", "=" * 96]
        if not record.raw_exif:
            lines.append("No raw EXIF tags were recovered from the selected file.")
            return "\n".join(lines)
        for key, value in sorted(record.raw_exif.items()):
            lines.append(f"{key:<34}: {value}")
        return "\n".join(lines)

    def _build_geo_text(self, record: EvidenceRecord) -> str:
        lines = [
            "[ GEO INTELLIGENCE ]",
            "=" * 96,
            f"Evidence ID           : {record.evidence_id}",
            f"Coordinates           : {record.gps_display}",
            f"Altitude              : {f'{record.gps_altitude:.2f} m' if record.gps_altitude is not None else 'Unavailable'}",
            f"Map Package           : {'Available' if self.current_map_path else 'Not generated'}",
            f"Time Anchor           : {record.timestamp} ({record.timestamp_source})",
            f"Source Profile        : {record.source_type}",
            f"Parser / Signature    : {record.parser_status} / {record.signature_status}",
            "",
        ]
        if record.has_gps:
            lines.extend(
                [
                    "GPS is present, so map-based reconstruction should be prioritized.",
                    "Next pivots: validate venue, route plausibility, travel timing, and any nearby corroborating uploads.",
                ]
            )
        else:
            lines.extend(
                [
                    "No GPS was recovered from the file.",
                    "Why this can still be normal: screenshots, messaging exports, edited graphics, and malformed assets often lack native GPS.",
                    "Next pivots: timeline anchor, source profile, device continuity, filenames, chat context, and custody notes.",
                ]
            )
        if record.parser_status != "Valid":
            lines.extend(["", "Structure warning: decoder failed, so geolocation conclusions must rely on external evidence rather than preview content."])
        return "\n".join(lines)

    def _build_geo_leads_text(self, record: EvidenceRecord) -> str:
        if record.has_gps:
            leads = record.osint_leads[:]
        else:
            leads = record.osint_leads[:] + [
                "No GPS → explain absence using workflow profile before framing it as suspicious.",
                "Correlate timestamp anchor with uploads, messages, or witness timeline.",
            ]
        lines = ["[ NEXT PIVOTS ]", "=" * 96]
        lines.extend(f"- {lead}" for lead in leads)
        return "\n".join(lines)

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
            lines.append(f"      GPS         : {record.gps_display}")
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
                code_hint = " Embedded readable strings were recovered from the container, so the file should still be treated as content-bearing rather than image-only."
            return (
                f"Single-item case: {record.evidence_id} is the only visible anchor. "
                f"Recovered time comes from {record.timestamp_source}. "
                f"Parser state is {record.parser_status} and trust is {record.format_trust}. "
                f"Source profile is {record.source_type} and GPS is {'present' if record.has_gps else 'absent'}."
                + code_hint +
                " Use external context such as uploads, chats, witness timelines, or cloud sync history before making chronology claims."
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
        source_fill = {"Embedded EXIF": "#1ca8ff", "Filename Pattern": "#ffd166", "Filesystem Modified Time": "#f7a35c", "Filesystem Created Time": "#f7a35c", "Unavailable": "#8c6cff"}
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

    def populate_custody_log(self) -> None:
        log = self.case_manager.export_chain_of_custody()
        query = self.audit_search.text().lower().strip() if hasattr(self, "audit_search") else ""
        lines = log.splitlines() if log else []
        if query:
            lines = [line for line in lines if query in line.lower()]
        category_counts = {"CASE": 0, "IMPORT": 0, "ANALYZE": 0, "NOTE": 0, "TAG": 0, "EXPORT": 0}
        formatted = []
        for line in lines:
            action = "OTHER"
            if "| IMPORT |" in line:
                action = "IMPORT"
            elif "| ANALYZE |" in line:
                action = "ANALYZE"
            elif "| NOTE |" in line:
                action = "NOTE"
            elif "| TAG |" in line:
                action = "TAG"
            elif "| CASE_" in line or "CASE |" in line:
                action = "CASE"
            elif "| EXPORT" in line or "report" in line.lower():
                action = "EXPORT"
            if action in category_counts:
                category_counts[action] += 1
            formatted.append(f"[{action:<7}] {line}")
        summary = [
            f"Total audit events: {len(log.splitlines()) if log else 0}",
            f"Filtered events shown: {len(lines)}",
            f"Active case: {self.case_manager.active_case_id}",
            f"Badges — CASE {category_counts['CASE']} | IMPORT {category_counts['IMPORT']} | ANALYZE {category_counts['ANALYZE']} | NOTE/TAG {category_counts['NOTE'] + category_counts['TAG']} | EXPORT {category_counts['EXPORT']}",
            "Case-scoped audit trail only; previous sessions remain isolated.",
        ]
        if hasattr(self, "audit_summary"):
            self.audit_summary.setPlainText("\n".join(summary))
        body = "\n".join(formatted) if formatted else "No audit events match the current filter."
        self.custody_text.setPlainText("[ CHAIN OF CUSTODY — CURRENT CASE ONLY ]\n" + "=" * 92 + "\n" + body)

    def copy_audit_log(self) -> None:
        QApplication.clipboard().setText(self.custody_text.toPlainText())
        self._show_toast("Audit copied", "Copied the filtered audit trail to the clipboard.", tone="success")

    def insert_note_template(self) -> None:
        name = self.note_template_combo.currentText()
        if name in self.note_templates:
            existing = self.note_editor.toPlainText().strip()
            template = self.note_templates[name]
            self.note_editor.setPlainText(((existing + "\n\n" + template) if existing else template).strip())

    def open_settings(self) -> None:
        dialog = SettingsDialog(self._startup_settings(), self)
        if dialog.exec_():
            values = dialog.values()
            for key, value in values.items():
                self.settings.setValue(key, value)
            self._apply_startup_settings()
            self._show_toast("Settings saved", "Workspace preferences were updated.", tone="success")

    def open_recent_cases_dialog(self) -> None:
        dialog = RecentCasesDialog(self.case_manager.list_cases(), self)
        if dialog.exec_() and dialog.selected_case_id:
            idx = self.case_switch_combo.findData(dialog.selected_case_id)
            if idx >= 0:
                self.case_switch_combo.setCurrentIndex(idx)
                self._set_workspace_page("Cases")

    def open_selected_case_from_page(self) -> None:
        item = self.cases_list.currentItem()
        if item is None:
            return
        case_id = item.data(Qt.UserRole)
        idx = self.case_switch_combo.findData(case_id)
        if idx >= 0:
            self.case_switch_combo.setCurrentIndex(idx)

    def open_case_snapshot_folder(self) -> None:
        snapshot_path = self.case_manager.case_snapshot_path()
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(snapshot_path.parent)))

    def rename_active_case(self) -> None:
        name, ok = QInputDialog.getText(self, "Rename Active Case", "Case name:", text=self.case_manager.active_case_name)
        if not ok or not name.strip():
            return
        self.case_manager.db.rename_case(self.case_manager.active_case_id, name.strip())
        self.case_manager.active_case = self.case_manager.db.get_active_case() or self.case_manager.active_case
        self.case_manager._write_case_snapshot()
        self._refresh_case_badges()
        self._refresh_case_switcher()
        self._refresh_cases_page()
        self._show_toast("Case renamed", self.case_manager.active_case_name, tone="success")

    def open_compare_mode(self) -> None:
        selected = self.selected_records()
        left: Optional[EvidenceRecord] = None
        right: Optional[EvidenceRecord] = None
        if len(selected) >= 2:
            left, right = selected[:2]
        else:
            left = self.selected_record()
            if left is None:
                self.show_info("Compare Evidence", "Select one or two evidence items to open compare mode.")
                return
            options = [f"{r.evidence_id} — {r.file_name}" for r in self.case_manager.records if r.evidence_id != left.evidence_id]
            if not options:
                self.show_info("Compare Evidence", "At least two evidence items are required for compare mode.")
                return
            choice, ok = QInputDialog.getItem(self, "Compare With", "Choose the second evidence item:", options, 0, False)
            if not ok:
                return
            second_id = choice.split(" — ", 1)[0]
            right = self.case_manager.get_record(second_id)
        if left is None or right is None:
            return
        CompareDialog(left, right, self).exec_()

    def open_duplicate_review(self) -> None:
        dialog = DuplicateReviewDialog(self.case_manager.records, self)
        if dialog.exec_() and dialog.selected_evidence_id:
            for row in range(self.inventory_list.count()):
                item = self.inventory_list.item(row)
                if item and item.data(Qt.UserRole) == dialog.selected_evidence_id:
                    self._set_workspace_page("Review")
                    self.inventory_list.setCurrentRow(row)
                    break

    def save_note_and_tags(self) -> None:
        record = self.selected_record()
        if record is None:
            self.show_info("No Selection", "Select an evidence item before saving notes or tags.")
            return
        note = self.note_editor.toPlainText().strip()
        tags = self.tags_editor.text().strip()
        bookmarked = self.bookmark_checkbox.isChecked()
        self.case_manager.update_note(record.evidence_id, note)
        self.case_manager.update_tags(record.evidence_id, tags, bookmarked)
        record.note = note
        record.tags = tags
        record.bookmarked = bookmarked
        self.apply_filters()
        self.populate_details()
        self.populate_custody_log()
        self._refresh_cases_page()
        self._show_toast("Analyst note saved", f"Updated {record.evidence_id}.", tone="success")

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

        labels = ["GPS Enabled", "No GPS", "Clustered", "Unique"]
        values = [sum(1 for r in records if r.has_gps), sum(1 for r in records if not r.has_gps), sum(1 for r in records if r.duplicate_group), sum(1 for r in records if not r.duplicate_group)]
        self._render_adaptive_chart(self.chart_geo, labels, values, self.export_dir / "chart_geo_duplicate.png", "coverage")
        self._render_relationship_graph(records)
        self.duplicate_terminal.setPlainText(self._build_duplicate_terminal_text())

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
            lines.append("No visual reuse found in the active case. Perceptual hashing did not produce any duplicate clusters.")
            return "\n".join(lines)
        for cluster, items in sorted(clusters.items()):
            lines.append(f"{cluster} ({len(items)} file(s))")
            lines.append("-" * 96)
            lead = items[0]
            lines.append(f"Lead item: {lead.evidence_id} — {lead.file_name} — {lead.dimensions} — {lead.timestamp}")
            for peer in items[1:]:
                lines.append(
                    f"Peer: {peer.evidence_id} — {peer.file_name} | dims {peer.dimensions} | time {peer.timestamp} | parser {peer.parser_status} | signature {peer.signature_status}"
                )
            lines.append("Interpretation: compare timestamps, workflow profile, and editing/software tags to decide which item is original vs derivative.")
            lines.append("")
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

    def open_map(self) -> None:
        if self.current_map_path is None:
            self.current_map_path = self.map_service.create_map(self.case_manager.records)
        if self.current_map_path is None:
            self.show_info("No GPS Data", "No GPS-enabled images are available to plot. Smart empty state: use timeline, source profile, and device continuity instead.")
            return
        webbrowser.open(self.current_map_path.as_uri())

    def open_export_folder(self) -> None:
        self.export_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.export_dir)))

    def generate_reports(self) -> None:
        if not self.case_manager.records:
            self.show_info("No Evidence", "Import evidence before generating reports.")
            return
        if self.report_thread is not None:
            self.show_info("Export Running", "A report package is already being generated.")
            return
        custody = self.case_manager.export_chain_of_custody()
        self.command_progress.setText("Generating report package in background…")
        self.export_summary.setPlainText("Background export started…\n\nCreating HTML, PDF, CSV, JSON, and courtroom summary outputs.")
        self.report_thread = QThread(self)
        self.report_worker = ReportWorker(self.report_service, list(self.case_manager.records), self.case_manager.active_case_id, self.case_manager.active_case_name, custody)
        self.report_worker.moveToThread(self.report_thread)
        self.report_thread.started.connect(self.report_worker.run)
        self.report_worker.finished.connect(self._on_report_finished)
        self.report_worker.error.connect(self._on_report_error)
        self.report_worker.finished.connect(self.report_thread.quit)
        self.report_worker.error.connect(self.report_thread.quit)
        self.report_thread.finished.connect(self._cleanup_report_thread)
        self.report_thread.start()

    def _on_report_finished(self, payload: dict) -> None:
        self.export_badge.setText("Report Package Generated")
        self.command_progress.setText("Export package ready")
        self.export_summary.setPlainText(
            "Generated files for the active case:\n\n"
            f"HTML: {Path(payload['html']).name}\n"
            f"PDF: {Path(payload['pdf']).name}\n"
            f"CSV: {Path(payload['csv']).name}\n"
            f"JSON: {Path(payload['json']).name}\n"
            f"Courtroom: {Path(payload['courtroom']).name}\n\n"
            f"Export folder: {self.export_dir}"
        )
        self.populate_custody_log()

    def _on_report_error(self, message: str) -> None:
        self.command_progress.setText("Export failed")
        self._log_error("Export Error", message)
        self.show_info("Export Error", message)

    def _cleanup_report_thread(self) -> None:
        if self.report_worker is not None:
            self.report_worker.deleteLater()
        if self.report_thread is not None:
            self.report_thread.deleteLater()
        self.report_worker = None
        self.report_thread = None

    def _build_case_assessment_text(self) -> str:
        records = self.case_manager.records
        if not records:
            return "Load evidence to generate a case-wide assessment. Case isolation is already active, so future custody logs will stay scoped to this case only."
        total = len(records)
        gps = sum(1 for r in records if r.has_gps)
        high = sum(1 for r in records if r.risk_level == "High")
        duplicates = len({r.duplicate_group for r in records if r.duplicate_group})
        parser_issues = sum(1 for r in records if r.parser_status != "Valid" or r.signature_status == "Mismatch")
        dominant_source = max({r.source_type for r in records}, key=lambda s: sum(1 for r in records if r.source_type == s))
        return (
            f"Total evidence items: {total}\n\n"
            f"Dominant source profile: {dominant_source}\n\n"
            f"GPS-bearing media: {gps} | Duplicate clusters: {duplicates}\n\n"
            f"Priority review items: {high} high-risk | Parser/signature alerts: {parser_issues}\n\n"
            "Interpretation: the active case summary is computed only from the current isolated case, so previous sessions do not contaminate the dashboard."
        )

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
                f"   Parser: {record.parser_status} • Signature: {record.signature_status} • Trust: {record.format_trust}\n"
                f"   Why it matters: {why}"
            )
        lines.extend([
            "",
            "Recommended next steps:",
            "Validate time anchors against chats, uploads, or witness timelines.",
            "Use duplicate clusters to collapse redundant review and isolate derivative media.",
            "Prioritize decoder failures, signature mismatches, and GPS-enabled files first.",
        ])
        return "\n\n".join(lines)

    def _build_hidden_content_text(self, record: EvidenceRecord) -> str:
        lines = [
            record.hidden_content_overview,
            "",
            f"URLs recovered: {len(record.urls_found)}",
            f"Readable strings kept for review: {len(record.extracted_strings)}",
            f"Code-like indicators: {len(record.hidden_code_indicators)}",
            "",
            "Interpretation:",
        ]
        if record.hidden_code_indicators:
            lines.append("Potential script-like, credential-like, or payload-bearing content was recovered from inside the container. Treat it as a heuristic lead and verify manually before drawing exploit conclusions.")
        elif record.extracted_strings:
            lines.append("Readable strings exist inside the file, but they do not currently look like strong executable payloads. They may still help with provenance, origin tracing, or hidden-message review.")
        else:
            lines.append("No readable payload strings or code markers were recovered from the file bytes during the lightweight scan.")
        return "\n".join(lines)

    def _build_hidden_content_dump(self, record: EvidenceRecord) -> str:
        lines = ["[ EMBEDDED TEXT / CODE-LIKE MARKER SCAN ]", "=" * 96]
        if record.urls_found:
            lines.append("URLs / external references:")
            lines.extend(f"- {url}" for url in record.urls_found)
            lines.append("")
        if record.hidden_code_indicators:
            lines.append("Code-like indicators:")
            lines.extend(f"- {item}" for item in record.hidden_code_indicators)
            lines.append("")
        if record.extracted_strings:
            lines.append("Readable embedded strings:")
            lines.extend(f"- {item}" for item in record.extracted_strings)
        else:
            lines.append("No readable strings recovered.")
        if len(lines) <= 2:
            lines.append("No embedded text markers recovered.")
        return "\n".join(lines)

    def _build_review_audit_text(self, record: EvidenceRecord) -> str:
        logs = self.case_manager.db.fetch_logs(self.case_manager.active_case_id)
        lines = ["[ REVIEW-SCOPED AUDIT ]", "=" * 96]
        selected = []
        for row in logs:
            if row["evidence_id"] in {None, record.evidence_id}:
                label = f"[{row['action']}]"
                selected.append(f"{row['action_time']} {label:<18} {row['evidence_id'] or 'CASE':<10} {row['details']}")
        lines.extend(selected[:40] if selected else ["No case events found for the selected evidence item."])
        return "\n".join(lines)

    def _build_verdict_panel_text(self, record: EvidenceRecord) -> str:
        lines = [
            f"Record: {record.evidence_id}",
            f"Likely profile: {record.source_type}",
            f"Overall posture: {record.risk_level}",
            f"Confidence: {record.confidence_score}%",
            f"Timestamp anchor: {record.timestamp_source}",
            f"Parser health: {record.parser_status}",
            f"Signature status: {record.signature_status} ({record.format_signature})",
            f"Container trust: {record.format_trust}",
            f"Location signal: {'Present' if record.has_gps else 'Missing'}",
            f"Duplicate relation: {record.duplicate_group or 'None'}",
            f"Hidden-content markers: {len(record.hidden_code_indicators)} code / {len(record.extracted_strings)} string",
            "",
            "Detailed narrative:",
            record.analyst_verdict or "No analyst verdict is available.",
        ]
        return "\n".join(lines)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        mime = event.mimeData()
        if mime.hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        mime = event.mimeData()
        if not mime.hasUrls():
            event.ignore()
            return
        paths = []
        for url in mime.urls():
            local = url.toLocalFile()
            if local:
                paths.append(Path(local))
        if paths:
            self._queue_or_start_analysis(paths)
            self._show_toast("Evidence dropped", f"Queued {len(paths)} dropped path(s).", tone="success")
            event.acceptProposedAction()
        else:
            event.ignore()

    def show_info(self, title: str, message: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QMessageBox.Ok)
        box.exec_()
