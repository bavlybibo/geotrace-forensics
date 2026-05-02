from pathlib import Path


def test_optional_forensics_stack_files_exist():
    root = Path(__file__).resolve().parents[1]
    required = [
        "requirements-forensics.txt",
        "requirements-ai-heavy.txt",
        "setup_forensics_stack_windows.bat",
        "docs/OPTIONAL_FORENSICS_AI_STACK.md",
        "app/core/forensics/exiftool_bridge.py",
        "app/core/vision/barcode_detector.py",
        "app/core/vision/imagehash_plus.py",
        "app/core/vision/yolo_detector.py",
        "app/core/osint/timezone_service.py",
        "app/core/osint/country_normalizer_plus.py",
        "app/core/osint/duckdb_geo_index.py",
    ]
    missing = [item for item in required if not (root / item).exists()]
    assert not missing, missing


def test_exiftool_bridge_fails_closed_when_binary_missing(monkeypatch):
    from app.core.forensics.exiftool_bridge import extract_exiftool_metadata

    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv("GEOTRACE_EXIFTOOL_CMD", raising=False)
    result = extract_exiftool_metadata(root / "demo_evidence" / "cairo_scene.jpg", project_root=root)
    assert result.executed is False
    assert isinstance(result.warnings, list)


def test_barcode_yolo_imagehash_helpers_return_structured_status():
    from app.core.vision.barcode_detector import detect_barcodes
    from app.core.vision.imagehash_plus import compute_imagehashes
    from app.core.vision.yolo_detector import detect_objects_yolo
    from app.core.osint.timezone_service import lookup_timezone

    root = Path(__file__).resolve().parents[1]
    image = root / "demo_evidence" / "cairo_scene.jpg"

    assert isinstance(detect_barcodes(image).to_dict(), dict)
    assert isinstance(compute_imagehashes(image), dict)
    assert isinstance(detect_objects_yolo(image).to_dict(), dict)
    assert isinstance(lookup_timezone(30.0444, 31.2357).to_dict(), dict)


def test_system_health_reports_new_optional_bridges():
    from app.core.system_health import build_system_health_report

    root = Path(__file__).resolve().parents[1]
    report = build_system_health_report(root)
    assert report.p2_readiness.get("exiftool_bridge") == "available"
    assert report.p2_readiness.get("qr_barcode_detector") == "available"
    assert "yolo_bridge" in report.p2_readiness
