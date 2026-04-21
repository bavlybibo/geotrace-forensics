APP_STYLESHEET = """
QMainWindow { background-color: #040d16; }
QWidget { color: #eaf4fb; font-family: 'Segoe UI'; font-size: 10pt; }
QToolTip { background-color: #0d2032; color: #eef9ff; border: 1px solid #244a6e; padding: 6px 8px; }

QFrame#HeaderFrame {
    border: 1px solid #112537;
    border-radius: 22px;
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #07121d, stop:0.55 #0b1b2a, stop:1 #0d2032);
}
QFrame#PanelFrame, QFrame#CompactPanel, QFrame#SecondaryPanel, QFrame#HeroPreviewPanel, QFrame#VerdictPanel {
    background-color: #07131e;
    border: 1px solid #0f2334;
    border-radius: 18px;
}
QFrame#CompactPanel { background-color: #081520; }
QFrame#SecondaryPanel { background-color: #091723; border-color:#132b40; }
QFrame#HeroPreviewPanel { background-color:#06131e; border-color:#14344b; }
QFrame#VerdictPanel { background-color:#081725; border-color:#143048; }
QFrame#StatCard { background-color: #07131e; border: 1px solid #10283b; border-radius: 18px; }
QFrame#StatCard:hover { border-color: #42d2ff; background-color: #091826; }
QFrame#StatCardAccent { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16b4ff, stop:1 #7deaff); border:none; border-radius:999px; min-height:4px; max-height:4px; }
QFrame#PreviewCanvasFrame { background-color:#020c14; border:1px solid #14324a; border-radius:20px; }

QPushButton { background-color:#0d2237; border:1px solid #1f4466; border-radius:12px; padding:9px 13px; color:#f4fbff; font-weight:700; }
QPushButton:hover { background-color:#12314c; border-color:#39c6ff; }
QPushButton:pressed { background-color:#091827; }
QPushButton:disabled { background-color:#07121d; color:#64809b; border-color:#16314a; }
QPushButton#PrimaryButton { background-color:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1db7ff, stop:1 #7df1ff); color:#04111a; border:1px solid #96f1ff; font-weight:800; }
QPushButton#GhostButton { background-color:transparent; color:#c9efff; }
QPushButton#SmallGhostButton { background-color: rgba(9,28,44,0.82); border:1px solid #214362; border-radius:11px; padding:6px 10px; color:#d8f5ff; font-size:9.1pt; }
QPushButton#SmallGhostButton:hover { background-color: rgba(14,39,60,0.95); }
QPushButton#PageButton { background-color:transparent; border:1px solid #17314a; color:#cbeeff; border-radius:12px; padding:8px 12px; font-weight:700; }
QPushButton#PageButton:hover { border-color:#35cdff; background-color:#0b1d2d; }
QPushButton#PageButtonActive { background-color:#10283d; border:1px solid #43d2ff; color:#8fe6ff; border-radius:12px; padding:8px 12px; font-weight:800; }

QLineEdit, QComboBox, QTextEdit, QPlainTextEdit {
    background-color:#04101a; border:1px solid #163650; border-radius:13px; padding:10px 12px; color:#eef7ff; selection-background-color:#1387cc;
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus { border-color:#33cbff; }
QComboBox::drop-down { border:none; width:24px; }
QComboBox QAbstractItemView { background-color:#071321; border:1px solid #1d4369; selection-background-color:#143d63; color:#edf6ff; }
QCheckBox { color:#dcefff; spacing:8px; }
QCheckBox::indicator { width:16px; height:16px; }
QCheckBox::indicator:unchecked { border:1px solid #2a5f8f; background:#081523; border-radius:4px; }
QCheckBox::indicator:checked { border:1px solid #67dcff; background:#15a9f4; border-radius:4px; }

QLabel#TitleLabel { font-size:24pt; font-weight:900; color:#95e8ff; }
QLabel#SubtitleLabel { color:#a6bed1; font-size:10.6pt; line-height: 1.35em; }
QLabel#SectionLabel { font-size:14.2pt; font-weight:900; color:#a9ebff; }
QLabel#SectionMetaLabel { color:#8eabbe; font-size:10pt; line-height: 1.35em; }
QLabel#MutedLabel { color:#7f9bb2; font-size:9.5pt; }
QLabel#BadgeLabel, QLabel#MicroBadge, QLabel#InfoBadge, QLabel#PreviewStateBadge, QLabel#ScoreBreakdownBadge {
    background-color: rgba(12,33,52,0.9); border:1px solid #204564; border-radius:12px; padding:7px 10px; color:#dff6ff; font-size:9.2pt;
}
QLabel#BadgeLabel { border-radius: 14px; }
QLabel#PreviewStateBadge, QLabel#ScoreBreakdownBadge { font-weight:700; }
QLabel#RiskBadgeHigh { background-color: rgba(67,24,32,0.92); border:1px solid #965163; color:#ffb7c2; border-radius:12px; padding:7px 10px; font-weight:700; }
QLabel#RiskBadgeMedium { background-color: rgba(67,52,21,0.92); border:1px solid #8f7440; color:#ffd98d; border-radius:12px; padding:7px 10px; font-weight:700; }
QLabel#RiskBadgeLow { background-color: rgba(18,62,38,0.92); border:1px solid #3f8a61; color:#b0f0cb; border-radius:12px; padding:7px 10px; font-weight:700; }
QLabel#TimelineBadge { background-color: rgba(8,28,44,0.9); border:1px solid #24496f; border-radius:14px; padding:8px 10px; color:#e9f5ff; font-size:9.3pt; font-weight:600; }
QLabel#CardValue { font-size:22pt; font-weight:900; color:#ffffff; }
QLabel#CardTitle { color:#dcefff; font-size:10.2pt; font-weight:700; }
QLabel#CardSubtext { color:#8dafca; font-size:9.2pt; }
QLabel#CardChip { color:#81d8ff; font-size:8.5pt; font-weight:700; padding:3px 8px; border-radius:999px; background-color: rgba(15,44,70,0.88); border:1px solid #275881; }
QLabel#PreviewMetaTitle { color:#89a8c0; font-size:9pt; font-weight:600; }
QLabel#PreviewMetaValue { color:#f5fbff; font-size:10.4pt; font-weight:700; }
QLabel#PreviewZoomPill { background-color: rgba(11,35,55,0.92); border:1px solid #27507a; border-radius:12px; padding:5px 10px; color:#e8f7ff; font-weight:700; }
QLabel#EvidenceCardTitle { font-size:10.7pt; font-weight:800; color:#f5fbff; }
QLabel#EvidenceCardMeta { font-size:9.2pt; color:#93afc6; }
QLabel#EvidenceCardBadges { font-size:8.9pt; color:#7fdcff; }

QProgressBar#ConfidenceBar { background-color:#06111b; border:1px solid #173652; border-radius:8px; min-height:12px; max-height:12px; }
QProgressBar#ConfidenceBar::chunk { border-radius:8px; background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16b0ff, stop:1 #67ecff); }
QProgressBar { background-color:#05101a; border:1px solid #17304b; border-radius:999px; text-align:center; color:#e7f7ff; min-height:18px; }
QProgressBar::chunk { border-radius:999px; background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #12aaff, stop:1 #66ecff); }

QTextEdit#NarrativeView, QPlainTextEdit#TerminalView { background-color:#06111b; border:1px solid #11283b; border-radius:16px; padding:14px; }
QTextEdit#NarrativeView { color:#e9f5ff; }
QPlainTextEdit#TerminalView { color:#ccecff; }

QListWidget#EvidenceList { background-color:#05101a; border:1px solid #12283a; border-radius:18px; padding:8px; }
QListWidget#EvidenceList::item { border:none; padding:4px; }
QListWidget#EvidenceList::item:selected { background:transparent; }
QFrame#EvidenceListCard { background-color:#081621; border:1px solid #11283b; border-radius:16px; }
QFrame#EvidenceListCard[selected="true"] { border:1px solid #47d6ff; background-color:#0a1c2b; }
QLabel#EvidenceThumb { border:1px solid #15324a; border-radius:12px; background-color:#06111b; }

QScrollBar:vertical { background:transparent; width:10px; margin:6px 2px 6px 2px; }
QScrollBar::handle:vertical { background:#244a6b; border-radius:5px; min-height:28px; }
QScrollBar::handle:vertical:hover { background:#2d648d; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal, QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background:none; border:none; }
QScrollBar:horizontal { background:transparent; height:0px; margin:0; }
QScrollBar::handle:horizontal { background:transparent; }
QSplitter::handle { background-color:#091827; }
QSplitter::handle:horizontal { width:4px; }
QSplitter::handle:vertical { height:4px; }
QScrollArea { background:transparent; border:none; }
QScrollArea > QWidget > QWidget { background:transparent; }

QFrame#FailurePanel { background-color:#08121b; border:1px solid #204564; border-radius:18px; }
QTabWidget#ReviewTabs::pane { border:1px solid #133046; border-radius:16px; top:-1px; background-color:#06111b; }
QTabWidget#ReviewTabs QTabBar::tab {
    background-color:#091827; border:1px solid #17314a; color:#cbeeff; border-top-left-radius:12px; border-top-right-radius:12px;
    padding:9px 14px; margin-right:6px; font-weight:700;
}
QTabWidget#ReviewTabs QTabBar::tab:selected { background-color:#10283d; border-color:#43d2ff; color:#8fe6ff; }
QTabWidget#ReviewTabs QTabBar::tab:hover { border-color:#35cdff; background-color:#0b1d2d; }
"""
