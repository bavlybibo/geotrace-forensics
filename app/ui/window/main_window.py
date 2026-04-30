"""Main application window implementation.

Moved from app.ui.main_window during v12.10.2 organization-only refactor.
"""

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

from PyQt5.QtCore import QSettings, QSize, Qt, QThread, QTimer, QUrl
from PyQt5.QtGui import QColor, QDesktopServices, QIcon, QKeySequence, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
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
    QToolButton,
    QVBoxLayout,
    QWidget,
    QMenu,
)


try:
    from ...core.anomalies import parse_timestamp
    from ...core.case_manager import CaseManager
    from ...core.map_service import MapService
    from ...core.models import EvidenceRecord
    from ...core.report_service import ReportService
    from ...core.launch_readiness import evaluate_launch_readiness, render_launch_gate_text
    from ...core.structured_logging import log_failure
    from ...config import APP_NAME, APP_ORGANIZATION, APP_VERSION, APP_BUILD_CHANNEL, DEFAULT_ANALYST_NAME
    from ...agents import RuleBasedForensicAgent
except ImportError:  # pragma: no cover - fallback for direct script execution
    from app.core.anomalies import parse_timestamp
    from app.core.case_manager import CaseManager
    from app.core.map_service import MapService
    from app.core.models import EvidenceRecord
    from app.core.report_service import ReportService
    from app.core.launch_readiness import evaluate_launch_readiness, render_launch_gate_text
    from app.core.structured_logging import log_failure
    from app.config import APP_NAME, APP_ORGANIZATION, APP_VERSION, APP_BUILD_CHANNEL, DEFAULT_ANALYST_NAME
    from app.agents import RuleBasedForensicAgent
from ..styles import APP_STYLESHEET
from ..dialogs import CompareDialog, DuplicateReviewDialog, FirstRunSetupWizardDialog, OCRSetupWizardDialog, OnboardingDialog, RecentCasesDialog, SettingsDialog, ToastPopup
from ..widgets import AutoHeightNarrativeView, CaseListCard, ChartCard, CustodyTimelineWidget, EvidenceListCard, ResizableImageLabel, ScoreRing, SmoothScrollArea, StatCard, TerminalView
from ..workers import AnalysisWorker, ReportWorker
from ..pages.ai_guardian_page import build_ai_guardian_page, refresh_ai_guardian_page
from ..pages.osint_workbench_page import build_osint_workbench_page, refresh_osint_workbench_page
from ..pages.ctf_geolocator_page import build_ctf_geolocator_page, refresh_ctf_geolocator_page
from ..pages.map_workspace_page import build_map_workspace_page, refresh_map_workspace_page
from ..pages.system_health_page import build_system_health_page, refresh_system_health_page, run_dependency_check_ui
from ..controllers.navigation import PAGE_KEYS, build_workspace_pages
from ..mixins.record_text_builder import RecordTextBuilderMixin
from ..mixins.chart_rendering import ChartRenderingMixin
from ..mixins.preview_interaction import PreviewInteractionMixin
from ..mixins.report_actions import ReportActionsMixin
from ..mixins.review_selection import ReviewSelectionMixin
from ..mixins.review_page_builders import ReviewPageBuilderMixin
from ..mixins.analysis_actions import AnalysisActionsMixin
from ..mixins.case_actions import CaseActionsMixin
from ..mixins.filtering import FilteringMixin
from ..mixins.timeline_page import TimelinePageMixin
from ..mixins.geo_page import GeoPageMixin



