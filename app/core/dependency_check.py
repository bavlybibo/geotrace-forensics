from __future__ import annotations

"""Offline dependency and runtime readiness checks for GeoTrace.

The checker is intentionally safe: it does not import heavy GUI/science modules,
does not contact the network, and does not execute user-controlled commands.  It
uses importlib metadata/spec discovery plus shutil.which for external binaries.
"""

from dataclasses import asdict, dataclass, field
import importlib.util
import os
from pathlib import Path
import platform
import shutil
import sys
from typing import Any

from .runtime_paths import RUNTIME_DIRS, ensure_project_runtime_dirs, runtime_dir_paths


@dataclass(slots=True)
class DependencyItem:
    name: str
    kind: str
    status: str
    version: str = ""
    detail: str = ""
    required: bool = True
    fix_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DependencyReport:
    app_ready: bool
    required_ok: int
    required_total: int
    optional_ok: int
    optional_total: int
    items: list[DependencyItem] = field(default_factory=list)
    runtime: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_ready": self.app_ready,
            "required_ok": self.required_ok,
            "required_total": self.required_total,
            "optional_ok": self.optional_ok,
            "optional_total": self.optional_total,
            "items": [item.to_dict() for item in self.items],
            "runtime": dict(self.runtime),
            "warnings": list(self.warnings),
        }

    def to_text(self) -> str:
        lines = [
            "GEOTRACE DEPENDENCY CHECK",
            "=" * 78,
            f"Application ready: {'YES' if self.app_ready else 'NO'}",
            f"Required: {self.required_ok}/{self.required_total}",
            f"Optional: {self.optional_ok}/{self.optional_total}",
            "",
            "Runtime:",
        ]
        for key, value in self.runtime.items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "Checks:"])
        for item in self.items:
            badge = "OK" if item.status == "ok" else "WARN" if item.status == "warning" else "MISS"
            req = "required" if item.required else "optional"
            version = f" ({item.version})" if item.version else ""
            lines.append(f"- [{badge}] {item.name}{version} — {req} — {item.detail}")
            if item.fix_hint:
                lines.append(f"  Fix: {item.fix_hint}")
        if self.warnings:
            lines.extend(["", "Warnings:"])
            lines.extend(f"- {warning}" for warning in self.warnings)
        return "\n".join(lines)


