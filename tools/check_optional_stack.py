#!/usr/bin/env python3
from __future__ import annotations

"""Check GeoTrace optional dependency groups without importing heavy modules.

This is safe to run after setup. It only checks whether modules are discoverable
and whether local GeoNames data has been imported. Missing optional packages do
not mean the app is broken.
"""

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

GROUPS = {
    "UI": {
        "install": "pip install -r requirements-ui.txt",
        "modules": {"qtawesome": "qtawesome", "pyqtgraph": "pyqtgraph"},
    },
    "Geo": {
        "install": "pip install -r requirements-geo.txt",
        "modules": {"rapidfuzz": "rapidfuzz", "geopy": "geopy", "shapely": "shapely", "h3": "h3"},
    },
    "Forensics": {
        "install": "pip install -r requirements-forensics.txt",
        "modules": {
            "PyExifTool": "exiftool",
            "zxing-cpp": "zxingcpp",
            "ImageHash": "imagehash",
            "timezonefinder": "timezonefinder",
            "pycountry": "pycountry",
            "DuckDB": "duckdb",
        },
    },
    "AI-heavy": {
        "install": "pip install -r requirements-ai.txt  (heavy/optional)",
        "modules": {
            "opencv-python": "cv2",
            "easyocr": "easyocr",
            "onnxruntime": "onnxruntime",
            "sentence-transformers": "sentence_transformers",
            "open-clip-torch": "open_clip",
            "ultralytics": "ultralytics",
            "paddleocr": "paddleocr",
            "paddlepaddle": "paddle",
        },
    },
    "OSINT-online/cache": {
        "install": "pip install -r requirements-osint.txt",
        "modules": {"requests": "requests", "requests-cache": "requests_cache"},
    },
}


def module_ok(import_name: str) -> bool:
    return importlib.util.find_spec(import_name) is not None


def _geodata_candidates(raw_dir: Path) -> list[Path]:
    bases = ["cities1000", "cities5000", "cities15000", "allCountries"]
    candidates: list[Path] = []
    for base in bases:
        candidates.append(raw_dir / f"{base}.txt")
        candidates.append(raw_dir / f"{base}.zip")
    return candidates


def main() -> int:
    print("GEOTRACE OPTIONAL STACK CHECK")
    print("=" * 72)
    print(f"Python: {sys.version.split()[0]} | {sys.executable}")
    print(f"Project: {ROOT}")
    missing_total = 0
    recommended_missing = 0
    for group, spec in GROUPS.items():
        modules = spec["modules"]
        ok = 0
        print(f"\n[{group}]")
        for package, import_name in modules.items():
            status = "OK" if module_ok(import_name) else "MISSING"
            if status == "OK":
                ok += 1
            else:
                missing_total += 1
                if group != "AI-heavy":
                    recommended_missing += 1
            print(f"- {package:<24} import={import_name:<24} {status}")
        print(f"  -> {ok}/{len(modules)} installed")
        if ok < len(modules):
            print(f"  install hint: {spec['install']}")

    raw_dir = ROOT / "data" / "geo" / "raw"
    generated = ROOT / "data" / "osint" / "generated_geocoder_index.json"
    primary_present = any(p.exists() for p in _geodata_candidates(raw_dir))
    print("\n[GeoNames data]")
    print(f"- raw folder:          {'OK' if raw_dir.exists() else 'missing'}")
    print(f"- primary source:      {'OK' if primary_present else 'missing'}  (cities1000/5000/15000/allCountries txt/zip)")
    print(f"- generated index:     {'OK' if generated.exists() else 'missing'}")
    print("\nRecommended next step:")
    if recommended_missing:
        print("- Run setup_recommended_stack_windows.bat")
    elif not primary_present:
        print("- Put cities1000.zip or cities15000.zip in data\\geo\\raw")
    elif not generated.exists():
        print("- Run import_project_geo_data.bat")
    elif missing_total:
        print("- Core + recommended stack looks ready. AI-heavy is optional; install only if needed.")
    else:
        print("- All optional groups checked here are installed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
