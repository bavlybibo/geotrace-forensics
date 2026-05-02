from __future__ import annotations

"""GeoTrace Forensics X application entry point."""

import os
import sys
from pathlib import Path


def _prepare_runtime(project_root: Path) -> None:
    """Create local runtime folders before Qt starts."""
    try:
        from app.core.runtime_paths import ensure_project_runtime_dirs

        ensure_project_runtime_dirs(project_root)
    except Exception:
        # Startup must remain resilient even if the package import path is unusual.
        for name in ("case_data", "cases", "exports", "logs", "cache", "reports", "tmp", "data/validation", "data/validation_cases"):
            (project_root / name).mkdir(parents=True, exist_ok=True)
    # Safe OCR defaults. Analysts can override from Settings or environment variables.
    os.environ.setdefault("GEOTRACE_OCR_MODE", "quick")
    os.environ.setdefault("GEOTRACE_OCR_TIMEOUT", "0.8")
    os.environ.setdefault("GEOTRACE_OCR_GLOBAL_TIMEOUT", "5.0")
    os.environ.setdefault("GEOTRACE_OCR_MAX_CALLS", "4")
    os.environ.setdefault("GEOTRACE_LOG_PRIVACY", "redacted")


def main() -> int:
    project_root = Path(__file__).resolve().parent
    _prepare_runtime(project_root)

    try:
        from PyQt5.QtWidgets import QApplication
        from app.ui.main_window import GeoTraceMainWindow
    except ImportError as exc:
        print("GeoTrace could not start because a required dependency is missing.", file=sys.stderr)
        print("Run setup_windows.bat or: python -m pip install -r requirements.txt", file=sys.stderr)
        print(f"Import error: {exc}", file=sys.stderr)
        return 2

    app = QApplication(sys.argv)
    app.setApplicationName("GeoTrace Forensics X")
    window = GeoTraceMainWindow(project_root)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
