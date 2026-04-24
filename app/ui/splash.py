from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt5.QtWidgets import QApplication, QSplashScreen


class GeoTraceSplash(QSplashScreen):
    """Startup splash screen kept separate from the application entry point."""

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
    return GeoTraceSplash(pixmap)
