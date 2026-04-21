APP_STYLESHEET = """
QMainWindow {
    background-color: #06101b;
}
QWidget {
    color: #e6f0ff;
    font-family: 'Segoe UI';
    font-size: 11pt;
}
QToolTip {
    background-color: #12243a;
    color: #eaf4ff;
    border: 1px solid #2f5c8e;
    padding: 6px 8px;
}
QFrame#HeaderFrame {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                      stop:0 #0a182b, stop:1 #10243f);
    border: 1px solid #173555;
    border-radius: 24px;
}
QFrame#CardAccent, QFrame#PanelFrame {
    background-color: #0c1a2d;
    border: 1px solid #173555;
    border-radius: 18px;
}
QFrame#StatCard {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #0f2440, stop:1 #0a1a2e);
    border: 1px solid #1d4b76;
    border-radius: 18px;
}
QFrame#StatCardAccent {
    background-color: #26c6ff;
    border: none;
    border-top-left-radius: 17px;
    border-top-right-radius: 17px;
    min-height: 4px;
    max-height: 4px;
}
QPushButton {
    background-color: #102846;
    border: 1px solid #2a5d8f;
    border-radius: 12px;
    padding: 10px 16px;
    font-weight: 700;
    min-height: 22px;
}
QPushButton:hover {
    background-color: #16365d;
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
    background-color: #0f3560;
    border-color: #3f93d4;
}
QPushButton#DangerSoftButton {
    background-color: #2a1820;
    border-color: #7a3b4f;
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
    background-color: #071525;
    border: 1px solid #234a72;
    border-radius: 12px;
    padding: 8px 10px;
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
    background-color: #071525;
    alternate-background-color: #0a1a2e;
    border: 1px solid #173555;
    border-radius: 14px;
    gridline-color: #15304b;
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
    border-radius: 16px;
    background: #0c1a2d;
    top: -1px;
}
QTabBar::tab {
    background: #0d2037;
    padding: 12px 16px;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    margin-right: 6px;
    min-width: 92px;
    font-weight: 700;
}
QTabBar::tab:selected {
    background: #12365f;
    color: #7fd9ff;
}
QTabBar::tab:hover {
    background: #113052;
}
QLabel#TitleLabel {
    font-size: 26pt;
    font-weight: 900;
    color: #76d7ff;
}
QLabel#SubtitleLabel {
    color: #97b2cd;
    font-size: 11pt;
}
QLabel#CardValue {
    font-size: 22pt;
    font-weight: 900;
    color: #ffffff;
}
QLabel#CardTitle {
    color: #8cb6dc;
    font-size: 10pt;
    font-weight: 700;
}
QLabel#SectionLabel {
    color: #7fd9ff;
    font-size: 14pt;
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
    color: #ccecff;
    font-size: 10pt;
    font-weight: 700;
}
QProgressBar {
    border: 1px solid #24537c;
    border-radius: 10px;
    background-color: #081627;
    text-align: center;
    min-height: 18px;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                      stop:0 #18b2ff, stop:1 #4de4ff);
    border-radius: 8px;
}
QSplitter::handle {
    background-color: #173555;
    width: 3px;
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
    background-color: #0b1829;
}
QMessageBox QLabel {
    color: #eaf4ff;
    min-width: 320px;
}
QMessageBox QPushButton {
    min-width: 92px;
}
"""
