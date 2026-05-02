from __future__ import annotations

"""System Health report builder for the GeoTrace desktop UI."""

from dataclasses import asdict, dataclass, field
import importlib.util
import json
import os
from pathlib import Path
import re
from typing import Any

from .dependency_check import DependencyReport, run_dependency_check


def _load_module_from_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _detect_local_vision_model(root: Path) -> dict[str, Any]:
    try:
        module = _load_module_from_path("geotrace_local_vision_model", root / "app" / "core" / "vision" / "local_vision_model.py")
        return module.detect_local_vision_model().to_dict()
    except Exception as exc:
        return {"enabled": False, "command_configured": False, "warnings": [f"Local vision status unavailable: {exc}"]}


def _load_local_landmarks(root: Path) -> list[dict[str, Any]]:
    try:
        module = _load_module_from_path("geotrace_local_landmarks", root / "app" / "core" / "osint" / "local_landmarks.py")
        return module.load_local_landmarks()
    except Exception:
        path = root / "data" / "osint" / "local_landmarks.json"
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            rows = data.get("landmarks", data) if isinstance(data, dict) else data
            return [item for item in rows if isinstance(item, dict)] if isinstance(rows, list) else []
        except Exception:
            return []


@dataclass(slots=True)
class HealthSection:
    title: str
    status: str
    summary: str
    details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SystemHealthReport:
    overall_status: str
    score: int
    dependency_report: DependencyReport
    sections: list[HealthSection] = field(default_factory=list)
    security_findings: list[str] = field(default_factory=list)
    p2_readiness: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "score": self.score,
            "dependency_report": self.dependency_report.to_dict(),
            "sections": [section.to_dict() for section in self.sections],
            "security_findings": list(self.security_findings),
            "p2_readiness": dict(self.p2_readiness),
        }

    def to_text(self) -> str:
        lines = [
            "GEOTRACE SYSTEM HEALTH",
            "=" * 78,
            f"Overall: {self.overall_status} ({self.score}/100)",
            "",
        ]
        for section in self.sections:
            lines.append(f"[{section.status}] {section.title}: {section.summary}")
            lines.extend(f"  - {item}" for item in section.details)
            lines.append("")
        lines.append("P2 readiness:")
        for key, value in self.p2_readiness.items():
            lines.append(f"- {key}: {value}")
        if self.security_findings:
            lines.extend(["", "Security hygiene findings:"])
            lines.extend(f"- {item}" for item in self.security_findings)
        lines.extend(["", self.dependency_report.to_text()])
        return "\n".join(lines)


_DANGEROUS_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\beval\s*\(", "Python eval() call"),
    (r"\bexec\s*\(", "Python exec() call"),
    (r"shell\s*=\s*True", "subprocess shell=True"),
    (r"os\.system\s*\(", "os.system() call"),
    (r"pickle\.loads?\s*\(", "pickle load operation"),
    (r"yaml\.load\s*\(", "unsafe yaml.load()"),
)


def _count_json_rows(path: Path, key: str) -> int:
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    if isinstance(data, dict):
        rows = data.get(key) or data.get("places") or data.get("landmarks") or []
    else:
        rows = data
    return len(rows) if isinstance(rows, list) else 0




