APP_STYLESHEET = """
QMainWindow {
    background-color: #030913;
}
QWidget {
    color: #edf6ff;
    font-family: 'Segoe UI';
    font-size: 10.8pt;
}
QToolTip {
    background-color: #102238;
    color: #f1f7ff;
    border: 1px solid #2b5f90;
    padding: 6px 8px;
}
QFrame#HeaderFrame {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                      stop:0 #071220, stop:0.5 #0c1d33, stop:1 #0a2038);
    border: 1px solid #17395b;
    border-radius: 26px;
}
QFrame#PanelFrame, QLabel#PreviewShell {
    background-color: #071423;
    border: 1px solid #143553;
    border-radius: 18px;
}
QFrame#StatCard {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #0b2038, stop:1 #071423);
    border: 1px solid #1a446b;
    border-radius: 18px;
}
QFrame#StatCard:hover {
    border-color: #35b7ff;
    background-color: #0d2743;
}
QFrame#StatCardAccent {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                      stop:0 #19b8ff, stop:1 #4ce2ff);
    border: none;
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
    min-height: 4px;
    max-height: 4px;
}
QPushButton {
    background-color: #102944;
    border: 1px solid #2a5d8f;
    border-radius: 13px;
    padding: 10px 16px;
    font-weight: 700;
    min-height: 24px;
}
QPushButton:hover { background-color: #16395f; border-color: #49b0ff; }
QPushButton:pressed { background-color: #0d2239; }
QPushButton:disabled { color: #6e8aa8; background-color: #0b1829; border-color: #17304c; }
QPushButton#PrimaryButton { background-color: #11416f; border-color: #58c4ff; }
QPushButton#GhostButton { background-color: #0b1829; border-color: #24496d; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
    background-color: #050f1b;
    border: 1px solid #234a72;
    border-radius: 12px;
    padding: 9px 10px;
    selection-background-color: #1a74b6;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border: 1px solid #39b8ff; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background-color: #0b1829;
    color: #e6f0ff;
    border: 1px solid #234a72;
    selection-background-color: #123862;
}
QTableWidget {
    background-color: #06111d;
    alternate-background-color: #091a2d;
    border: 1px solid #173555;
    border-radius: 16px;
    gridline-color: #13314d;
    selection-background-color: #12355a;
    selection-color: #ffffff;
}
QTableCornerButton::section { background-color: #10243f; border: none; }
QTableWidget::item { padding: 8px; border-bottom: 1px solid #10273e; }
QTableWidget::item:selected { background-color: #12355a; color: #ffffff; }
QHeaderView::section {
    background-color: #10243f;
    color: #7fd9ff;
    border: none;
    border-bottom: 1px solid #1a446c;
    padding: 12px 10px;
    font-weight: 800;
}
QTabWidget::pane {
    border: 1px solid #173555;
    border-radius: 18px;
    background: #09182a;
    top: -1px;
}
QTabBar::tab {
    background: #0d2037;
    padding: 12px 20px;
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
    margin-right: 8px;
    min-width: 92px;
    font-weight: 800;
}
QTabBar::tab:selected { background: #123f6d; color: #89dcff; }
QTabBar::tab:hover { background: #143052; }
QLabel#TitleLabel { font-size: 28pt; font-weight: 900; color: #76d7ff; }
QLabel#SubtitleLabel { color: #9cb6d0; font-size: 11pt; }
QLabel#CardValue { font-size: 26pt; font-weight: 900; color: #ffffff; }
QLabel#CardTitle { color: #90b6dc; font-size: 10pt; font-weight: 700; }
QLabel#SectionLabel { color: #7fd9ff; font-size: 14.5pt; font-weight: 800; }
QLabel#MutedLabel { color: #8caac7; }
QLabel#BadgeLabel {
    background-color: #0f2843;
    border: 1px solid #2f5c8e;
    border-radius: 999px;
    padding: 6px 10px;
    color: #d6efff;
    font-size: 10pt;
    font-weight: 700;
}
QLabel#MicroBadge {
    background-color: #0d2440;
    border: 1px solid #245884;
    border-radius: 10px;
    padding: 7px 10px;
    color: #eaf8ff;
    font-size: 10pt;
    font-weight: 700;
}
QLabel#ChartCanvas {
    border: 1px dashed #2c5c88;
    border-radius: 16px;
    background-color: #04101b;
    padding: 8px;
}
QProgressBar {
    border: 1px solid #24537c;
    border-radius: 12px;
    background-color: #081627;
    text-align: center;
    min-height: 22px;
    font-size: 10.5pt;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                      stop:0 #18b2ff, stop:1 #4de4ff);
    border-radius: 10px;
}
QSplitter::handle { background-color: #173555; width: 4px; height: 4px; }
QScrollBar:vertical {
    background: #071220;
    width: 12px;
    margin: 2px;
    border-radius: 6px;
}
QScrollBar::handle:vertical {
    background: #234f7a;
    min-height: 24px;
    border-radius: 6px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { height: 0; width: 0; }
QScrollBar:horizontal {
    background: #071220;
    height: 12px;
    margin: 2px;
    border-radius: 6px;
}
QScrollBar::handle:horizontal {
    background: #234f7a;
    min-width: 24px;
    border-radius: 6px;
}
QMessageBox { background-color: #081525; }
QMessageBox QLabel { color: #f0f7ff; min-width: 420px; }
QMessageBox QPushButton { min-width: 92px; }
QPlainTextEdit#TerminalView {
    background-color: #030b15;
    color: #dbefff;
    border: 1px solid #23527a;
    border-radius: 14px;
    padding: 14px;
    selection-background-color: #1f75ba;
}
"""
