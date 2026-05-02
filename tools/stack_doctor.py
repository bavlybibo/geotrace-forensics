#!/usr/bin/env python3
from __future__ import annotations

"""Human-readable setup doctor for GeoTrace optional stacks."""

import importlib.util
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GROUPS = {
    "recommended_ui": {
        "install": "python -m pip install -r requirements-ui.txt",
        "modules": {"qtawesome": "qtawesome", "pyqtgraph": "pyqtgraph"},
    },
    "recommended_geo": {
        "install": "python -m pip install -r requirements-geo.txt",
        "modules": {"rapidfuzz": "rapidfuzz", "geopy": "geopy", "shapely": "shapely", "h3": "h3"},
    },
    "recommended_forensics": {
        "install": "python -m pip install -r requirements-forensics.txt",
        "modules": {
            "PyExifTool": "exiftool",
            "zxing-cpp": "zxingcpp",
            "ImageHash": "imagehash",
            "timezonefinder": "timezonefinder",
            "pycountry": "pycountry",
            "DuckDB": "duckdb",
        },
    },
    "recommended_osint_cache": {
        "install": "python -m pip install -r requirements-osint.txt",
        "modules": {"requests": "requests", "requests-cache": "requests_cache"},
    },
    "ai_heavy_optional": {
        "install": "python -m pip install -r requirements-ai.txt",
        "modules": {
            "opencv-python": "cv2",
            "EasyOCR": "easyocr",
            "ONNX Runtime": "onnxruntime",
            "SentenceTransformers": "sentence_transformers",
            "OpenCLIP": "open_clip",
            "Ultralytics YOLO": "ultralytics",
            "PaddleOCR": "paddleocr",
            "PaddlePaddle": "paddle",
        },
    },
}


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def status_line(ok: bool) -> str:
    return "OK" if ok else "MISSING"


def main() -> int:
    print("GEOTRACE STACK DOCTOR")
    print("=" * 72)
    print(f"Project root: {ROOT}")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    print()

    recommended_missing: list[str] = []
    ai_missing: list[str] = []
    for group_name, spec in GROUPS.items():
        modules = spec["modules"]
        ok_count = 0
        print(f"[{group_name}]")
        for package, import_name in modules.items():
            ok = has_module(import_name)
            ok_count += int(ok)
            if not ok:
                if group_name.startswith("ai_"):
                    ai_missing.append(package)
                else:
                    recommended_missing.append(package)
            print(f"- {package:<24} import={import_name:<24} {status_line(ok)}")
        print(f"  -> {ok_count}/{len(modules)} installed")
        if ok_count != len(modules):
            print(f"  install: {spec['install']}")
        print()

    print("[external_binaries]")
    for label, exe in [("Tesseract OCR", "tesseract"), ("ExifTool binary", "exiftool")]:
        found = shutil.which(exe)
        print(f"- {label:<24} {status_line(bool(found))}" + (f" -> {found}" if found else ""))
    print()

    raw = ROOT / "data" / "geo" / "raw"
    primary_names = ["cities1000", "cities5000", "cities15000", "allCountries"]
    primary = []
    for base in primary_names:
        primary.extend([raw / f"{base}.zip", raw / f"{base}.txt"])
    generated = ROOT / "data" / "osint" / "generated_geocoder_index.json"
    print("[geodata]")
    print(f"- raw folder: {raw}")
    print(f"- primary source present: {status_line(any(p.exists() for p in primary))}")
    print(f"- generated index: {status_line(generated.exists())}" + (f" ({generated})" if generated.exists() else ""))
    if not any(p.exists() for p in primary):
        print("  next: put cities1000.zip or cities15000.zip in data\\geo\\raw")
    if not generated.exists():
        print("  next: run import_project_geo_data.bat")
    print()

    print("[recommended_next_step]")
    if recommended_missing:
        print("Run: setup_recommended_stack_windows.bat")
    elif not generated.exists():
        print("Add GeoNames data, then run: import_project_geo_data.bat")
    elif ai_missing:
        print("Core + recommended stack is ready. AI-heavy remains optional: setup_ai_stack_windows.bat")
    else:
        print("All checked stacks are installed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