_MODULES: tuple[tuple[str, str, bool, str], ...] = (
    ("PyQt5", "PyQt5", True, "pip install -r requirements.txt"),
    ("Pillow", "PIL", True, "pip install -r requirements.txt"),
    ("numpy", "numpy", True, "pip install -r requirements.txt"),
    ("matplotlib", "matplotlib", True, "pip install -r requirements.txt"),
    ("reportlab", "reportlab", True, "pip install -r requirements.txt"),
    ("folium", "folium", False, "pip install -r requirements.txt"),
    ("exifread", "exifread", False, "pip install -r requirements.txt"),
    ("pytesseract", "pytesseract", False, "pip install -r requirements.txt"),
    ("pillow-heif", "pillow_heif", False, "pip install -r requirements.txt"),

    # P0+ forensic/geo precision stack
    ("PyExifTool", "exiftool", False, "setup_recommended_stack_windows.bat or pip install -r requirements-forensics.txt"),
    ("zxing-cpp", "zxingcpp", False, "setup_recommended_stack_windows.bat or pip install -r requirements-forensics.txt"),
    ("ImageHash", "imagehash", False, "setup_recommended_stack_windows.bat or pip install -r requirements-forensics.txt"),
    ("timezonefinder", "timezonefinder", False, "setup_recommended_stack_windows.bat or pip install -r requirements-forensics.txt"),
    ("pycountry", "pycountry", False, "setup_recommended_stack_windows.bat or pip install -r requirements-forensics.txt"),
    ("DuckDB", "duckdb", False, "setup_recommended_stack_windows.bat or pip install -r requirements-forensics.txt"),

    # P0 safe optional stack
    ("QtAwesome", "qtawesome", False, "setup_recommended_stack_windows.bat or pip install -r requirements-ui.txt"),
    ("PyQtGraph", "pyqtgraph", False, "setup_recommended_stack_windows.bat or pip install -r requirements-ui.txt"),
    ("RapidFuzz", "rapidfuzz", False, "setup_recommended_stack_windows.bat or pip install -r requirements-geo.txt"),
    ("geopy", "geopy", False, "setup_recommended_stack_windows.bat or pip install -r requirements-geo.txt"),
    ("shapely", "shapely", False, "setup_recommended_stack_windows.bat or pip install -r requirements-geo.txt"),
    ("h3", "h3", False, "setup_recommended_stack_windows.bat or pip install -r requirements-geo.txt"),

    # P1 heavy optional local AI stack
    ("opencv-python", "cv2", False, "pip install -r requirements-ai.txt"),
    ("EasyOCR", "easyocr", False, "pip install -r requirements-ai.txt"),
    ("ONNX Runtime", "onnxruntime", False, "pip install -r requirements-ai.txt"),
    ("SentenceTransformers", "sentence_transformers", False, "pip install -r requirements-ai.txt"),
    ("OpenCLIP", "open_clip", False, "pip install -r requirements-ai.txt"),
    ("Ultralytics YOLO", "ultralytics", False, "pip install -r requirements-ai-heavy.txt"),
    ("PaddleOCR", "paddleocr", False, "pip install -r requirements-ai-heavy.txt"),
    ("PaddlePaddle", "paddle", False, "pip install -r requirements-ai-heavy.txt"),

    # P2 online OSINT helpers
    ("requests", "requests", False, "pip install -r requirements-osint.txt"),
    ("requests-cache", "requests_cache", False, "setup_recommended_stack_windows.bat or pip install -r requirements-osint.txt"),

    ("pytest", "pytest", False, "pip install -r requirements-dev.txt"),
    ("pyinstaller", "PyInstaller", False, "pip install -r requirements-dev.txt"),
)

_BINARIES: tuple[tuple[str, str, bool, str], ...] = (
    ("Tesseract OCR", "tesseract", False, "Install Tesseract and add it to PATH, or keep OCR mode quick/off."),
    ("ExifTool binary", "exiftool", False, "Install ExifTool, place exiftool.exe in tools\\bin\\exiftool, or set GEOTRACE_EXIFTOOL_CMD."),
)


def _module_status(package_name: str, import_name: str, required: bool, fix_hint: str) -> DependencyItem:
    spec = importlib.util.find_spec(import_name)
    if spec is None:
        return DependencyItem(
            package_name,
            "python-module",
            "missing",
            detail=f"Python import '{import_name}' is not available.",
            required=required,
            fix_hint=fix_hint,
        )
    return DependencyItem(
        package_name,
        "python-module",
        "ok",
        version="discoverable",
        detail=f"Import '{import_name}' is discoverable without importing the module.",
        required=required,
        fix_hint="",
    )


def _binary_status(label: str, executable: str, required: bool, fix_hint: str) -> DependencyItem:
    path = shutil.which(executable)
    if not path:
        return DependencyItem(label, "external-binary", "missing", detail=f"'{executable}' not found on PATH.", required=required, fix_hint=fix_hint)
    return DependencyItem(label, "external-binary", "ok", version="found", detail=path, required=required)


def _exiftool_binary_status(root: Path, required: bool, fix_hint: str) -> DependencyItem:
    try:
        from .forensics.exiftool_bridge import resolve_exiftool_binary
        path = resolve_exiftool_binary(root)
    except Exception:
        path = ""
    if not path:
        return DependencyItem("ExifTool binary", "external-binary", "missing", detail="ExifTool not found in GEOTRACE_EXIFTOOL_CMD, tools/bin/exiftool, or PATH.", required=required, fix_hint=fix_hint)
    return DependencyItem("ExifTool binary", "external-binary", "ok", version="found", detail=path, required=required)


