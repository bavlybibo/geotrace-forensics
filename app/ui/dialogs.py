from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from PyQt5.QtCore import QPoint, QPropertyAnimation, Qt, QTimer
from PyQt5.QtGui import QColor, QPixmap
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from ..core.models import CaseInfo, EvidenceRecord
except ImportError:  # pragma: no cover - fallback for direct script execution
    from app.core.models import CaseInfo, EvidenceRecord


DIALOG_STYLESHEET = """
QDialog#ThemedDialog { background-color:#07131e; }
QDialog#ThemedDialog QLabel { color:#eaf4fb; }
QDialog#ThemedDialog QLabel[role=muted] { color:#9fbdd2; }
QDialog#ThemedDialog QFrame#DialogCard { background:#081621; border:1px solid #14314a; border-radius:18px; }
QDialog#ThemedDialog QLineEdit,
QDialog#ThemedDialog QComboBox,
QDialog#ThemedDialog QTextEdit {
    background-color:#04101a; border:1px solid #163650; border-radius:13px; padding:10px 12px; color:#eef7ff;
}
QDialog#ThemedDialog QComboBox QAbstractItemView { background-color:#071321; border:1px solid #1d4369; selection-background-color:#143d63; color:#edf6ff; }
QDialog#ThemedDialog QPushButton { background-color:#0d2237; border:1px solid #1f4466; border-radius:12px; padding:9px 13px; color:#f4fbff; font-weight:700; }
QDialog#ThemedDialog QPushButton:hover { background-color:#12314c; border-color:#39c6ff; }
QDialog#ThemedDialog QCheckBox { color:#dcefff; spacing:8px; }
QDialog#ThemedDialog QCheckBox::indicator { width:16px; height:16px; }
QDialog#ThemedDialog QCheckBox::indicator:unchecked { border:1px solid #2a5f8f; background:#081523; border-radius:4px; }
QDialog#ThemedDialog QCheckBox::indicator:checked { border:1px solid #67dcff; background:#15a9f4; border-radius:4px; }
"""


class ToastPopup(QFrame):
    def __init__(self, parent: QWidget, title: str, message: str, *, tone: str = 'info', timeout_ms: int = 2600) -> None:
        super().__init__(parent)
        self.setObjectName('ToastPopup')
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.ToolTip)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setStyleSheet('font-weight: 800; color: #f5fbff;')
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet('color: #d9f2ff;')
        layout.addWidget(title_label)
        layout.addWidget(msg_label)
        palette = {
            'info': ('#081b2a', '#2fc8ff'),
            'success': ('#0a2318', '#6fe7a3'),
            'warning': ('#2b1d0d', '#ffd07d'),
            'error': ('#2a1217', '#ff9eb1'),
        }
        bg, border = palette.get(tone, palette['info'])
        self.setStyleSheet(f"QFrame#ToastPopup {{ background-color: {bg}; border: 1px solid {border}; border-radius: 14px; }}")
        self.adjustSize()
        self._fade = QPropertyAnimation(self, b'windowOpacity', self)
        self._fade.setDuration(240)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()
        QTimer.singleShot(timeout_ms, self._fade_out)

    def show_top_right(self, margin: int = 26) -> None:
        parent = self.parentWidget()
        if parent is None:
            self.show()
            return
        target = parent.geometry().topRight()
        x = target.x() - self.width() - margin
        y = parent.geometry().top() + margin
        self.move(QPoint(x, y))
        self.show()
        self.raise_()

    def _fade_out(self) -> None:
        self._fade = QPropertyAnimation(self, b'windowOpacity', self)
        self._fade.setDuration(280)
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self.deleteLater)
        self._fade.start()


class OnboardingDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('ThemedDialog')
        self.setStyleSheet(DIALOG_STYLESHEET)
        self.setWindowTitle('Welcome to GeoTrace Forensics X')
        self.resize(760, 560)
        self.selected_action = 'close'
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel('Welcome to GeoTrace Forensics X')
        title.setStyleSheet('font-size: 20pt; font-weight: 900; color: #95e8ff;')
        subtitle = QLabel(
            'This launch candidate opens into a case-based forensic workspace with drag and drop intake, queue-aware imports, review-first evidence inspection, recent cases, export validation, and stronger audit visibility.'
        )
        subtitle.setWordWrap(True)
        subtitle.setProperty('role', 'muted')
        subtitle.setStyleSheet('font-size: 10.5pt;')
        layout.addWidget(title)
        layout.addWidget(subtitle)

        hero = QFrame()
        hero.setObjectName('DialogCard')
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(14, 14, 14, 14)
        hero_layout.setSpacing(6)
        hero_title = QLabel('Start a protected forensic case')
        hero_title.setStyleSheet('font-size: 13pt; font-weight: 800; color: #e8f8ff;')
        hero_layout.addWidget(hero_title)
        intro = QLabel('Control how the review workspace opens, where exports land you afterward, and whether onboarding or confirmation prompts stay visible.')
        intro.setWordWrap(True)
        intro.setProperty('role', 'muted')
        hero_layout.addWidget(intro)
        layout.addWidget(hero)

        settings_card = QFrame()
        settings_card.setObjectName('DialogCard')
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(14, 14, 14, 14)
        settings_layout.setSpacing(12)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        cards = [
            ('1', 'Start with a case', 'Create or reopen a case so evidence, notes, and audit logs stay isolated.'),
            ('2', 'Drag and drop evidence', 'Drop files or folders anywhere in the window to enqueue a batch.'),
            ('3', 'Review before export', 'Use the Review page for preview, metadata overview, compare mode, and analyst notes.'),
            ('4', 'Validate the output', 'Exports now validate expected files and show completion toasts with folder links.'),
        ]
        for idx, (badge, heading, text) in enumerate(cards):
            card = QFrame()
            card.setObjectName('DialogCard')
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 14, 14, 14)
            pill = QLabel(badge)
            pill.setStyleSheet('background:#0f2a42; border:1px solid #2ecfff; border-radius:999px; padding:4px 10px; font-weight:800; color:#e9f8ff;')
            head = QLabel(heading)
            head.setStyleSheet('font-weight:800; font-size:11pt; color:#eef8ff;')
            body = QLabel(text)
            body.setWordWrap(True)
            body.setProperty('role', 'muted')
            card_layout.addWidget(pill, alignment=Qt.AlignLeft)
            card_layout.addWidget(head)
            card_layout.addWidget(body)
            grid.addWidget(card, idx // 2, idx % 2)
        layout.addLayout(grid)

        actions = QHBoxLayout()
        self.hide_future = QCheckBox('Do not show this onboarding flow again on startup')
        actions.addWidget(self.hide_future)
        actions.addStretch(1)
        self.btn_demo = QPushButton('Load Demo Folder')
        self.btn_import = QPushButton('Import Evidence Now')
        self.btn_cases = QPushButton('Open Cases Page')
        self.btn_close = QPushButton('Continue')
        for btn in [self.btn_demo, self.btn_import, self.btn_cases, self.btn_close]:
            actions.addWidget(btn)
        layout.addLayout(actions)

        self.btn_demo.clicked.connect(lambda: self._set_action('demo'))
        self.btn_import.clicked.connect(lambda: self._set_action('import'))
        self.btn_cases.clicked.connect(lambda: self._set_action('cases'))
        self.btn_close.clicked.connect(self.accept)

    def _set_action(self, action: str) -> None:
        self.selected_action = action
        self.accept()


class SettingsDialog(QDialog):
    def __init__(self, values: Dict[str, object], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('ThemedDialog')
        self.setStyleSheet(DIALOG_STYLESHEET)
        self.setWindowTitle('Settings')
        self.resize(620, 470)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel('Workspace Settings')
        title.setStyleSheet('font-size: 17pt; font-weight: 900; color: #95e8ff;')

        hero = QFrame()
        hero.setObjectName('DialogCard')
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(14, 14, 14, 14)
        hero_layout.setSpacing(6)
        hero_title = QLabel('Start a protected forensic case')
        hero_title.setStyleSheet('font-size: 13pt; font-weight: 800; color: #e8f8ff;')
        hero_layout.addWidget(hero_title)
        intro = QLabel('Control how the review workspace opens, where exports land you afterward, and whether onboarding or confirmation prompts stay visible.')
        intro.setWordWrap(True)
        intro.setProperty('role', 'muted')
        hero_layout.addWidget(intro)
        layout.addWidget(hero)

        settings_card = QFrame()
        settings_card.setObjectName('DialogCard')
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(14, 14, 14, 14)
        settings_layout.setSpacing(12)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        self.analyst_combo = QComboBox()
        self.analyst_combo.setEditable(True)
        self.analyst_combo.addItems(['Lead Analyst', 'Examiner A', 'Case Officer'])
        self.analyst_combo.setCurrentText(str(values.get('analyst_name', 'Lead Analyst')))

        self.default_page = QComboBox()
        self.default_page.addItems(['Dashboard', 'Review', 'Geo', 'Timeline', 'Custody', 'Reports', 'Cases'])
        self.default_page.setCurrentText(str(values.get('default_page', 'Dashboard')))

        self.sort_mode = QComboBox()
        self.sort_mode.addItems(['Score ↓', 'Time ↑', 'Time ↓', 'Filename A→Z', 'Filename Z→A', 'Confidence ↓', 'Bookmarked First'])
        self.sort_mode.setCurrentText(str(values.get('default_sort', 'Score ↓')))

        self.auto_reopen = QCheckBox('Reopen the last active case on startup')
        self.auto_reopen.setChecked(bool(values.get('auto_reopen_last_case', True)))
        self.open_reports_after_export = QCheckBox('Switch to Reports page after export completes')
        self.open_reports_after_export.setChecked(bool(values.get('open_reports_after_export', True)))
        self.show_toasts = QCheckBox('Show completion toasts for import, notes, and export actions')
        self.show_toasts.setChecked(bool(values.get('show_toasts', True)))
        self.confirm_before_new_case = QCheckBox('Ask for confirmation before replacing the active case context')
        self.confirm_before_new_case.setChecked(bool(values.get('confirm_before_new_case', True)))
        self.show_onboarding = QCheckBox('Show onboarding flow on startup')
        self.show_onboarding.setChecked(bool(values.get('show_onboarding', True)))

        grid.addWidget(QLabel('Analyst label'), 0, 0)
        grid.addWidget(self.analyst_combo, 0, 1)
        grid.addWidget(QLabel('Default landing page'), 1, 0)
        grid.addWidget(self.default_page, 1, 1)
        grid.addWidget(QLabel('Default evidence sort'), 2, 0)
        grid.addWidget(self.sort_mode, 2, 1)
        settings_layout.addLayout(grid)
        for widget in [self.auto_reopen, self.open_reports_after_export, self.show_toasts, self.confirm_before_new_case, self.show_onboarding]:
            settings_layout.addWidget(widget)

        notes = QLabel('Tip: review tabs now separate overview, metadata, raw tags, notes, and audit focus so the preview stage keeps a cleaner hierarchy.')
        notes.setWordWrap(True)
        notes.setProperty('role', 'muted')
        settings_layout.addWidget(notes)
        layout.addWidget(settings_card)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> Dict[str, object]:
        return {
            'analyst_name': self.analyst_combo.currentText().strip() or 'Lead Analyst',
            'default_page': self.default_page.currentText(),
            'default_sort': self.sort_mode.currentText(),
            'auto_reopen_last_case': self.auto_reopen.isChecked(),
            'open_reports_after_export': self.open_reports_after_export.isChecked(),
            'show_toasts': self.show_toasts.isChecked(),
            'confirm_before_new_case': self.confirm_before_new_case.isChecked(),
            'show_onboarding': self.show_onboarding.isChecked(),
        }


class CompareDialog(QDialog):
    def __init__(self, left: EvidenceRecord, right: EvidenceRecord, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('ThemedDialog')
        self.setStyleSheet(DIALOG_STYLESHEET)
        self.setWindowTitle(f'Compare Evidence — {left.evidence_id} vs {right.evidence_id}')
        self.resize(1120, 720)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(12)

        hero = QFrame()
        hero.setObjectName('DialogCard')
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(14, 14, 14, 14)
        summary = QLabel(f'{left.evidence_id} vs {right.evidence_id}')
        summary.setStyleSheet('font-weight:900; font-size:13pt; color:#eef8ff;')
        delta = QLabel(
            f'Score delta: {abs(left.suspicion_score - right.suspicion_score)} • '
            f'Time delta: {left.timestamp_source} vs {right.timestamp_source} • '
            f'Duplicate link: {left.duplicate_group or "None"} / {right.duplicate_group or "None"}'
        )
        delta.setWordWrap(True)
        delta.setProperty('role', 'muted')
        hero_layout.addWidget(summary)
        hero_layout.addWidget(delta)
        outer.addWidget(hero)

        layout = QHBoxLayout()
        layout.setSpacing(12)
        layout.addWidget(self._build_record_panel(left), 1)
        layout.addWidget(self._build_record_panel(right), 1)
        outer.addLayout(layout, 1)

    def _build_record_panel(self, record: EvidenceRecord) -> QWidget:
        frame = QFrame()
        frame.setObjectName('DialogCard')
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        title = QLabel(f'{record.evidence_id} — {record.file_name}')
        title.setStyleSheet('font-weight:900; font-size:12pt; color:#eef8ff;')
        body = QTextEdit()
        body.setReadOnly(True)
        body.setPlainText(
            '\n'.join([
                f'Source Type: {record.source_type}',
                f'Risk / Score: {record.risk_level} / {record.suspicion_score}',
                f'Confidence: {record.confidence_score}%',
                f'Timestamp: {record.timestamp} ({record.timestamp_source})',
                f'Device: {record.device_model}',
                f'GPS: {record.gps_display}',
                f'Parser: {record.parser_status}',
                f'Signature: {record.signature_status} ({record.format_signature})',
                f'Trust: {record.format_trust}',
                f'Hidden markers: {len(record.hidden_code_indicators)} code / {len(record.extracted_strings)} context string',
                f'Duplicate Group: {record.duplicate_group or "None"}',
                '',
                'Analyst Verdict:',
                record.analyst_verdict or 'No analyst verdict.',
                '',
                'Anomaly Reasons:',
                *(record.anomaly_reasons or ['None']),
                '',
                'OSINT / Follow-up Leads:',
                *(record.osint_leads or ['None']),
            ])
        )
        layout.addWidget(title)
        layout.addWidget(body, 1)
        return frame


class DuplicateReviewDialog(QDialog):
    def __init__(self, records: Iterable[EvidenceRecord], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Duplicate Cluster Review')
        self.resize(720, 520)
        self.selected_evidence_id: Optional[str] = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        title = QLabel('Duplicate Cluster Review')
        title.setStyleSheet('font-size: 17pt; font-weight: 900; color: #95e8ff;')
        layout.addWidget(title)
        self.list_widget = QListWidget()
        cluster_count = 0
        for record in records:
            if not record.duplicate_group:
                continue
            cluster_count += 1
            item = QListWidgetItem(f'{record.duplicate_group} — {record.evidence_id} — {record.file_name}')
            item.setData(Qt.UserRole, record.evidence_id)
            self.list_widget.addItem(item)
        if cluster_count == 0:
            empty = QListWidgetItem('No duplicate clusters are available in the active case.')
            empty.setFlags(Qt.NoItemFlags)
            self.list_widget.addItem(empty)
        layout.addWidget(self.list_widget, 1)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        open_btn = QPushButton('Jump to Selected Item')
        close_btn = QPushButton('Close')
        btn_row.addWidget(open_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        open_btn.clicked.connect(self._accept)
        close_btn.clicked.connect(self.reject)

    def _accept(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        self.selected_evidence_id = item.data(Qt.UserRole)
        self.accept()


class RecentCasesDialog(QDialog):
    def __init__(self, cases: List[CaseInfo], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Recent Cases')
        self.resize(720, 520)
        self.selected_case_id: Optional[str] = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        title = QLabel('Recent Cases')
        title.setStyleSheet('font-size: 17pt; font-weight: 900; color: #95e8ff;')
        layout.addWidget(title)
        self.list_widget = QListWidget()
        for case in cases:
            item = QListWidgetItem(f'{case.case_name} — {case.case_id} — {case.item_count} item(s) — updated {case.updated_at}')
            item.setData(Qt.UserRole, case.case_id)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Open | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        self.selected_case_id = item.data(Qt.UserRole)
        self.accept()
