from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from app.config import APP_NAME, APP_ORGANIZATION
from app.ui.main_window import GeoTraceMainWindow
from app.ui.splash import build_splash


def configure_application(project_root: Path) -> QApplication:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANIZATION)

    icon_path = project_root / "assets" / "app_icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    return app


def main() -> None:
    app = configure_application(PROJECT_ROOT)
    splash = build_splash(PROJECT_ROOT)
    splash.show()
    splash.set_status("Loading forensic UI shell...", 18)

    splash.set_status("Preparing evidence database and custody log...", 42)
    window = GeoTraceMainWindow(project_root=PROJECT_ROOT)
    splash.set_status("Binding analysis modules and dashboards...", 76)
    window.show()
    splash.set_status("GeoTrace ready.", 100)
    splash.finish(window)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