def _count_geo_aliases(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0, 0
    countries = data.get("countries", []) if isinstance(data, dict) else []
    cities = data.get("cities", []) if isinstance(data, dict) else []
    return (len(countries) if isinstance(countries, list) else 0, len(cities) if isinstance(cities, list) else 0)



def _optional_module_ok(import_name: str) -> bool:
    return importlib.util.find_spec(import_name) is not None


def _raw_geonames_status(root: Path) -> dict[str, Any]:
    raw = root / "data" / "geo" / "raw"
    city_files = [
        raw / "cities1000.zip",
        raw / "cities1000.txt",
        raw / "cities5000.zip",
        raw / "cities5000.txt",
        raw / "cities15000.zip",
        raw / "cities15000.txt",
        raw / "allCountries.zip",
        raw / "allCountries.txt",
    ]
    aux_files = {
        "alternateNamesV2": raw / "alternateNamesV2.zip",
        "countryInfo": raw / "countryInfo.txt",
        "admin1CodesASCII": raw / "admin1CodesASCII.txt",
        "admin2Codes": raw / "admin2Codes.txt",
        "timeZones": raw / "timeZones.txt",
    }
    present_city_files = [path.name for path in city_files if path.exists()]
    present_aux_files = [name for name, path in aux_files.items() if path.exists()]
    return {
        "raw_dir": str(raw),
        "present_city_files": present_city_files,
        "present_aux_files": present_aux_files,
        "cities1000_zip": (raw / "cities1000.zip").exists(),
        "cities15000_zip": (raw / "cities15000.zip").exists(),
        "alternateNamesV2_zip": (raw / "alternateNamesV2.zip").exists(),
        "ready": bool(present_city_files),
        "aux_ready": bool(present_aux_files),
    }


def _scan_security_patterns(project_root: Path) -> list[str]:
    findings: list[str] = []
    for folder_name in ("app", "tools"):
        folder = project_root / folder_name
        if not folder.exists():
            continue
        for path in folder.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern, label in _DANGEROUS_PATTERNS:
                if re.search(pattern, text):
                    rel = path.relative_to(project_root)
                    # Detection-pattern files intentionally contain marker text; flag them as review-only.
                    tone = "review" if "marker" in text[max(0, text.find(pattern) - 80): text.find(pattern) + 120].lower() else "review"
                    findings.append(f"{tone}: {rel} contains pattern '{label}'. Manually confirm it is a detector string, not executable behavior.")
    return sorted(set(findings))[:30]


def build_system_health_report(project_root: Path | str) -> SystemHealthReport:
    root = Path(project_root)
    dep = run_dependency_check(root)
    local_vision = _detect_local_vision_model(root)
    landmarks = _load_local_landmarks(root)
    geocoder_rows = _count_json_rows(root / "data" / "osint" / "local_geocoder_places.json", "places")
    generated_geocoder_rows = _count_json_rows(root / "data" / "osint" / "generated_geocoder_index.json", "places")
    project_geo_source_rows = _count_json_rows(root / "data" / "geo" / "processed" / "places_geonames.json", "places")
    raw_geonames = _raw_geonames_status(root)
    geo_alias_countries, geo_alias_cities = _count_geo_aliases(root / "data" / "osint" / "geo_aliases.json")
    optional_stack = {
        "ui": {"qtawesome": _optional_module_ok("qtawesome"), "pyqtgraph": _optional_module_ok("pyqtgraph")},
        "geo": {"rapidfuzz": _optional_module_ok("rapidfuzz"), "geopy": _optional_module_ok("geopy"), "shapely": _optional_module_ok("shapely"), "h3": _optional_module_ok("h3")},
        "forensics": {"exiftool_py": _optional_module_ok("exiftool"), "zxingcpp": _optional_module_ok("zxingcpp"), "imagehash": _optional_module_ok("imagehash")},
        "geo_plus": {"timezonefinder": _optional_module_ok("timezonefinder"), "pycountry": _optional_module_ok("pycountry"), "duckdb": _optional_module_ok("duckdb")},
        "ai": {"cv2": _optional_module_ok("cv2"), "easyocr": _optional_module_ok("easyocr"), "onnxruntime": _optional_module_ok("onnxruntime"), "sentence_transformers": _optional_module_ok("sentence_transformers"), "open_clip": _optional_module_ok("open_clip"), "ultralytics": _optional_module_ok("ultralytics"), "paddleocr": _optional_module_ok("paddleocr"), "paddlepaddle": _optional_module_ok("paddle")},
        "osint": {"requests": _optional_module_ok("requests"), "requests_cache": _optional_module_ok("requests_cache")},
    }
    validation_template = root / "data" / "validation_ground_truth.real_template.json"
    validation_cases = root / "data" / "validation_cases" / "ground_truth_v12_10_24.json"
    benchmark_tool = root / "tools" / "benchmark_accuracy.py"
    similarity_tool = root / "tools" / "visual_similarity_search.py"
    release_scripts = [root / name for name in ("setup_windows.bat", "run_windows.bat", "make_release.bat", "geotrace_forensics_x.spec")]
    release_ok = all(path.exists() for path in release_scripts)
    tests = list((root / "tests").glob("test_*.py")) if (root / "tests").exists() else []

    p2 = {
        "local_vision_model": "command-ready" if local_vision.get("command_configured") else "adapter-ready / command not configured",
        "local_vision_policy": local_vision.get("policy_status", "unknown"),
        "local_vision_runner_sha256": local_vision.get("runner_sha256", "") or "not available",
        "landmark_index_rows": len(landmarks),
        "offline_geocoder_seed_rows": geocoder_rows,
        "offline_geocoder_generated_rows": generated_geocoder_rows,
        "project_geo_source_rows": project_geo_source_rows,
        "raw_cities15000_ready": raw_geonames["ready"],
        "optional_stack": optional_stack,
        "geo_alias_countries": geo_alias_countries,
        "geo_alias_cities": geo_alias_cities,
        "offline_geocoder_importer": "available" if (root / "tools" / "build_offline_geocoder_index.py").exists() else "missing",
        "online_osint_connectors": "available / privacy-gated" if (root / "app" / "core" / "osint" / "online_enrichment.py").exists() else "missing",
        "exiftool_bridge": "available" if (root / "app" / "core" / "forensics" / "exiftool_bridge.py").exists() else "missing",
        "qr_barcode_detector": "available" if (root / "app" / "core" / "vision" / "barcode_detector.py").exists() else "missing",
        "yolo_bridge": "available / disabled by default" if (root / "app" / "core" / "vision" / "yolo_detector.py").exists() else "missing",
        "geo_confidence_cells": "available" if (root / "app" / "core" / "osint" / "geocell.py").exists() else "missing",
        "geo_data_sources_doc": "available" if (root / "docs" / "GEO_DATA_SOURCES.md").exists() else "missing",
        "visual_similarity_search": "available" if similarity_tool.exists() else "missing",
        "validation_dataset_template": "available" if validation_template.exists() else "missing",
        "validation_cases_v12_10_24": "available" if validation_cases.exists() else "missing",
        "benchmark_accuracy_tool": "available" if benchmark_tool.exists() else "missing",
        "map_provider_bridge": "online lookup enabled" if os.environ.get("GEOTRACE_ONLINE_MAP_LOOKUP", "0").strip().lower() in {"1", "true", "yes", "on"} else "offline links ready / online lookup off",
        "tests_available": len(tests),
    }

    sections: list[HealthSection] = []
    sections.append(HealthSection(
        "Runtime dependencies",
        "PASS" if dep.app_ready else "WARN",
        f"Required dependencies {dep.required_ok}/{dep.required_total}; optional {dep.optional_ok}/{dep.optional_total}.",
        dep.warnings[:6],
    ))
    sections.append(HealthSection(
        "P2 AI/vision readiness",
        "PASS" if local_vision.get("enabled") else "WARN",
        str(p2["local_vision_model"]),
        [
            "GeoTrace keeps deterministic/offline analysis by default.",
            "Configure GEOTRACE_LOCAL_VISION_COMMAND for real local model execution.",
            "Runner output is bounded, parsed as JSON, blocked on shell-control tokens, and executed with shell=False.",
            f"Runner policy: {local_vision.get('policy_status', 'unknown')}; SHA256: {(local_vision.get('runner_sha256') or 'not available')[:16]}",
            "Manifest template: data/local_vision/manifest.example.json; setup guide: docs/LOCAL_VISION_SETUP.md.",
        ],
    ))
    sections.append(HealthSection(
        "Optional forensic/AI engines",
        "PASS" if (root / "app" / "core" / "forensics" / "exiftool_bridge.py").exists() and (root / "app" / "core" / "vision" / "barcode_detector.py").exists() else "WARN",
        "ExifTool/QR/ImageHash/timezone/YOLO bridges are code-ready and fail-safe.",
        [
            f"ExifTool bridge: {p2.get('exiftool_bridge')}",
            f"QR/barcode detector: {p2.get('qr_barcode_detector')}",
            f"YOLO bridge: {p2.get('yolo_bridge')}",
            "Install requirements-forensics.txt for ExifTool Python wrapper, QR/barcode, ImageHash, timezonefinder, pycountry, and DuckDB.",
            "Install requirements-ai-heavy.txt only on capable machines; YOLO requires GEOTRACE_YOLO_ENABLED=1 and GEOTRACE_YOLO_MODEL.",
        ],
    ))
    sections.append(HealthSection(
        "Map provider bridge",
        "PASS",
        str(p2["map_provider_bridge"]),
        [
            "Generates Google Maps, OpenStreetMap, and Apple Maps verification links from native GPS, parsed map URLs, OCR coordinates, or place labels.",
            "Online Nominatim geocoding/reverse-geocoding is disabled by default and requires GEOTRACE_ONLINE_MAP_LOOKUP=1.",
            "Evidence files are never uploaded automatically; opening provider links is an analyst-approved action.",
        ],
    ))
    sections.append(HealthSection(
        "Landmark/geocoder data",
        "PASS" if len(landmarks) >= 80 and geocoder_rows >= 40 else "WARN",
        f"{len(landmarks)} landmark aliases + {geocoder_rows} seed places + {generated_geocoder_rows} generated places loaded/offline.",
        ["Still a seed database, not a global proof engine; every derived location needs corroboration."],
    ))
    sections.append(HealthSection(
        "Optional stack and city database",
        "PASS" if raw_geonames["ready"] or generated_geocoder_rows > 0 else "WARN",
        "GeoNames source detected or generated index already exists." if raw_geonames["ready"] or generated_geocoder_rows > 0 else "Put cities1000.zip/cities15000.zip in data/geo/raw, then run import_project_geo_data.bat.",
        [
            f"Raw GeoNames ready: {raw_geonames['ready']} (city files={', '.join(raw_geonames.get('present_city_files', [])) or 'none'})",
            f"Aux GeoNames enrichment: {raw_geonames.get('aux_ready', False)} (aux files={', '.join(raw_geonames.get('present_aux_files', [])) or 'none'})",
            f"UI optional installed: {sum(optional_stack['ui'].values())}/{len(optional_stack['ui'])}",
            f"Geo optional installed: {sum(optional_stack['geo'].values())}/{len(optional_stack['geo'])}",
            f"Forensics optional installed: {sum(optional_stack['forensics'].values())}/{len(optional_stack['forensics'])}",
            f"Geo+ optional installed: {sum(optional_stack['geo_plus'].values())}/{len(optional_stack['geo_plus'])}",
            f"AI optional installed: {sum(optional_stack['ai'].values())}/{len(optional_stack['ai'])}",
            f"OSINT optional installed: {sum(optional_stack['osint'].values())}/{len(optional_stack['osint'])}",
            "Heavy AI note: YOLO/PaddleOCR are disabled unless explicitly installed and configured.",
        ],
    ))
    sections.append(HealthSection(
        "Validation and benchmark",
        "PASS" if validation_template.exists() and benchmark_tool.exists() else "WARN",
        "Ground-truth template and benchmark CLI are present." if validation_template.exists() and benchmark_tool.exists() else "Validation assets incomplete.",
        ["Use a real labelled dataset folder before claiming accuracy numbers."],
    ))
    sections.append(HealthSection(
        "Release/build hygiene",
        "PASS" if release_ok else "FAIL",
        "Windows setup/run/release scripts and PyInstaller spec are present." if release_ok else "Release files missing.",
        [f"Tests discovered: {len(tests)}", "Run python -m pytest -q and make_release.bat on Windows before delivery."],
    ))

    security_findings = _scan_security_patterns(root)
    if not security_findings:
        sections.append(HealthSection("Security hygiene", "PASS", "No high-risk executable patterns found in app/tools scan.", []))
    else:
        sections.append(HealthSection("Security hygiene", "WARN", f"{len(security_findings)} pattern(s) require manual review.", security_findings[:6]))

    score = 60
    score += 10 if dep.app_ready else 0
    score += 8 if release_ok else 0
    score += 7 if len(landmarks) >= 80 else 0
    score += 5 if (geocoder_rows + generated_geocoder_rows) >= 40 else 0
    score += 3 if raw_geonames["ready"] or generated_geocoder_rows > 0 else 0
    score += 5 if validation_template.exists() and benchmark_tool.exists() else 0
    score += 5 if similarity_tool.exists() else 0
    score += 3
    score = max(0, min(100, score))
    if score >= 90 and dep.app_ready and release_ok:
        overall = "READY_WITH_LOCAL_VALIDATION_REQUIRED"
    elif score >= 78:
        overall = "MOSTLY_READY_REVIEW_WARNINGS"
    else:
        overall = "NEEDS_SETUP"
    return SystemHealthReport(overall, score, dep, sections, security_findings, p2)
