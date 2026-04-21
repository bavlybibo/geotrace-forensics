APP_STYLESHEET = """
QMainWindow { background-color: #07111a; }
QWidget { color: #ebf4fb; font-family: 'Segoe UI'; font-size: 10pt; }
QToolTip { background-color: #112538; color: #eef9ff; border: 1px solid #376386; padding: 6px 8px; }
QFrame#HeaderFrame {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0a1725, stop:0.55 #10253b, stop:1 #17314b);
    border: 1px solid #254d6d; border-radius: 22px; }
QFrame#PanelFrame, QFrame#CompactPanel, QFrame#SecondaryPanel, QFrame#HeroPreviewPanel, QFrame#VerdictPanel {
    background-color: #0a1622; border: 1px solid #224764; border-radius: 18px; }
QFrame#CompactPanel { background-color: #0b1825; }
QFrame#SecondaryPanel { background-color: #0a1420; border-radius: 16px; }
QFrame#HeroPreviewPanel { border-color: #2a567c; }
QFrame#VerdictPanel { background-color: #0c1825; border-color: #2b5a7c; }
QFrame#StatCard { background-color: #0c1724; border: 1px solid #234967; border-radius: 18px; }
QFrame#StatCard:hover { border-color: #76d8ff; background-color: #0e1c2b; }
QFrame#StatCardAccent { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5dd7ff, stop:0.55 #7ff7d1, stop:1 #8ba5ff); border:none; border-radius:999px; min-height:4px; max-height:4px; }
QPushButton { background-color:#10233a; border:1px solid #34597c; border-radius:12px; padding:9px 14px; color:#f4fbff; font-weight:600; }
QPushButton:hover { background-color:#15304a; border-color:#7de3ff; }
QPushButton:pressed { background-color:#0a1826; }
QPushButton:disabled { background-color:#0b131d; color:#6f8597; border-color:#1f3245; }
QPushButton#PrimaryButton { background-color:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #58d4ff, stop:0.55 #77f0d2, stop:1 #94a4ff); color:#03131d; border:1px solid #c1fbff; font-weight:800; }
QPushButton#PrimaryButton:hover { background-color:#9df5ff; }
QPushButton#GhostButton { background-color:transparent; color:#d7f2ff; }
QPushButton#SmallGhostButton { background-color: rgba(12,29,44,0.9); border:1px solid #325774; border-radius:12px; padding:6px 10px; color:#e2f7ff; font-size:9.3pt; }
QPushButton#SmallGhostButton:hover { background-color: rgba(19,43,63,0.96); }
QLineEdit, QComboBox, QTextEdit, QPlainTextEdit { background-color:#07111a; border:1px solid #244a67; border-radius:14px; padding:10px 12px; color:#eef7ff; selection-background-color:#1597d4; }
QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus { border-color:#7de3ff; }
QComboBox::drop-down { border:none; width:24px; }
QComboBox QAbstractItemView { background-color:#0b1521; border:1px solid #28516f; selection-background-color:#173f62; color:#edf6ff; }
QLabel#TitleLabel { font-size:22pt; font-weight:900; color:#82e5ff; }
QLabel#SubtitleLabel { color:#c6d9e8; font-size:10pt; }
QLabel#SectionLabel { font-size:12.2pt; font-weight:800; color:#96e6ff; }
QLabel#SectionMetaLabel { color:#9cb7cb; font-size:9.5pt; }
QLabel#MutedLabel { color:#95adbf; font-size:9.3pt; }
QLabel#BadgeLabel, QLabel#MicroBadge, QLabel#InfoBadge, QLabel#PreviewStateBadge, QLabel#ScoreBreakdownBadge {
    background-color: rgba(14,34,50,0.95); border:1px solid #315976; border-radius:12px; padding:7px 10px; color:#e5f8ff; font-size:9.2pt; }
QLabel#BadgeLabel { border-radius:14px; }
QLabel#PreviewStateBadge, QLabel#ScoreBreakdownBadge { font-weight:700; }
QLabel#RiskBadgeHigh { background-color: rgba(76,25,37,0.95); border:1px solid #b45f76; color:#ffd0d9; border-radius:12px; padding:7px 10px; font-weight:700; }
QLabel#RiskBadgeMedium { background-color: rgba(72,56,22,0.95); border:1px solid #b68b38; color:#ffe09b; border-radius:12px; padding:7px 10px; font-weight:700; }
QLabel#RiskBadgeLow { background-color: rgba(20,68,44,0.95); border:1px solid #4c9a73; color:#b6f3d2; border-radius:12px; padding:7px 10px; font-weight:700; }
QLabel#TimelineBadge { background-color: rgba(10,29,44,0.95); border:1px solid #2f5977; border-radius:14px; padding:8px 10px; color:#edf6ff; font-size:9.2pt; font-weight:600; }
QLabel#CardValue { font-size:25pt; font-weight:900; color:#ffffff; }
QLabel#CardTitle { color:#e2f0fb; font-size:10.3pt; font-weight:700; }
QLabel#CardSubtext { color:#9bb5c8; font-size:9.1pt; }
QLabel#CardChip { color:#dffaff; font-size:8.6pt; font-weight:700; padding:3px 8px; border-radius:999px; background-color: rgba(17,53,79,0.9); border:1px solid #406e92; }
QLabel#PreviewMetaTitle { color:#9ab1c3; font-size:9pt; font-weight:600; }
QLabel#PreviewMetaValue { color:#f2f8ff; font-size:10pt; font-weight:700; }
QLabel#PreviewZoomPill { background-color: rgba(14,35,52,0.95); border:1px solid #3d6786; border-radius:12px; padding:5px 10px; color:#eef8ff; font-weight:700; }
QFrame#PreviewCanvasFrame { background-color:#06111b; border:1px dashed #315d7d; border-radius:18px; }
QProgressBar#ConfidenceBar { background-color:#08131d; border:1px solid #224967; border-radius:8px; min-height:12px; max-height:12px; }
QProgressBar#ConfidenceBar::chunk { border-radius:8px; background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5fd1ff, stop:0.5 #7ff0d2, stop:1 #95a1ff); }
QTextEdit#NarrativeView, QPlainTextEdit#TerminalView { background-color:#08131d; border:1px solid #214562; border-radius:14px; padding:12px; }
QTextEdit#NarrativeView { color:#edf6ff; line-height:1.45; }
QPlainTextEdit#TerminalView { color:#d5efff; }
QTableWidget { background-color:#07111a; border:1px solid #20415b; border-radius:16px; gridline-color:transparent; alternate-background-color: rgba(13,26,39,0.76); selection-background-color: rgba(31,136,199,0.32); selection-color:#ffffff; }
QHeaderView::section { background-color:#102136; color:#9fe8ff; border:none; border-bottom:1px solid #214766; padding:10px 8px; font-weight:800; }
QTableWidget::item { padding:8px; border-bottom:1px solid rgba(32,71,102,0.38); }
QTableCornerButton::section { background-color:#102136; border:none; }
QTabWidget::pane { border:1px solid #214663; border-radius:16px; top:-1px; background:#0a1521; }
QTabBar::tab { background:transparent; border:1px solid #244a66; border-bottom:none; padding:10px 16px; margin-right:8px; min-width:90px; border-top-left-radius:14px; border-top-right-radius:14px; color:#afcddd; font-weight:700; }
QTabBar::tab:selected { background:#10233a; color:#96e5ff; border-color:#4f7ca0; }
QTabBar::tab:hover { color:#e3f7ff; }
QProgressBar { background-color:#09131c; border:1px solid #20435f; border-radius:999px; text-align:center; color:#e7f7ff; min-height:20px; }
QProgressBar::chunk { border-radius:999px; background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5fd1ff, stop:0.5 #7ff0d2, stop:1 #95a1ff); }
QScrollBar:vertical { background:transparent; width:10px; margin:6px 2px 6px 2px; }
QScrollBar::handle:vertical { background:#426987; border-radius:5px; min-height:28px; }
QScrollBar::handle:vertical:hover { background:#5d88a9; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal, QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background:none; border:none; }
QScrollBar:horizontal { background:transparent; height:10px; margin:2px 6px 2px 6px; }
QScrollBar::handle:horizontal { background:#426987; border-radius:5px; min-width:28px; }
QScrollBar::handle:horizontal:hover { background:#5d88a9; }
QSplitter::handle { background-color:#0b1622; }
QSplitter::handle:horizontal { width:5px; }
QSplitter::handle:vertical { height:5px; }
QScrollArea { background:transparent; border:none; }
QScrollArea > QWidget > QWidget { background:transparent; }
"""
