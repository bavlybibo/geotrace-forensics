APP_STYLESHEET = """
QMainWindow { background-color: #040b13; }
QWidget { color: #eaf4fb; font-family: 'Segoe UI'; font-size: 10pt; }
QToolTip { background-color: #0d2032; color: #eef9ff; border: 1px solid #244a6e; padding: 6px 8px; }
QMenu { background-color:#091824; color:#eef8ff; border:1px solid #1f476a; border-radius:12px; padding:8px; }
QMenu::item { padding:8px 14px; border-radius:8px; margin:2px 4px; }
QMenu::item:selected { background-color:#12314b; color:#97e8ff; }
QMenu::separator { height:1px; background:#173853; margin:6px 10px; }

QFrame#HeaderFrame {
    border: 1px solid #102232;
    border-radius: 20px;
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #07111b, stop:0.55 #0a1825, stop:1 #0c2131);
}
QFrame#PanelFrame, QFrame#CompactPanel, QFrame#SecondaryPanel, QFrame#HeroPreviewPanel, QFrame#VerdictPanel {
    background-color: #07131d;
    border: 1px solid #10273b;
    border-radius: 16px;
}
QFrame#CompactPanel { background-color: #08141e; }
QFrame#SecondaryPanel { background-color: #091723; border-color:#12283a; }
QFrame#HeroPreviewPanel { background-color:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #091827, stop:0.45 #07131f, stop:1 #06101a); border-color:#1b3d5a; }
QFrame#VerdictPanel { background-color:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #0a1828, stop:1 #07131d); border-color:#1c3e5a; }
QFrame#StatCard { background-color: #07131d; border: 1px solid #102436; border-radius: 16px; }
QFrame#StatCard:hover { border-color: #31c8ff; background-color: #091825; }
QFrame#StatCardAccent { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #18b4ff, stop:1 #7deaff); border:none; border-radius:999px; min-height:4px; max-height:4px; }
QFrame#PreviewCanvasFrame { background-color:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #071827, stop:1 #06121d); border:1px solid #1c4766; border-radius:22px; }

QPushButton, QToolButton {
    background-color:#0d2234; border:1px solid #173a57; border-radius:11px; padding:8px 12px; color:#f4fbff; font-weight:700; min-height:16px;
}
QPushButton:hover, QToolButton:hover { background-color:#123149; border-color:#39c6ff; }
QPushButton:pressed, QToolButton:pressed { background-color:#0a1724; }
QPushButton:disabled, QToolButton:disabled { background-color:#07121b; color:#64809b; border-color:#143046; }
QPushButton#PrimaryButton { background-color:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1db7ff, stop:1 #7df1ff); color:#04111a; border:1px solid #96f1ff; font-weight:800; }
QPushButton#GhostButton, QToolButton#GhostToolButton { background-color:transparent; color:#c9efff; }
QPushButton#SmallGhostButton { background-color: rgba(9,28,44,0.78); border:1px solid #244b69; border-radius:10px; padding:7px 12px; color:#e6f8ff; font-size:9pt; min-width:64px; }
QPushButton#SmallGhostButton:hover { background-color: rgba(14,39,60,0.88); border-color:#56d7ff; }
QPushButton#PageButton { background-color:transparent; border:1px solid #153149; color:#cbeeff; border-radius:11px; padding:7px 11px; font-weight:700; }
QPushButton#PageButton:hover { border-color:#35cdff; background-color:#0b1d2d; }
QPushButton#PageButtonActive { background-color:#10283d; border:1px solid #43d2ff; color:#8fe6ff; border-radius:11px; padding:7px 11px; font-weight:800; }
QPushButton#ActionFilesButton { background-color: rgba(42, 32, 8, 0.78); border:1px solid #8a6a25; color:#ffe7a8; }
QPushButton#ActionFilesButton:hover { background-color: rgba(53, 41, 11, 0.95); border-color:#ffd166; }
QPushButton#ActionFolderButton { background-color: rgba(51, 35, 8, 0.78); border:1px solid #9a7530; color:#ffd58c; }
QPushButton#ActionFolderButton:hover { background-color: rgba(62, 44, 11, 0.95); border-color:#ffcf70; }
QPushButton#ActionReportButton { background-color: rgba(41, 20, 58, 0.78); border:1px solid #7c58b1; color:#e5d3ff; }
QPushButton#ActionReportButton:hover { background-color: rgba(53, 25, 75, 0.95); border-color:#b48cff; }
QPushButton#ActionMapButton { background-color: rgba(10, 45, 42, 0.78); border:1px solid #2b8d84; color:#b7fff1; }
QPushButton#ActionMapButton:hover { background-color: rgba(11, 56, 52, 0.95); border-color:#4ce5d4; }
QPushButton#ActionCompareButton { background-color: rgba(54, 31, 10, 0.78); border:1px solid #b06a2d; color:#ffd7b4; }
QPushButton#ActionCompareButton:hover { background-color: rgba(69, 38, 12, 0.95); border-color:#ff9d4d; }
QToolButton#ActionMoreButton { background-color: rgba(11, 23, 34, 0.88); border:1px solid #33536f; color:#d9eefc; border-radius:11px; padding:8px 12px; }
QToolButton#ActionMoreButton:hover { background-color:#12293d; border-color:#62dfff; }

QLineEdit, QComboBox, QTextEdit, QPlainTextEdit {
    background-color:#04101a; border:1px solid #14324a; border-radius:12px; padding:9px 11px; color:#eef7ff; selection-background-color:#1387cc;
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus { border-color:#33cbff; }
QComboBox::drop-down { border:none; width:24px; }
QComboBox QAbstractItemView { background-color:#071321; border:1px solid #1d4369; selection-background-color:#143d63; color:#edf6ff; }
QCheckBox { color:#dcefff; spacing:8px; }
QCheckBox::indicator { width:16px; height:16px; }
QCheckBox::indicator:unchecked { border:1px solid #2a5f8f; background:#081523; border-radius:4px; }
QCheckBox::indicator:checked { border:1px solid #67dcff; background:#15a9f4; border-radius:4px; }

QLabel#TitleLabel { font-size:23pt; font-weight:900; color:#95e8ff; }
QLabel#SubtitleLabel { color:#a6bed1; font-size:10.2pt; }
QLabel#SectionLabel { font-size:14pt; font-weight:900; color:#a9ebff; }
QLabel#SectionMetaLabel { color:#9fbad0; font-size:9.5pt; }
QLabel#MutedLabel { color:#8eabc1; font-size:9pt; }
QLabel#BadgeLabel, QLabel#MicroBadge, QLabel#InfoBadge, QLabel#PreviewStateBadge, QLabel#ScoreBreakdownBadge, QLabel#EvidenceChip {
    background-color: rgba(12,33,52,0.86); border:1px solid #1b4261; border-radius:11px; padding:7px 11px; color:#e8f7ff; font-size:9pt;
}
QLabel#BadgeLabel { border-radius: 13px; }
QLabel#PreviewStateBadge, QLabel#ScoreBreakdownBadge, QLabel#EvidenceChip { font-weight:700; }
QLabel#RiskBadgeHigh { background-color: rgba(67,24,32,0.9); border:1px solid #965163; color:#ffb7c2; border-radius:11px; padding:6px 10px; font-weight:700; }
QLabel#RiskBadgeMedium { background-color: rgba(67,52,21,0.9); border:1px solid #8f7440; color:#ffd98d; border-radius:11px; padding:6px 10px; font-weight:700; }
QLabel#RiskBadgeLow { background-color: rgba(18,62,38,0.9); border:1px solid #3f8a61; color:#b0f0cb; border-radius:11px; padding:6px 10px; font-weight:700; }
QLabel#TimelineBadge { background-color: rgba(8,28,44,0.88); border:1px solid #1d4263; border-radius:12px; padding:7px 10px; color:#e9f5ff; font-size:9.1pt; font-weight:600; }
QLabel#CardValue { font-size:22pt; font-weight:900; color:#ffffff; }
QLabel#CardTitle { color:#dcefff; font-size:10.1pt; font-weight:700; }
QLabel#CardSubtext { color:#8dafca; font-size:9pt; }
QLabel#CardChip { color:#81d8ff; font-size:8.4pt; font-weight:700; padding:3px 8px; border-radius:999px; background-color: rgba(15,44,70,0.88); border:1px solid #275881; }
QLabel#PreviewMetaTitle { color:#89a8c0; font-size:8.8pt; font-weight:600; }
QLabel#PreviewMetaValue { color:#f5fbff; font-size:10.4pt; font-weight:700; }
QLabel#PreviewZoomPill { background-color: rgba(11,35,55,0.9); border:1px solid #214867; border-radius:11px; padding:5px 10px; color:#e8f7ff; font-weight:700; }
QLabel#EvidenceCardTitle { font-size:10.8pt; font-weight:800; color:#f5fbff; }
QLabel#EvidenceCardMeta { font-size:9pt; color:#d7edff; }
QLabel#EvidenceCardBadges { font-size:8.5pt; color:#bfefff; }
QLabel#EvidenceCardSupport { font-size:8.4pt; color:#8fd4ff; }

QProgressBar#ConfidenceBar { background-color:#06111b; border:1px solid #173652; border-radius:8px; min-height:8px; max-height:8px; margin-top:2px; margin-bottom:4px; }
QProgressBar#ConfidenceBar::chunk { border-radius:8px; background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16b0ff, stop:1 #67ecff); }
QProgressBar { background-color:#05101a; border:1px solid #17304b; border-radius:999px; text-align:center; color:#e7f7ff; min-height:18px; }
QProgressBar::chunk { border-radius:999px; background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #12aaff, stop:1 #66ecff); }

QTextEdit#NarrativeView, QPlainTextEdit#TerminalView { background-color:#06111b; border:1px solid #102538; border-radius:14px; padding:14px; }
QTextEdit#NarrativeView { color:#e9f5ff; }
QPlainTextEdit#TerminalView { color:#ccecff; }

QListWidget#EvidenceList { background-color:#05101a; border:1px solid #112638; border-radius:16px; padding:10px; }
QListWidget#EvidenceList::item { border:none; padding:4px; }
QListWidget#EvidenceList::item:selected { background:transparent; }
QFrame#EvidenceListCard { background-color:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #081621, stop:1 #0a1823); border:1px solid #133149; border-radius:16px; }
QFrame#EvidenceListCard:hover { border-color:#3b698b; background-color:#0b1c2a; }
QFrame#EvidenceListCard[selected="true"] { border:1px solid #58ddff; background-color:#0c2233; box-shadow: 0 0 0 1px #89efff; }
QLabel#EvidenceThumb { border:1px solid #14324a; border-radius:10px; background-color:#06111b; }
QFrame#EvidenceAccent { background:#47d6ff; border:none; border-radius:3px; }

QScrollBar:vertical { background:transparent; width:12px; margin:6px 2px 6px 2px; }
QScrollBar::handle:vertical { background:#2a587d; border-radius:5px; min-height:34px; }
QScrollBar::handle:vertical:hover { background:#2d648d; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal, QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background:none; border:none; }
QScrollBar:horizontal { background:transparent; height:0px; margin:0; }
QScrollBar::handle:horizontal { background:transparent; }
QSplitter::handle { background-color:#07131d; }
QSplitter::handle:horizontal { width:5px; }
QSplitter::handle:vertical { height:3px; }
QScrollArea { background:transparent; border:none; }
QScrollArea > QWidget > QWidget { background:transparent; }

QFrame#FailurePanel { background-color:#08121b; border:1px solid #204564; border-radius:16px; }
QTabWidget#ReviewTabs::pane { border:1px solid #11293b; border-radius:15px; top:-1px; background-color:#06111b; margin-top:2px; }
QTabWidget#ReviewTabs QTabBar::tab {
    background-color:#091827; border:1px solid #14314a; color:#cbeeff; border-top-left-radius:11px; border-top-right-radius:11px;
    padding:10px 16px 10px 16px; margin-right:6px; font-weight:700; font-size:10pt; min-width:92px; min-height:26px; qproperty-alignment: AlignCenter;
}
QTabWidget#ReviewTabs QTabBar::tab:selected { background-color:#10283d; border-color:#43d2ff; color:#8fe6ff; }
QTabWidget#ReviewTabs QTabBar::tab:hover { border-color:#35cdff; background-color:#0b1d2d; }
QLabel#ScoreBreakdownBadge[role="auth"] { border-color:#2f8160; color:#b7ffd9; }
QLabel#ScoreBreakdownBadge[role="meta"] { border-color:#8e6e2c; color:#ffe0a8; }
QLabel#ScoreBreakdownBadge[role="tech"] { border-color:#5b70a5; color:#d6e2ff; }
QLabel#MicroBadge[semantic="parser"] { border-color:#2f8160; color:#b7ffd9; }
QLabel#MicroBadge[semantic="time"] { border-color:#8e6e2c; color:#ffe0a8; }
QLabel#MicroBadge[semantic="source"] { border-color:#6659aa; color:#e0d7ff; }
QLabel#MicroBadge[semantic="gps"] { border-color:#2a7f87; color:#bbfffa; }
"

QFrame#PanelFrame, QFrame#CompactPanel {
    background-color:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(7,20,31,0.98), stop:1 rgba(9,27,40,0.96));
    border:1px solid #16334a;
}
QFrame#PanelFrame:hover, QFrame#CompactPanel:hover { border-color:#2b5e84; }
QFrame#MetricPill {
    background-color:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(10,29,44,0.96), stop:1 rgba(12,38,58,0.96));
    border:1px solid #204c6d;
    border-radius:14px;
}
QFrame#MetricPill:hover { border-color:#53d6ff; }
QLabel#MetricPillLabel {
    color:#86b8d9;
    font-size:8.6pt;
    font-weight:700;
    text-transform:uppercase;
}
QLabel#MetricPillValue {
    color:#f4fbff;
    font-size:18pt;
    font-weight:900;
}
QLabel#MetricPillNote {
    color:#9ac0db;
    font-size:8.8pt;
}
QPushButton {
    min-height:32px;
    padding:8px 14px;
}
QPushButton#PageButtonActive {
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #114a70, stop:1 #0f6fa0);
    color:#f8fdff;
    border:1px solid #69e1ff;
}
QPushButton#PageButton:hover, QPushButton#PrimaryButton:hover {
    border-color:#69ddff;
    background-color:#10304a;
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QListWidget, QTableWidget {
    selection-background-color:#12486d;
    selection-color:#ffffff;
}
QTableWidget {
    gridline-color:#173854;
    alternate-background-color:#081522;
    border-radius:14px;
}
QHeaderView::section {
    background-color:#0e2740;
    color:#dff5ff;
    padding:8px 10px;
    border:none;
    border-right:1px solid #1c4568;
    border-bottom:1px solid #1c4568;
    font-weight:800;
}
QLabel#SectionLabel {
    font-size:14.5pt;
    font-weight:900;
    color:#b8f2ff;
}
QLabel#SectionMetaLabel { color:#9ebed7; line-height:1.3; }

"

QFrame#HeroPanel {
    background-color:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(7,20,31,1.0), stop:0.48 rgba(8,31,48,0.98), stop:1 rgba(5,14,23,0.98));
    border:1px solid #1e4968;
    border-radius:18px;
}
QFrame#HeroPanel:hover { border-color:#51d7ff; }
QFrame#GeoSignalRail {
    background-color:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(6,17,27,0.98), stop:1 rgba(9,30,45,0.96));
    border:1px solid #183a55;
    border-radius:16px;
}
QFrame#ReportArtifactCard {
    background-color:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #081724, stop:1 #0a1f31);
    border:1px solid #1b4564;
    border-radius:14px;
}
QFrame#ReportArtifactCard:hover {
    border-color:#54d7ff;
    background-color:#0b2437;
}
QFrame#ReportArtifactCard QLabel#PreviewMetaValue {
    color:#9edfff;
    font-size:9.4pt;
    font-weight:800;
}
QLabel#MetricPillValue {
    color:#ffffff;
    letter-spacing:0.2px;
}
QLabel#MetricPillNote { color:#9fc2dc; }
QFrame#MetricPill {
    min-height:76px;
}
QFrame#CompactPanel QTextEdit, QFrame#CompactPanel QPlainTextEdit {
    background-color:#050f19;
}
QLabel#TitleLabel {
    font-size:24pt;
    letter-spacing:0.4px;
}

"""