def run_dependency_check(project_root: Path | str | None = None) -> DependencyReport:
    root = Path(project_root) if project_root is not None else Path.cwd()
    items: list[DependencyItem] = []
    for package_name, import_name, required, fix_hint in _MODULES:
        items.append(_module_status(package_name, import_name, required, fix_hint))
    for label, executable, required, fix_hint in _BINARIES:
        if label == "ExifTool binary":
            items.append(_exiftool_binary_status(root, required, fix_hint))
        else:
            items.append(_binary_status(label, executable, required, fix_hint))

    runtime_dirs = runtime_dir_paths(root)
    warnings: list[str] = []
    for folder in runtime_dirs:
        if not folder.exists():
            warnings.append(f"Runtime folder missing and will be created on first run: {folder.name}")

    required = [item for item in items if item.required]
    optional = [item for item in items if not item.required]
    required_ok = sum(1 for item in required if item.status == "ok")
    optional_ok = sum(1 for item in optional if item.status == "ok")
    py_ok = sys.version_info >= (3, 10)
    if not py_ok:
        warnings.append("Python 3.10+ is recommended for PyQt5/PyInstaller compatibility.")
    if sys.version_info >= (3, 14):
        warnings.append("Python 3.14 detected: keep AI-heavy packages separate. If heavy AI install fails, use setup_recommended_stack_windows.bat and keep local AI optional.")

    raw_geo = root / "data" / "geo" / "raw"
    generated_geo = root / "data" / "osint" / "generated_geocoder_index.json"
    primary_geo_names = ("cities1000", "cities5000", "cities15000", "allCountries")
    primary_geo_present = any((raw_geo / f"{name}.zip").exists() or (raw_geo / f"{name}.txt").exists() for name in primary_geo_names)
    if not primary_geo_present:
        warnings.append("GeoNames primary dataset missing. Put cities1000.zip or cities15000.zip in data/geo/raw, then run import_project_geo_data.bat.")
    elif not generated_geo.exists():
        warnings.append("GeoNames source detected but generated index is missing. Run import_project_geo_data.bat before expecting large offline city matching.")

    local_vision_command = os.environ.get("GEOTRACE_LOCAL_VISION_COMMAND", "").strip()
    local_vision_model = os.environ.get("GEOTRACE_LOCAL_VISION_MODEL", "").strip()
    if local_vision_command and any(token in local_vision_command for token in ["&&", "|", ";", ">", "<"]):
        warnings.append("Local vision command contains shell-control characters; GeoTrace will run it with shell=False, but review the command anyway.")

    runtime = {
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "project_root": str(root),
        "local_vision_model": local_vision_model or "not configured",
        "local_vision_command": "configured" if local_vision_command else "not configured",
        "ocr_mode": os.environ.get("GEOTRACE_OCR_MODE", "quick"),
        "log_privacy": os.environ.get("GEOTRACE_LOG_PRIVACY", "redacted"),
        "online_map_lookup": "enabled" if os.environ.get("GEOTRACE_ONLINE_MAP_LOOKUP", "0").strip().lower() in {"1", "true", "yes", "on"} else "disabled/privacy-first",
        "online_osint": "enabled" if os.environ.get("GEOTRACE_OSINT_ONLINE", "0").strip().lower() in {"1", "true", "yes", "on"} else "disabled/privacy-first",
        "mapillary_token": "configured" if os.environ.get("GEOTRACE_MAPILLARY_TOKEN", "").strip() else "not configured",
        "exiftool_cmd": "configured" if os.environ.get("GEOTRACE_EXIFTOOL_CMD", "").strip() else "auto-detect",
        "yolo_enabled": "enabled" if os.environ.get("GEOTRACE_YOLO_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"} else "disabled",
        "yolo_model": os.environ.get("GEOTRACE_YOLO_MODEL", "").strip() or "not configured",
    }
    return DependencyReport(
        app_ready=(required_ok == len(required) and py_ok),
        required_ok=required_ok,
        required_total=len(required),
        optional_ok=optional_ok,
        optional_total=len(optional),
        items=items,
        runtime=runtime,
        warnings=warnings,
    )


def ensure_runtime_folders(project_root: Path | str) -> list[str]:
    root = Path(project_root)
    created: list[str] = []
    return ensure_project_runtime_dirs(root)
