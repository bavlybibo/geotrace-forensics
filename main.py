import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QSplashScreen

from app.ui.main_window import GeoTraceMainWindow


def build_splash() -> QSplashScreen:
    pixmap = QPixmap(720, 360)
    pixmap.fill(Qt.transparent)
    splash = QSplashScreen(pixmap)
    splash.setStyleSheet(
        """
        QSplashScreen {
            background: #07111f;
            border: 1px solid #16304f;
            border-radius: 18px;
        }
        """
    )
    splash.showMessage(
        "GeoTrace Forensics\nInitializing forensic modules...",
        alignment=Qt.AlignCenter,
        color=Qt.white,
    )
    splash.setFont(QFont("Segoe UI", 16, QFont.Bold))
    return splash


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("GeoTrace Forensics")
    app.setOrganizationName("Cyber Forensics Team")

    splash = build_splash()
    splash.show()
    app.processEvents()

    window = GeoTraceMainWindow(project_root=Path(__file__).resolve().parent)
    window.show()
    splash.finish(window)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
