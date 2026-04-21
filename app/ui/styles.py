APP_STYLESHEET = """
QMainWindow {
    background-color: #050c16;
}
QWidget {
    color: #eaf4ff;
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
                                      stop:0 #091829, stop:0.5 #10243f, stop:1 #0b1f35);
    border: 1px solid #173555;
    border-radius: 26px;
}
QFrame#PanelFrame, QLabel#PreviewShell {
    background-color: #0a182b;
    border: 1px solid #173555;
    border-radius: 18px;
}
QFrame#StatCard {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #0e213a, stop:1 #0a182b);
    border: 1px solid #1c4771;
    border-radius: 18px;
}
QFrame#StatCardAccent {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                      stop:0 #18b2ff, stop:1 #4de4ff);
    border: none;
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
    min-height: 4px;
    max-height: 4px;
}
QPushButton {
    background-color: #0f2843;
    border: 1px solid #2a5d8f;
    border-radius: 13px;
    padding: 10px 16px;
    font-weight: 700;
    min-height: 24px;
}
QPushButton:hover {
    background-color: #15365c;
    border-color: #3a79b4;
}
QPushButton:pressed {
    background-color: #0b1f37;
}
QPushButton:disabled {
    color: #6e8aa8;
    background-color: #0b1829;
    border-color: #17304c;
}
QPushButton#PrimaryButton {
    background-color: #0e3865;
    border-color: #49b0ff;
}
QPushButton#GhostButton {
    background-color: #0b1829;
    border-color: #24496d;
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
    background-color: #061220;
    border: 1px solid #234a72;
    border-radius: 12px;
    padding: 9px 10px;
    selection-background-color: #1a74b6;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #39b8ff;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    background-color: #0b1829;
    color: #e6f0ff;
    border: 1px solid #234a72;
    selection-background-color: #123862;
}
QTableWidget {
    background-color: #071321;
    alternate-background-color: #0b1a2d;
    border: 1px solid #173555;
    border-radius: 16px;
    gridline-color: #13314d;
    selection-background-color: #10355f;
    selection-color: #ffffff;
}
QTableCornerButton::section {
    background-color: #10243f;
    border: none;
}
QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #10273e;
}
QTableWidget::item:selected {
    background-color: #12355a;
    color: #ffffff;
}
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
    background: #0b1a2d;
    top: -1px;
}
QTabBar::tab {
    background: #0d2037;
    padding: 12px 18px;
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
    margin-right: 8px;
    min-width: 84px;
    font-weight: 800;
}
QTabBar::tab:selected {
    background: #113d69;
    color: #89dcff;
}
QTabBar::tab:hover {
    background: #123052;
}
QLabel#TitleLabel {
    font-size: 27pt;
    font-weight: 900;
    color: #76d7ff;
}
QLabel#SubtitleLabel {
    color: #9cb6d0;
    font-size: 11pt;
}
QLabel#CardValue {
    font-size: 26pt;
    font-weight: 900;
    color: #ffffff;
}
QLabel#CardTitle {
    color: #90b6dc;
    font-size: 10pt;
    font-weight: 700;
}
QLabel#SectionLabel {
    color: #7fd9ff;
    font-size: 14.5pt;
    font-weight: 800;
}
QLabel#MutedLabel {
    color: #8caac7;
}
QLabel#BadgeLabel {
    background-color: #0f2843;
    border: 1px solid #2f5c8e;
    border-radius: 999px;
    padding: 6px 10px;
    color: #d6efff;
    font-size: 10pt;
    font-weight: 700;
}
QLabel#ChartCanvas {
    border: 1px dashed #2c5c88;
    border-radius: 16px;
    background-color: #081524;
    padding: 8px;
}
QProgressBar {
    border: 1px solid #24537c;
    border-radius: 12px;
    background-color: #081627;
    text-align: center;
    min-height: 20px;
    font-size: 10.5pt;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                      stop:0 #18b2ff, stop:1 #4de4ff);
    border-radius: 10px;
}
QSplitter::handle {
    background-color: #173555;
    width: 4px;
}
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
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QMessageBox {
    background-color: #081525;
}
QMessageBox QLabel {
    color: #f0f7ff;
    min-width: 360px;
}
QMessageBox QPushButton {
    min-width: 92px;
}
"""
