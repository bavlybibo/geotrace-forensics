APP_STYLESHEET = """
QMainWindow {
    background-color: #03101b;
}
QWidget {
    color: #ebf5ff;
    font-family: 'Segoe UI';
    font-size: 10pt;
}
QToolTip {
    background-color: #10233a;
    color: #eef9ff;
    border: 1px solid #2b5e8d;
    padding: 6px 8px;
}
QFrame#HeaderFrame {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                      stop:0 #071323, stop:0.55 #0c1a31, stop:1 #0f2340);
    border: 1px solid #163455;
    border-radius: 22px;
}
QFrame#PanelFrame, QFrame#CompactPanel, QFrame#SecondaryPanel {
    background-color: #071421;
    border: 1px solid #17324c;
    border-radius: 18px;
}
QFrame#CompactPanel {
    border-radius: 16px;
    background-color: #081525;
}
QFrame#SecondaryPanel {
    background-color: #06101c;
}
QFrame#StatCard {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #0b192e, stop:1 #091423);
    border: 1px solid #16324f;
    border-radius: 18px;
}
QFrame#StatCard:hover {
    border-color: #28c6ff;
    background-color: #0b1d34;
}
QFrame#StatCardAccent {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                      stop:0 #15b8ff, stop:1 #70e5ff);
    border: none;
    border-radius: 999px;
    min-height: 4px;
    max-height: 4px;
}
QPushButton {
    background-color: #0c2138;
    border: 1px solid #244a73;
    border-radius: 14px;
    padding: 10px 16px;
    color: #f4fbff;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #12304f;
    border-color: #39c9ff;
}
QPushButton:pressed {
    background-color: #0a1a2d;
}
QPushButton:disabled {
    background-color: #07111c;
    color: #63809e;
    border-color: #17314c;
}
QPushButton#PrimaryButton {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                      stop:0 #129af2, stop:1 #2ed2ff);
    color: #03111d;
    border: 1px solid #73e6ff;
    font-weight: 800;
}
QPushButton#PrimaryButton:hover {
    background-color: #4fddff;
}
QPushButton#GhostButton {
    background-color: transparent;
    color: #bdeeff;
}
QPushButton#SmallGhostButton {
    background-color: transparent;
    border: 1px solid #1d3e61;
    border-radius: 12px;
    padding: 6px 10px;
    color: #bdeeff;
    font-size: 9.5pt;
}
QLineEdit, QComboBox, QTextEdit, QPlainTextEdit {
    background-color: #040c16;
    border: 1px solid #173652;
    border-radius: 14px;
    padding: 10px 12px;
    color: #eef7ff;
    selection-background-color: #1387cc;
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #33cbff;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #071321;
    border: 1px solid #1d4369;
    selection-background-color: #143d63;
    color: #edf6ff;
}
QLabel#TitleLabel {
    font-size: 22pt;
    font-weight: 900;
    color: #78d9ff;
}
QLabel#SubtitleLabel {
    color: #c2d9ec;
    font-size: 10pt;
}
QLabel#SectionLabel {
    font-size: 12pt;
    font-weight: 800;
    color: #8ce2ff;
}
QLabel#SectionMetaLabel {
    color: #8fb5d1;
    font-size: 9.4pt;
}
QLabel#MutedLabel {
    color: #89a8c0;
    font-size: 9.4pt;
}
QLabel#BadgeLabel, QLabel#MicroBadge, QLabel#InfoBadge {
    background-color: rgba(16, 34, 56, 0.84);
    border: 1px solid #23486f;
    border-radius: 12px;
    padding: 7px 10px;
    color: #dff6ff;
    font-size: 9.5pt;
}
QLabel#RiskBadgeHigh {
    background-color: rgba(64, 21, 31, 0.9);
    border: 1px solid #8b485a;
    color: #ffb4c1;
    border-radius: 12px;
    padding: 7px 10px;
    font-weight: 700;
}
QLabel#RiskBadgeMedium {
    background-color: rgba(63, 48, 18, 0.9);
    border: 1px solid #856a31;
    color: #ffd789;
    border-radius: 12px;
    padding: 7px 10px;
    font-weight: 700;
}
QLabel#RiskBadgeLow {
    background-color: rgba(17, 55, 35, 0.9);
    border: 1px solid #327450;
    color: #a9f1cb;
    border-radius: 12px;
    padding: 7px 10px;
    font-weight: 700;
}
QLabel#CardValue {
    font-size: 25pt;
    font-weight: 900;
    color: #ffffff;
}
QLabel#CardTitle {
    color: #dcefff;
    font-size: 10.3pt;
    font-weight: 700;
}
QLabel#CardSubtext {
    color: #8dafca;
    font-size: 9.2pt;
}
QLabel#CardChip {
    color: #81d8ff;
    font-size: 8.7pt;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 999px;
    background-color: rgba(15, 44, 70, 0.88);
    border: 1px solid #275881;
}
QLabel#PreviewMetaTitle {
    color: #89a8c0;
    font-size: 9pt;
    font-weight: 600;
}
QLabel#PreviewMetaValue {
    color: #f2f8ff;
    font-size: 10pt;
    font-weight: 700;
}
QLabel#HeroValue {
    font-size: 13pt;
    font-weight: 800;
    color: #ffffff;
}
QTextEdit#NarrativeView, QPlainTextEdit#TerminalView {
    background-color: #040d18;
    border: 1px solid #16304c;
    border-radius: 14px;
    padding: 12px;
}
QTextEdit#NarrativeView {
    color: #e9f5ff;
    line-height: 1.45;
}
QPlainTextEdit#TerminalView {
    color: #bfeeff;
    background-color: #04101b;
}
QTableWidget {
    background-color: #040c16;
    border: 1px solid #17304b;
    border-radius: 16px;
    gridline-color: transparent;
    alternate-background-color: rgba(12, 24, 38, 0.72);
    selection-background-color: rgba(22, 110, 165, 0.38);
    selection-color: #ffffff;
}
QHeaderView::section {
    background-color: #0d2138;
    color: #9ee7ff;
    border: none;
    border-bottom: 1px solid #173652;
    padding: 10px 8px;
    font-weight: 800;
}
QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid rgba(19, 48, 76, 0.45);
}
QTableCornerButton::section {
    background-color: #0d2138;
    border: none;
}
QTabWidget::pane {
    border: 1px solid #17314c;
    border-radius: 16px;
    top: -1px;
    background: #06111d;
}
QTabBar::tab {
    background: transparent;
    border: 1px solid #173652;
    border-bottom: none;
    padding: 10px 16px;
    margin-right: 8px;
    min-width: 90px;
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
    color: #a9cae0;
    font-weight: 700;
}
QTabBar::tab:selected {
    background: #0b2238;
    color: #8de2ff;
    border-color: #2a5f8f;
}
QTabBar::tab:hover {
    color: #dff6ff;
}
QProgressBar {
    background-color: #050c16;
    border: 1px solid #17304b;
    border-radius: 999px;
    text-align: center;
    color: #e7f7ff;
    min-height: 20px;
}
QProgressBar::chunk {
    border-radius: 999px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #12aaff, stop:1 #66ecff);
}
QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 6px 2px 6px 2px;
}
QScrollBar::handle:vertical {
    background: #173652;
    border-radius: 6px;
    min-height: 24px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
    border: none;
}
QScrollBar:horizontal {
    background: transparent;
    height: 12px;
    margin: 2px 6px 2px 6px;
}
QScrollBar::handle:horizontal {
    background: #173652;
    border-radius: 6px;
    min-width: 24px;
}
QSplitter::handle {
    background-color: #0a1a2b;
}
QSplitter::handle:horizontal {
    width: 6px;
}
QSplitter::handle:vertical {
    height: 6px;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
"""
