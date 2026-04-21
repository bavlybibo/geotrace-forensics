import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import QApplication, QSplashScreen

from app.ui.main_window import GeoTraceMainWindow
from app.config import APP_NAME, APP_ORGANIZATION


class GeoTraceSplash(QSplashScreen):
    def __init__(self, pixmap: QPixmap) -> None:
        super().__init__(pixmap)
        self._message = "Initializing forensic modules..."
        self._progress = 0
        self.setWindowFlag(Qt.FramelessWindowHint)

    def set_status(self, message: str, progress: int) -> None:
        self._message = message
        self._progress = progress
        self.repaint()
        QApplication.processEvents()

    def drawContents(self, painter: QPainter) -> None:  # type: ignore[override]
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor("#dff5ff"))
        painter.setFont(QFont("Segoe UI", 16, QFont.Bold))
        painter.drawText(86, 562, self._message)
        painter.setPen(QColor("#8fb2cf"))
        painter.setFont(QFont("Consolas", 11))
        painter.drawText(86, 595, f"Boot sequence {self._progress}%")
        painter.setBrush(QColor("#0b1d31"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(86, 610, 1024, 18, 9, 9)
        painter.setBrush(QColor("#20c2ff"))
        painter.drawRoundedRect(86, 610, int(1024 * max(0, min(self._progress, 100)) / 100), 18, 9, 9)


def build_splash(project_root: Path) -> GeoTraceSplash:
    splash_path = project_root / "assets" / "splash.png"
    pixmap = QPixmap(str(splash_path))
    if pixmap.isNull():
        pixmap = QPixmap(1200, 640)
        pixmap.fill(QColor("#07111f"))
    splash = GeoTraceSplash(pixmap)
    return splash


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANIZATION)

    project_root = Path(__file__).resolve().parent
    icon_path = project_root / "assets" / "app_icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    splash = build_splash(project_root)
    splash.show()
    splash.set_status("Loading forensic UI shell...", 18)

    splash.set_status("Preparing evidence database and custody log...", 42)
    window = GeoTraceMainWindow(project_root=project_root)
    splash.set_status("Binding analysis modules and dashboards...", 76)
    window.show()
    splash.set_status("GeoTrace ready.", 100)
    splash.finish(window)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
