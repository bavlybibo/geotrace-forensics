#!/usr/bin/env python3
from __future__ import annotations

"""Fast local release smoke check.

This script avoids GUI startup, heavy AI imports, and network calls. It verifies
that the core modules parse, requirement groups exist, the optional geodata importer
can build a tiny GeoNames index, and System Health can produce a report.
"""

import ast
import json
from pathlib import Path
import tempfile
import zipfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def check_python_syntax() -> None:
    errors: list[str] = []
    for path in [*ROOT.joinpath("app").rglob("*.py"), *ROOT.joinpath("tools").rglob("*.py"), ROOT / "main.py"]:
        if "__pycache__" in path.parts:
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
        except Exception as exc:  # pragma: no cover
            errors.append(f"{path.relative_to(ROOT)}: {exc}")
    if errors:
        raise SystemExit("Syntax errors:\n" + "\n".join(errors))


def check_release_files() -> None:
    required = [
        "VERSION",
        "main.py",
        "requirements.txt",
        "requirements-ui.txt",
        "requirements-geo.txt",
        "requirements-ai.txt",
        "requirements-osint.txt",
        "setup_windows.bat",
        "setup_full_stack_windows.bat",
        "run_windows.bat",
        "import_project_geo_data.bat",
        "tools/build_offline_geocoder_index.py",
        "tools/check_optional_stack.py",
        "docs/GEO_PROJECT_DATA_IMPORT.md",
    ]
    missing = [name for name in required if not (ROOT / name).exists()]
    if missing:
        raise SystemExit("Missing release files: " + ", ".join(missing))


def check_geodata_importer() -> None:
    from tools import build_offline_geocoder_index as importer

    sample = (
        "3530597\tCairo\tCairo\tالقاهرة,Al Qahirah\t30.0444\t31.2357\tP\tPPLC\tEG\t\t11\t\t\t\t9606916\t\t23\tAfrica/Cairo\t2026-01-01\n"
    )
    alt = "1\t3530597\tar\tالقاهرة\t1\t0\t0\t0\t\t\n2\t3530597\ten\tCairo City\t0\t0\t0\t0\t\t\n"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        archive = tmp_path / "cities1000.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("cities1000.txt", sample)
        alt_archive = tmp_path / "alternateNamesV2.zip"
        with zipfile.ZipFile(alt_archive, "w") as zf:
            zf.writestr("alternateNamesV2.txt", alt)

        rows = list(importer.load_geonames_zip(archive, source="geonames_zip", min_population=0, limit=10))
        if not rows or rows[0]["name"] != "Cairo":
            raise SystemExit("GeoNames ZIP loader failed")
        aux = importer._find_auxiliary_files(tmp_path, tmp_path, [archive])  # noqa: SLF001 - release smoke check
        rows, stats = importer._enrich_rows_with_auxiliary(rows, aux)  # noqa: SLF001
        if "القاهرة" not in rows[0].get("aliases", []):
            raise SystemExit("alternateNamesV2 enrichment failed")
        if stats.get("alternate_aliases_added", 0) < 1:
            raise SystemExit("alternateNamesV2 stats failed")


def check_system_health() -> None:
    from app.core.system_health import build_system_health_report

    report = build_system_health_report(ROOT)
    payload = report.to_dict()
    if "overall_status" not in payload or "sections" not in payload:
        raise SystemExit("System Health report failed")


def main() -> int:
    check_release_files()
    check_python_syntax()
    check_geodata_importer()
    check_system_health()
    print("GeoTrace smoke check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