class GeoTraceMainWindow(RecordTextBuilderMixin, ChartRenderingMixin, PreviewInteractionMixin, ReportActionsMixin, ReviewSelectionMixin, ReviewPageBuilderMixin, AnalysisActionsMixin, CaseActionsMixin, FilteringMixin, TimelinePageMixin, GeoPageMixin, QMainWindow):
    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.project_root = project_root
        self.settings = QSettings(APP_ORGANIZATION, APP_NAME)
        self.current_workspace_mode = str(self.settings.value("workspace_mode", "Analyst"))
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
        self.agent = RuleBasedForensicAgent()
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
        self.populate_table(self.filtered_records)
        self.refresh_dashboard()
        self.refresh_ai_guardian()
        self.refresh_system_health()
        self.update_charts()
        self.populate_timeline()
        self.populate_custody_log()
        self._refresh_batch_queue_view()
        self._refresh_cases_page()
        if self.filtered_records:
            self._auto_select_visible_record()
        else:
            self.clear_details(reason=self._inventory_status_message([]))
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
            "workspace_mode": self.settings.value("workspace_mode", "Analyst"),
            "auto_reopen_last_case": self.settings.value("auto_reopen_last_case", True, type=bool),
            "open_reports_after_export": self.settings.value("open_reports_after_export", True, type=bool),
            "show_toasts": self.settings.value("show_toasts", True, type=bool),
            "confirm_before_new_case": self.settings.value("confirm_before_new_case", True, type=bool),
            "show_onboarding": self.settings.value("show_onboarding", True, type=bool),
            "first_run_setup_completed": self.settings.value("first_run_setup_completed", False, type=bool),
            "ocr_mode": self.settings.value("ocr_mode", os.getenv("GEOTRACE_OCR_MODE", "quick")),
            "ocr_timeout": self.settings.value("ocr_timeout", os.getenv("GEOTRACE_OCR_TIMEOUT", "0.8")),
            "ocr_global_timeout": self.settings.value("ocr_global_timeout", os.getenv("GEOTRACE_OCR_GLOBAL_TIMEOUT", "5.0")),
            "ocr_max_calls": self.settings.value("ocr_max_calls", os.getenv("GEOTRACE_OCR_MAX_CALLS", "4")),
            "log_privacy": self.settings.value("log_privacy", os.getenv("GEOTRACE_LOG_PRIVACY", "redacted")),
            "local_ai_enabled": self.settings.value("local_ai_enabled", False, type=bool),
        }

    def _apply_startup_settings(self) -> None:
        values = self._startup_settings()
        self.analyst_name = str(values["analyst_name"])
        os.environ["GEOTRACE_OCR_MODE"] = str(values.get("ocr_mode", "quick"))
        os.environ["GEOTRACE_OCR_TIMEOUT"] = str(values.get("ocr_timeout", "0.8"))
        os.environ["GEOTRACE_OCR_GLOBAL_TIMEOUT"] = str(values.get("ocr_global_timeout", "5.0"))
        os.environ["GEOTRACE_OCR_MAX_CALLS"] = str(values.get("ocr_max_calls", "4"))
        os.environ["GEOTRACE_LOG_PRIVACY"] = str(values.get("log_privacy", "redacted"))
        os.environ["GEOTRACE_LOCAL_AI_ENABLED"] = "1" if bool(values.get("local_ai_enabled", False)) else "0"
        if hasattr(self, "sort_combo"):
            self.sort_combo.setCurrentText(str(values["default_sort"]))
        if hasattr(self, "workspace_mode_combo"):
            self.workspace_mode_combo.setCurrentText(str(values.get("workspace_mode", "Analyst")))
        self._apply_workspace_mode()
        self._set_workspace_page(str(values["default_page"]))

    def _show_onboarding_if_needed(self) -> None:
        if not self.settings.value("first_run_setup_completed", False, type=bool):
            self.open_first_run_setup_wizard()
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
            "Ctrl+4": lambda: self._set_workspace_page("Map Workspace"),
            "Ctrl+5": lambda: self._set_workspace_page("Timeline"),
            "Ctrl+6": lambda: self._set_workspace_page("Custody"),
            "Ctrl+7": lambda: self._set_workspace_page("Reports"),
            "Ctrl+8": lambda: self._set_workspace_page("Cases"),
            "Ctrl+9": lambda: self._set_workspace_page("AI Guardian"),
            "Ctrl+0": lambda: self._set_workspace_page("OSINT Workbench"),
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
        try:
            from ...core.structured_logging import log_failure
            log_failure(self.logger, context=context, operation=context, message=message, log_dir=self.project_root / "logs")
        except Exception:
            self.logger.error(self.last_error_message)
        if hasattr(self, "error_log_view"):
            existing = self.error_log_view.toPlainText().strip()
            combined = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {self.last_error_message}"
            self.error_log_view.setPlainText(((combined + "\n\n" + existing) if existing else combined).strip())
        self._show_toast("Error logged", context, tone="error")

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
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(4)
        title = QLabel("GeoTrace Forensics X")
        title.setObjectName("TitleLabel")
        subtitle = QLabel("Forensic image triage for metadata, GPS, timeline, and custody.")
        subtitle.setObjectName("SubtitleLabel")
        subtitle.setWordWrap(True)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        self.case_badge = QLabel()
        self.case_badge.setObjectName("BadgeLabel")
        self.mode_badge = QLabel("Analyst mode")
        self.mode_badge.setObjectName("BadgeLabel")
        self.export_badge = QLabel("Import → Decide → Export")
        self.export_badge.setObjectName("BadgeLabel")
        for badge in [self.case_badge, self.mode_badge, self.export_badge]:
            badge_row.addWidget(badge)
        badge_row.addStretch(1)

        left.addWidget(title)
        left.addWidget(subtitle)
        left.addLayout(badge_row)

        right = QGridLayout()
        right.setHorizontalSpacing(10)
        right.setVerticalSpacing(8)
        self.case_label = self._info_badge("Case ID", "—")
        self.status_label = self._info_badge("Status", "Awaiting evidence")
        self.integrity_label = self._info_badge("Integrity", "0/0 Verified")
        self.method_label = self._info_badge("Workflow", "Case-based")
        right.addWidget(self.case_label, 0, 0)
        right.addWidget(self.status_label, 0, 1)
        right.addWidget(self.integrity_label, 1, 0)
        right.addWidget(self.method_label, 1, 1)

        layout.addLayout(left, 7)
        layout.addLayout(right, 5)
        return frame

    def _build_command_bar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("CommandBarFrame")
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
        self.btn_load_images.setObjectName("ActionFilesButton")
        self.btn_load_images.clicked.connect(self.import_images)
        self.btn_load_images.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))

        self.btn_load_folder = QPushButton("Folder")
        self.btn_load_folder.setObjectName("ActionFolderButton")
        self.btn_load_folder.clicked.connect(self.import_folder)
        self.btn_load_folder.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))

        self.btn_cancel_analysis = QPushButton("Cancel")
        self.btn_cancel_analysis.clicked.connect(self.cancel_analysis)
        self.btn_cancel_analysis.setEnabled(False)

        self.btn_generate_report = QPushButton("Report")
        self.btn_generate_report.setObjectName("ActionReportButton")
        self.btn_generate_report.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.btn_generate_report.clicked.connect(self.generate_reports)
        self.btn_generate_report.setEnabled(False)

        self.btn_open_map = QPushButton("Map")
        self.btn_open_map.setObjectName("ActionMapButton")
        self.btn_open_map.setIcon(self.style().standardIcon(QStyle.SP_DriveNetIcon))
        self.btn_open_map.clicked.connect(self.open_map)
        self.btn_open_map.setEnabled(False)

        self.btn_compare = QPushButton("Compare")
        self.btn_compare.setObjectName("ActionCompareButton")
        self.btn_compare.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
        self.btn_compare.clicked.connect(self.open_compare_mode)
        self.btn_compare.setEnabled(False)

        self.btn_open_exports = QPushButton("Exports")
        self.btn_open_exports.clicked.connect(lambda: self._set_workspace_page("Reports"))
        self.btn_open_exports.setObjectName("GhostButton")

        self.btn_courtroom = QPushButton("Courtroom")
        self.btn_courtroom.clicked.connect(self.generate_reports)
        self.btn_courtroom.setEnabled(False)

        self.btn_recent_cases = QPushButton("Recent Cases")
        self.btn_recent_cases.clicked.connect(self.open_recent_cases_dialog)

        self.btn_settings = QPushButton("Preferences")
        self.btn_settings.clicked.connect(self.open_settings)

        self.more_actions_button = QToolButton()
        self.more_actions_button.setText("More")
        self.more_actions_button.setObjectName("ActionMoreButton")
        self.more_actions_button.setIcon(self.style().standardIcon(QStyle.SP_TitleBarUnshadeButton))
        self.more_actions_button.setPopupMode(QToolButton.InstantPopup)
        more_menu = QMenu(self.more_actions_button)
        more_menu.addAction("Open Exports", lambda: self._set_workspace_page("Reports"))
        more_menu.addAction("Courtroom Summary", self.generate_reports)
        more_menu.addAction("Recent Cases", self.open_recent_cases_dialog)
        more_menu.addAction("Preferences", self.open_settings)
        more_menu.addAction("System Health", lambda: self._set_workspace_page("System Health"))
        more_menu.addAction("Dependency Check", self.run_dependency_check_ui)
        more_menu.addAction("First Run Setup Wizard", self.open_first_run_setup_wizard)
        more_menu.addAction("OCR Setup Wizard", self.open_ocr_setup_wizard)
        self.more_actions_button.setMenu(more_menu)

        self.command_progress = QLabel("Ready")
        self.command_progress.setObjectName("PreviewStateBadge")

        self.case_switch_combo = QComboBox()
        self.case_switch_combo.setMinimumWidth(320)
        self.case_switch_combo.currentIndexChanged.connect(self._switch_case_from_combo)

        for btn in [
            self.btn_new_case,
            self.btn_load_images,
            self.btn_load_folder,
            self.btn_generate_report,
            self.btn_open_map,
            self.btn_compare,
            self.more_actions_button,
        ]:
            row_top.addWidget(btn)
        row_top.addStretch(1)
        row_top.addWidget(self.btn_cancel_analysis)

        switch_label = QLabel("Active case")
        switch_label.setObjectName("MutedLabel")
        self.command_hint = QLabel("Import, review, then export.")
        self.command_hint.setObjectName("MutedLabel")
        row_bottom.addWidget(switch_label)
        row_bottom.addWidget(self.case_switch_combo, 1)
        row_bottom.addWidget(self.command_hint)
        row_bottom.addStretch(1)
        row_bottom.addWidget(self.command_progress)

        outer.addLayout(row_top)
        outer.addLayout(row_bottom)
        return frame

    def _build_page_bar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("PageNavFrame")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        mode_label = QLabel("Mode")
        mode_label.setObjectName("MutedLabel")
        self.workspace_mode_combo = QComboBox()
        self.workspace_mode_combo.addItems(["Executive", "Analyst", "Technical"])
        self.workspace_mode_combo.setCurrentText(str(getattr(self, "current_workspace_mode", "Analyst")))
        self.workspace_mode_combo.setMinimumWidth(130)
        self.workspace_mode_combo.currentTextChanged.connect(self._set_workspace_mode)
        layout.addWidget(mode_label)
        layout.addWidget(self.workspace_mode_combo)
        self.page_buttons = {}
        for key in PAGE_KEYS:
            btn = QPushButton(key)
            btn.setObjectName("PageButton")
            btn.clicked.connect(lambda checked=False, page=key: self._set_workspace_page(page))
            layout.addWidget(btn)
            self.page_buttons[key] = btn
        layout.addStretch(1)
        hint = QLabel(f"{APP_NAME} {APP_VERSION} • active workspace")
        hint.setObjectName("MutedLabel")
        layout.addWidget(hint)
        return frame

    def _info_badge(self, title: str, value: str) -> QLabel:
        label = QLabel(f"<div><span style='color:#86a8c2;font-size:8.8pt;'>{title}</span><br><span style='font-weight:800;color:#f5fbff;'>{value}</span></div>")
        label.setObjectName("InfoBadge")
        label.setTextFormat(Qt.RichText)
        return label

    def _build_metric_pill(self, label_text: str, value_text: str = "—", note_text: str = "", *, value_attr: str = "", note_attr: str = "") -> QFrame:
        frame = QFrame()
        frame.setObjectName("MetricPill")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(3)
        label = QLabel(label_text)
        label.setObjectName("MetricPillLabel")
        value = QLabel(value_text)
        value.setObjectName("MetricPillValue")
        note = QLabel(note_text)
        note.setObjectName("MetricPillNote")
        note.setWordWrap(True)
        layout.addWidget(label)
        layout.addWidget(value)
        layout.addWidget(note)
        if value_attr:
            setattr(self, value_attr, value)
        if note_attr:
            setattr(self, note_attr, note)
        return frame

    def _build_system_health_page(self) -> QWidget:
        return build_system_health_page(self)

    def refresh_system_health(self) -> None:
        try:
            refresh_system_health_page(self)
        except Exception as exc:
            self.logger.exception("System Health refresh failed")
            if hasattr(self, "system_health_sections_view"):
                self.system_health_sections_view.setPlainText(f"System Health refresh failed: {exc}")

    def run_dependency_check_ui(self) -> None:
        try:
            run_dependency_check_ui(self)
            self._show_toast("Dependency check complete", "System Health dependency output refreshed.")
        except Exception as exc:
            self.logger.exception("Dependency check failed")
            QMessageBox.warning(self, "Dependency Check", f"Dependency check failed: {exc}")

    def open_first_run_setup_wizard(self) -> None:
        dialog = FirstRunSetupWizardDialog(self.project_root, self._startup_settings(), self)
        if dialog.exec_():
            values = dialog.values()
            for key, value in values.items():
                self.settings.setValue(key, value)
            self.settings.setValue("first_run_setup_completed", True)
            self._apply_startup_settings()
            self.refresh_system_health()
            self._show_toast("First run setup saved", "Runtime folders and safe defaults are ready.")

    def _build_content_pages(self) -> QWidget:
        self.workspace_stack = QStackedWidget()
        self.workspace_pages = build_workspace_pages(self)
        for key in PAGE_KEYS:
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

        hero = QFrame()
        hero.setObjectName("HeroPanel")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(16, 14, 16, 14)
        hero_layout.setSpacing(10)
        title = QLabel("Case Command Center")
        title.setObjectName("SectionLabel")
        meta = QLabel(
            "Clean case view: inventory, risk, geo coverage, timeline integrity, and export readiness without repeated narrative blocks."
        )
        meta.setObjectName("SectionMetaLabel")
        meta.setWordWrap(True)
        hero_layout.addWidget(title)
        hero_layout.addWidget(meta)
        mission_row = QHBoxLayout()
        mission_row.setSpacing(10)
        mission_row.addWidget(self._build_metric_pill("Workflow", "Import → Analyze → Export", "Case-isolated pipeline."))
        mission_row.addWidget(self._build_metric_pill("AI Layer", "Explainable", "Risk, contradictions, hidden content."))
        mission_row.addWidget(self._build_metric_pill("Evidence Policy", "Local-first", "No remote lookup by default."))
        mission_row.addWidget(self._build_metric_pill("Readiness", "Clean", "Designed empty states."))
        hero_layout.addLayout(mission_row)
        layout.addWidget(hero)

        layout.addWidget(self._build_stat_cards())

        evidence_studio = QSplitter(Qt.Horizontal)
        evidence_studio.setChildrenCollapsible(False)
        self.dashboard_evidence_preview = ResizableImageLabel(
            "Evidence Viewer: import/select evidence to preview image and crop context.",
            min_height=300,
        )
        self.dashboard_evidence_preview.setMinimumHeight(320)

        studio_actions = QWidget()
        studio_actions_layout = QVBoxLayout(studio_actions)
        studio_actions_layout.setContentsMargins(0, 0, 0, 0)
        studio_actions_layout.setSpacing(8)
        self.dashboard_action_center = AutoHeightNarrativeView(
            "Action Center: key blockers and next actions appear after selection.",
            max_auto_height=210,
        )
        self.dashboard_claim_links_view = AutoHeightNarrativeView(
            "Claim-to-evidence links appear after analysis.",
            max_auto_height=210,
        )
        studio_actions_layout.addWidget(self.dashboard_action_center)
        studio_actions_layout.addWidget(self.dashboard_claim_links_view)
        evidence_studio.addWidget(self._shell(
            "Evidence Viewer",
            self.dashboard_evidence_preview,
            "Proof stays visible beside case decisions.",
        ))
        evidence_studio.addWidget(self._shell(
            "Action Center + Claim Links",
            studio_actions,
            "Claims map to source, confidence, and next action.",
        ))
        evidence_studio.setSizes([740, 680])
        layout.addWidget(evidence_studio)

        top_split = QSplitter(Qt.Horizontal)
        top_split.setChildrenCollapsible(False)
        top_split.addWidget(self._shell(
            "Case Snapshot",
            self._build_dashboard_summary_body(),
            "Fast case orientation without raw dumps.",
        ))
        charts = QWidget()
        charts_layout = QGridLayout(charts)
        charts_layout.setContentsMargins(0, 0, 0, 0)
        charts_layout.setHorizontalSpacing(12)
        charts_layout.setVerticalSpacing(12)
        self.chart_sources = ChartCard("Source Profile Mix", "Adaptive overview for source families, screenshots, edited files, and imports.")
        self.chart_risks = ChartCard("Risk Mix", "High/medium/low distribution without crowding the review screen.")
        self.chart_geo = ChartCard("Geo Anchor & Duplicate Coverage", "Native GPS, derived map anchors, duplicate clusters, and route/map indicators.")
        self.chart_relationships = ChartCard("Relationship Graph", "Links appear only when meaningful evidence relationships exist.")
        charts_layout.addWidget(self.chart_sources, 0, 0)
        charts_layout.addWidget(self.chart_risks, 0, 1)
        charts_layout.addWidget(self.chart_geo, 1, 0)
        charts_layout.addWidget(self.chart_relationships, 1, 1)
        charts_layout.setColumnStretch(0, 1)
        charts_layout.setColumnStretch(1, 1)
        top_split.addWidget(charts)
        top_split.setSizes([470, 930])

        self.duplicate_terminal = AutoHeightNarrativeView("Visual diff, duplicate reuse, and case reuse notes will appear here.", max_auto_height=210)
        layout.addWidget(top_split, 1)
        layout.addWidget(self._shell(
            "Visual Diff & Reuse Review",
            self.duplicate_terminal,
            "Duplicate/reuse notes stay compact.",
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
        self.card_gps = StatCard("Geo Anchors", chip="GPS/Map")
        self.card_duplicates = StatCard("Duplicates", chip="Correlation")
        self.card_timeline = StatCard("Timeline", chip="Span")
        self.card_integrity = StatCard("Integrity", chip="Custody")

        cards = [self.card_total, self.card_high, self.card_gps, self.card_duplicates, self.card_timeline, self.card_integrity]
        for idx, card in enumerate(cards):
            layout.addWidget(card, 0, idx)
            layout.setColumnStretch(idx, 1)

        self.card_total.clicked.connect(lambda: self._activate_filter("All Evidence"))
        self.card_high.clicked.connect(lambda: self._activate_filter("High Risk"))
        self.card_gps.clicked.connect(lambda: self._activate_filter("Has Geo Anchor"))
        self.card_duplicates.clicked.connect(lambda: self._activate_filter("Duplicate Cluster"))
        self.card_timeline.clicked.connect(lambda: self._set_workspace_page("Timeline"))
        self.card_integrity.clicked.connect(lambda: self._set_workspace_page("Custody"))
        return frame

    def _build_metadata_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        meta_intro = QLabel("Technical depth lives here. Raw dumps stay collapsed by default so Review remains clean; open only when needed.")
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
        self.metadata_view.setMinimumHeight(230)
        self.raw_exif_view.setMinimumHeight(200)
        self.normalized_shell = self._shell("Normalized Metadata Dump", self.metadata_view, "Structured normalized values for technical review.")
        self.raw_shell = self._shell("Raw EXIF vs Embedded Tags", self.raw_exif_view, "Deep tag-level comparison only when you explicitly need it.")
        self.normalized_shell.hide()
        self.raw_shell.hide()
        self.btn_toggle_normalized.setText("Show Normalized Dump")
        self.btn_toggle_raw.setText("Show Raw Tags")
        self.metadata_splitter = QSplitter(Qt.Vertical)
        self.metadata_splitter.setChildrenCollapsible(False)
        self.metadata_splitter.addWidget(self.normalized_shell)
        self.metadata_splitter.addWidget(self.raw_shell)
        self.metadata_splitter.setStretchFactor(0, 1)
        self.metadata_splitter.setStretchFactor(1, 1)
        self.metadata_splitter.setSizes([360, 260])
        layout.addWidget(self.metadata_splitter, 1)
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


    def _make_guardian_view(self, text: str, height: int = 200) -> AutoHeightNarrativeView:
        return AutoHeightNarrativeView(text, max_auto_height=height)

    def _build_ai_guardian_page(self) -> QWidget:
        return build_ai_guardian_page(self)

    def _build_osint_workbench_page(self) -> QWidget:
        return build_osint_workbench_page(self)

    def _build_ctf_geolocator_page(self) -> QWidget:
        return build_ctf_geolocator_page(self)

    def _build_map_workspace_page(self) -> QWidget:
        return build_map_workspace_page(self)

    def refresh_map_workspace(self) -> None:
        refresh_map_workspace_page(self)

    def refresh_ai_guardian(self) -> None:
        refresh_ai_guardian_page(self)
        if hasattr(self, "osint_hypothesis_view"):
            refresh_osint_workbench_page(self)
        if hasattr(self, "ctf_clue_cards_view"):
            refresh_ctf_geolocator_page(self)
        if hasattr(self, "map_workspace_summary_view"):
            refresh_map_workspace_page(self)

    def _build_reports_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        hero = QFrame()
        hero.setObjectName("HeroPanel")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(16, 14, 16, 14)
        hero_layout.setSpacing(10)
        title = QLabel("Reports & Export Command Center")
        title.setObjectName("SectionLabel")
        meta = QLabel(
            "Export hub for generated artifacts, verification, privacy posture, courtroom notes, and troubleshooting grouped by value."
        )
        meta.setObjectName("SectionMetaLabel")
        meta.setWordWrap(True)
        hero_layout.addWidget(title)
        hero_layout.addWidget(meta)
        report_metrics = QHBoxLayout()
        report_metrics.setSpacing(10)
        report_metrics.addWidget(self._build_metric_pill("Package", "Pending", "Generate reports to populate the package.", value_attr="reports_metric_package_value", note_attr="reports_metric_package_note"))
        report_metrics.addWidget(self._build_metric_pill("Privacy Gate", "Safe default", "Shareable Redacted is selected by default.", value_attr="reports_metric_privacy_value", note_attr="reports_metric_privacy_note"))
        report_metrics.addWidget(self._build_metric_pill("Verification", "Hash-first", "Manifest and signature sidecars supported.", value_attr="reports_metric_verify_value", note_attr="reports_metric_verify_note"))
        report_metrics.addWidget(self._build_metric_pill("CTF Readiness", "Awaiting", "Answer readiness appears after analysis.", value_attr="reports_metric_ctf_value", note_attr="reports_metric_ctf_note"))
        hero_layout.addLayout(report_metrics)
        report_action_row = QHBoxLayout()
        report_action_row.setSpacing(8)
        self.btn_verify_export = QPushButton("Verify Last Package")
        self.btn_verify_export.clicked.connect(self.verify_last_export_package)
        self.btn_quick_generate_reports = QPushButton("Generate Export Package")
        self.btn_quick_generate_reports.setObjectName("PrimaryButton")
        self.btn_quick_generate_reports.clicked.connect(self.generate_reports)
        self.btn_preview_export = QPushButton("Preview Export")
        self.btn_preview_export.clicked.connect(self.preview_report_package)
        self.btn_ocr_setup_wizard = QPushButton("OCR Setup Wizard")
        self.btn_ocr_setup_wizard.clicked.connect(self.open_ocr_setup_wizard)
        report_action_row.addWidget(self.btn_quick_generate_reports)
        report_action_row.addWidget(self.btn_preview_export)
        report_action_row.addWidget(self.btn_verify_export)
        report_action_row.addWidget(self.btn_ocr_setup_wizard)
        report_action_row.addStretch(1)
        hero_layout.addLayout(report_action_row)
        layout.addWidget(hero)

        self.export_summary = AutoHeightNarrativeView("No export package generated for the current case yet.", max_auto_height=170)
        self.report_preview_view = AutoHeightNarrativeView("Click Preview Export before generating a package to see blockers, warnings, privacy mode, and expected artifacts.", max_auto_height=190)
        self.report_notes_view = AutoHeightNarrativeView("Generate reports to populate courtroom-ready output notes here.", max_auto_height=160)
        self.batch_queue_view = AutoHeightNarrativeView("No active or queued import batches.", max_auto_height=140)
        self.error_log_view = TerminalView("Graceful error logs will appear here for user-visible troubleshooting.")
        self.error_log_view.setMinimumHeight(150)
        artifacts_frame = QFrame()
        artifacts_frame.setObjectName("CompactPanel")
        artifacts_layout = QGridLayout(artifacts_frame)
        artifacts_layout.setContentsMargins(10, 10, 10, 10)
        artifacts_layout.setHorizontalSpacing(12)
        artifacts_layout.setVerticalSpacing(12)
        self.report_artifact_labels = {}
        self.report_artifact_buttons = {}
        for idx, (key, title_text, hint_text) in enumerate([
            ("html", "HTML Report", "Interactive technical reading"),
            ("pdf", "PDF Package", "Shareable polished export"),
            ("csv", "CSV Summary", "Privacy-aware evidence table"),
            ("json", "JSON Evidence", "Machine-readable case export"),
            ("manifest", "Manifest", "Hashes for reports and assets"),
            ("manifest_signature", "Manifest Signature", "SHA-256 sidecar"),
            ("courtroom", "Courtroom Notes", "Legal-facing readout"),
            ("validation", "Validation Summary", "Workflow sanity"),
            ("validation_template", "Validation Template", "Ground-truth JSON skeleton"),
            ("executive", "Executive Summary", "Manager-friendly overview"),
            ("ai_guardian", "AI Guardian", "Readiness and graph"),
            ("osint_appendix", "OSINT Appendix", "Hypotheses and entities"),
            ("ctf_writeup", "OSINT/CTF Writeup", "Answer support"),
            ("claim_matrix", "Claim Matrix", "Claim-to-evidence map"),
            ("report_builder", "Report Builder Index", "Handoff table of contents"),
            ("report_builder_json", "Report Builder JSON", "Machine-readable handoff plan"),
            ("verification", "Package Verification", "Manifest/hash/privacy verifier"),
            ("report_preview", "Report Preview", "Pre-export blockers/warnings"),
            ("map_workspace", "Map Workspace", "Coordinate reconstruction notes"),
        ]):
            card, label, button = self._build_artifact_card(title_text, hint_text, key)
            self.report_artifact_labels[key] = label
            self.report_artifact_buttons[key] = button
            artifacts_layout.addWidget(card, idx // 3, idx % 3)
        for col in range(3):
            artifacts_layout.setColumnStretch(col, 1)
        layout.addWidget(self._shell("Artifact Cards", artifacts_frame, "Open generated report artifacts directly instead of hunting through folders."))

        report_grid = QGridLayout()
        report_grid.setContentsMargins(0, 0, 0, 0)
        report_grid.setHorizontalSpacing(12)
        report_grid.setVerticalSpacing(12)
        report_grid.addWidget(self._shell("Package Status", self.export_summary, "HTML, PDF, CSV, JSON, validation, and courtroom outputs are summarized here."), 0, 0)
        report_grid.addWidget(self._shell("Courtroom Output Notes", self.report_notes_view, "Use this page as the document hub after generation."), 0, 1)
        report_grid.addWidget(self._shell("Batch Queue & Intake Progress", self.batch_queue_view, "Drag-and-drop or import multiple sets; queued batches start automatically."), 1, 0)
        report_grid.addWidget(self._shell("Graceful Error Log", self.error_log_view, "User-visible runtime issues are stored here and mirrored to logs/app_errors.log and structured_failures.jsonl."), 1, 1)
        report_grid.addWidget(self._shell("Pre-export Preview", self.report_preview_view, "Blockers/warnings/artifact contract before you generate a report package."), 2, 0, 1, 2)
        report_grid.setColumnStretch(0, 1)
        report_grid.setColumnStretch(1, 1)
        layout.addLayout(report_grid)
        layout.addStretch(1)
        return widget


    def preview_report_package(self) -> None:
        try:
            from ...core.report_preview import render_report_preview
        except Exception:  # pragma: no cover
            from app.core.report_preview import render_report_preview
        text = render_report_preview(
            list(getattr(self.case_manager, "records", [])),
            privacy_level="redacted_text",
            export_mode="Shareable Redacted",
            verification_passed=None,
        )
        if hasattr(self, "report_preview_view"):
            self.report_preview_view.setPlainText(text)
        self._show_toast("Export preview ready", "Review blockers/warnings before generating the package.", tone="info")

    def _build_artifact_card(self, title: str, subtitle: str, artifact: str):
        frame = QFrame()
        frame.setObjectName("ReportArtifactCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 11, 12, 11)
        layout.setSpacing(5)
        frame.setMinimumHeight(118)
        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("CardSubtext")
        subtitle_label.setWordWrap(True)
        status_label = QLabel("Not generated yet")
        status_label.setObjectName("PreviewMetaValue")
        status_label.setWordWrap(True)
        open_button = QPushButton("Open")
        open_button.setObjectName("SmallGhostButton")
        open_button.clicked.connect(lambda _=False, key=artifact: self._open_export_artifact(key))
        open_button.setEnabled(False)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addWidget(status_label)
        layout.addStretch(1)
        layout.addWidget(open_button, alignment=Qt.AlignLeft)
        return frame, status_label, open_button

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
        self.btn_cases_backup = QPushButton("Create Backup")
        self.btn_cases_backup.clicked.connect(self.create_case_backup_from_ui)
        self.btn_cases_restore = QPushButton("Restore Backup")
        self.btn_cases_restore.clicked.connect(self.restore_case_backup_from_ui)
        self.btn_cases_refresh = QPushButton("Refresh")
        self.btn_cases_refresh.clicked.connect(self._refresh_cases_page)
        for btn in [self.btn_cases_open, self.btn_cases_snapshot, self.btn_cases_rename, self.btn_cases_backup, self.btn_cases_restore, self.btn_cases_refresh]:
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


    def _set_workspace_mode(self, mode: str) -> None:
        try:
            from ...core.workspace_modes import normalize_mode, mode_tooltip
        except Exception:  # pragma: no cover
            from app.core.workspace_modes import normalize_mode, mode_tooltip
        self.current_workspace_mode = normalize_mode(mode)
        self.settings.setValue("workspace_mode", self.current_workspace_mode)
        if hasattr(self, "mode_badge"):
            self.mode_badge.setText(f"{self.current_workspace_mode} mode")
        if hasattr(self, "command_hint"):
            self.command_hint.setText(mode_tooltip(self.current_workspace_mode))
        self._apply_workspace_mode()

    def _apply_workspace_mode(self) -> None:
        try:
            from ...core.workspace_modes import allowed_pages_for_mode, get_workspace_mode_profile
        except Exception:  # pragma: no cover
            from app.core.workspace_modes import allowed_pages_for_mode, get_workspace_mode_profile
        allowed = allowed_pages_for_mode(getattr(self, "current_workspace_mode", "Analyst"))
        for page, button in getattr(self, "page_buttons", {}).items():
            button.setVisible(page in allowed)
        current_page = None
        if hasattr(self, "workspace_stack") and hasattr(self, "workspace_pages"):
            current_widget = self.workspace_stack.currentWidget()
            for page, widget in self.workspace_pages.items():
                if widget is current_widget:
                    current_page = page
                    break
            if current_page and current_page not in allowed:
                self._set_workspace_page(get_workspace_mode_profile(self.current_workspace_mode).allowed_pages[0])

    def _set_workspace_page(self, page: str) -> None:
        alias_map = {"Overview": "Review", "Insights": "Dashboard", "CTF GeoLocator": "OSINT Workbench", "CTF": "OSINT Workbench", "OSINT CTF": "OSINT Workbench", "Map": "Map Workspace"}
        resolved = alias_map.get(page, page)
        try:
            from ...core.workspace_modes import allowed_pages_for_mode, get_workspace_mode_profile
            allowed = allowed_pages_for_mode(getattr(self, "current_workspace_mode", "Analyst"))
            if resolved not in allowed:
                resolved = get_workspace_mode_profile(getattr(self, "current_workspace_mode", "Analyst")).allowed_pages[0]
        except Exception as exc:
            log_failure(
                getattr(self, "logger", None),
                context="main_window",
                operation="set_workspace_page",
                message=f"Workspace mode guard failed for requested page {page!r}.",
                exc=exc,
                log_dir=getattr(self, "project_root", Path.cwd()) / "logs",
                severity="warning",
                user_visible=False,
            )
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

    def _micro_badge(self, text: str, semantic: str = "") -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("MicroBadge")
        lbl.setWordWrap(True)
        if semantic:
            lbl.setProperty("semantic", semantic)
        return lbl

    def _risk_badge(self, text: str, level: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        self._apply_risk_badge_style(lbl, level)
        return lbl


    def _refresh_dashboard_selection_widgets(self, record: Optional[EvidenceRecord] = None) -> None:
        if not hasattr(self, "dashboard_action_center"):
            return
        record = record or self.selected_record()
        if record is None:
            self.dashboard_evidence_preview.clear_source("Evidence Viewer: no evidence selected. Import/select an item to show image and crop context.")
            self.dashboard_action_center.setPlainText(
                "Next actions:\n"
                "- Import evidence or open a recent case.\n"
                "- Run OCR Setup Wizard if OCR is disabled.\n"
                "- Use Review for visual inspection and Manual Crop OCR when labels are small.\n"
                "- Export only after the Launch Gate and package verifier pass."
            )
            self.dashboard_claim_links_view.setPlainText("Claim-to-evidence links will appear after a record is selected.")
            return

        pixmap = self.current_preview_pixmap if getattr(self, "current_preview_pixmap", None) is not None else QPixmap(str(record.file_path))
        if pixmap is not None and not pixmap.isNull():
            self.dashboard_evidence_preview.set_source_pixmap(pixmap)
        else:
            self.dashboard_evidence_preview.clear_source(self._build_parser_fallback_text(record))

        actions = []
        for attr in ("map_extraction_plan", "map_recommended_actions", "location_estimate_next_actions", "next_actions"):
            value = getattr(record, attr, None)
            if isinstance(value, list):
                actions.extend(str(item) for item in value if str(item).strip())
        if not actions:
            actions = [
                "Open Review and verify the visual evidence manually.",
                "Run Manual Crop OCR on map labels, street signs, UI text, or hidden small text.",
                "Use OCR Setup Wizard if OCR confidence is 0% or language packs are missing.",
                "Generate a redacted export package only after claim links and verification are reviewed.",
            ]
        seen = set()
        clean_actions = []
        for action in actions:
            if action not in seen:
                seen.add(action)
                clean_actions.append(action)

        privacy_review = getattr(record, "osint_privacy_review", {}) or {}
        if isinstance(privacy_review, dict):
            privacy_text = privacy_review.get("recommended_mode") or privacy_review.get("decision") or "Review privacy gate before export"
        else:
            privacy_text = str(privacy_review)
        route_text = "none"
        if getattr(record, 'map_route_start_label', '') or getattr(record, 'map_route_end_label', ''):
            route_text = f"{getattr(record, 'map_route_start_label', '') or 'unknown'} → {getattr(record, 'map_route_end_label', '') or 'unknown'}"
        cluster_count = len(getattr(record, 'map_label_clusters', []) or [])
        offline_hits = len(getattr(record, 'map_offline_geocoder_hits', []) or [])
        radius = int(getattr(record, 'map_confidence_radius_m', 0) or 0)
        gate = evaluate_launch_readiness(self.case_manager.records, privacy_level="full")
        gate_lines = [f"Launch Gate: {gate.label} ({gate.score}%)", f"Gate status: {gate.status}"]
        if gate.blockers:
            gate_lines.append("Top blocker: " + gate.blockers[0])
        elif gate.warnings:
            gate_lines.append("Top warning: " + gate.warnings[0])

        self.dashboard_action_center.setPlainText(
            "\n".join(gate_lines) + "\n\n"
            f"{record.evidence_id} — {record.file_name}\n"
            f"Map readiness: {getattr(record, 'map_answer_readiness_label', 'Not answer-ready')} ({getattr(record, 'map_answer_readiness_score', 0)}%) | radius≈{radius}m\n"
            f"OCR confidence: {getattr(record, 'ocr_confidence', 0)}% | label clusters={cluster_count} | offline hits={offline_hits}\n"
            f"Route: {route_text}\n"
            f"Geo: native={getattr(record, 'gps_confidence', 0)}% derived={getattr(record, 'derived_geo_confidence', 0)}% | Privacy: {privacy_text}\n\n"
            "Next actions:\n" + "\n".join(f"- {action}" for action in clean_actions[:7])
        )

        links = list(getattr(record, "claim_to_evidence_links", []) or [])
        if not links:
            try:
                from ...core.evidence_claims import build_claim_links_dicts
            except ImportError:  # pragma: no cover
                from app.core.evidence_claims import build_claim_links_dicts
            links = build_claim_links_dicts(record)
        rows = []
        for item in links[:10]:
            if hasattr(item, "to_dict"):
                item = item.to_dict()
            rows.append(
                f"- {item.get('claim_id', 'claim')} | {item.get('status', 'review')} | "
                f"{item.get('source_family', 'unknown')} | {item.get('confidence', 0)}% :: {item.get('summary', '')}"
            )
        self.dashboard_claim_links_view.setPlainText(
            "Claim-to-evidence links:\n" + ("\n".join(rows) if rows else "- No claim links yet. Run analysis/rescan to attach auditable claim rows.")
        )

    def _apply_risk_badge_style(self, label: QLabel, level: str) -> None:
        object_name = {"High": "RiskBadgeHigh", "Medium": "RiskBadgeMedium", "Low": "RiskBadgeLow"}.get(level, "RiskBadgeLow")
        label.setObjectName(object_name)
        label.style().unpolish(label)
        label.style().polish(label)
        label.update()

    def refresh_dashboard(self) -> None:
        stats = self.case_manager.build_stats()
        high = sum(1 for record in self.case_manager.records if record.risk_level == "High")
        self.card_total.set_value(str(stats.total_images))
        self.card_total.set_subtitle("Total evidence items in the active isolated case.")
        self.card_high.set_value(str(high))
        self.card_high.set_subtitle("Items that should be reviewed first.")
        native_gps_count = stats.gps_enabled
        derived_anchor_count = sum(1 for record in self.case_manager.records if not record.has_gps and (getattr(record, "derived_geo_display", "Unavailable") != "Unavailable" or int(getattr(record, "map_answer_readiness_score", 0) or 0) >= 70))
        self.card_gps.set_value(f"{native_gps_count} GPS / {derived_anchor_count} map")
        self.card_gps.set_subtitle("Native GPS plus derived map/URL/OCR anchors. Click to show all geo-ready evidence.")
        self.card_duplicates.set_value(str(stats.duplicates_count))
        self.card_duplicates.set_subtitle("Near-duplicate groups that can collapse redundant review.")
        self.card_timeline.set_value(stats.timeline_span)
        self.card_timeline.set_subtitle("Recovered chronological span across the active case.")
        self.card_integrity.set_value(stats.integrity_summary)
        self.card_integrity.set_subtitle("Case-level integrity and custody isolation summary.")
        self._set_info_badge(self.integrity_label, "Case Integrity", stats.integrity_summary)
        has_geo_or_map_signal = stats.gps_enabled > 0 or any(
            (getattr(record, "derived_geo_display", "Unavailable") != "Unavailable")
            or int(getattr(record, "map_intelligence_confidence", 0) or 0) > 0
            for record in self.case_manager.records
        )
        self.btn_open_map.setEnabled(has_geo_or_map_signal and self.current_map_path is not None)
        self.btn_generate_report.setEnabled(stats.total_images > 0 and self.analysis_thread is None)
        self.btn_courtroom.setEnabled(stats.total_images > 0 and self.analysis_thread is None)
        self.btn_compare.setEnabled(len(self.records) >= 2)
        assessment = self._build_case_assessment_text()
        priority = self._build_priority_text()
        self.export_summary.setPlainText(self.export_summary.toPlainText() if self.export_summary.toPlainText().strip() else "No export package generated for the current case yet.")
        if hasattr(self, "reports_metric_package_value"):
            generated = sum(1 for label in getattr(self, "report_artifact_labels", {}).values() if label.text() != "Not generated yet")
            self.reports_metric_package_value.setText("Ready" if generated else "Pending")
            self.reports_metric_package_note.setText(f"{generated} generated artifact(s) in the current report hub.")
            top_readiness = max([int(getattr(record, "map_answer_readiness_score", 0) or 0) for record in self.case_manager.records], default=0)
            answer_ready = sum(1 for record in self.case_manager.records if int(getattr(record, "map_answer_readiness_score", 0) or 0) >= 70)
            self.reports_metric_ctf_value.setText(f"{top_readiness}%")
            self.reports_metric_ctf_note.setText(f"{answer_ready} answer-ready item(s); weak visual map leads remain internal.")
        if hasattr(self, "summary_text"):
            self.summary_text.setPlainText(assessment)
        if hasattr(self, "dashboard_priority_text"):
            self.dashboard_priority_text.setPlainText(priority)
        self.command_progress.setText("Ready" if not self.records else f"Active case: {self.case_manager.active_case_id}")
        self.inventory_meta.setText(self._inventory_status_message(self.filtered_records if self.filtered_records else ([] if self.records else [])))
        if hasattr(self, "ai_guardian_summary"):
            self.refresh_ai_guardian()
        else:
            if hasattr(self, "osint_hypothesis_view"):
                refresh_osint_workbench_page(self)
            if hasattr(self, "ctf_clue_cards_view"):
                refresh_ctf_geolocator_page(self)
        if hasattr(self, "map_workspace_summary_view"):
            refresh_map_workspace_page(self)
        if hasattr(self, "_refresh_dashboard_selection_widgets"):
            self._refresh_dashboard_selection_widgets(self.selected_record())
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
        selected = self.selected_record()
        summary = [
            f"Total audit events: {len(log.splitlines()) if log else 0}",
            f"Filtered events shown: {len(lines)}",
            f"Active case: {self.case_manager.active_case_id}",
            f"Selected evidence slice: {selected.evidence_id if selected else 'none'}",
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

    def open_ocr_setup_wizard(self) -> None:
        dialog = OCRSetupWizardDialog(self)
        dialog.exec_()

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
