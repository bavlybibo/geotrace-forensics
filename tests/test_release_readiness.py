from __future__ import annotations

import json
from pathlib import Path

from app.config import APP_BUILD_CHANNEL, APP_VERSION
from app.core.report_service import ReportService
from app.core.reports import verify_export_package


def test_release_identity_matches_readme() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert APP_VERSION in readme
    assert APP_BUILD_CHANNEL in readme
    assert APP_BUILD_CHANNEL == "Public Release Candidate"


def test_release_docs_exist() -> None:
    for filename in [
        "LICENSE",
        "PRIVACY.md",
        "SECURITY.md",
        "DISCLAIMER.md",
        "THIRD_PARTY_NOTICES.md",
        "RELEASE_CHECKLIST.md",
        "make_release.bat",
    ]:
        assert Path(filename).exists(), filename


def test_production_spec_excludes_demo_evidence_and_uses_ico() -> None:
    prod_spec = Path("geotrace_forensics_x.spec").read_text(encoding="utf-8")
    demo_spec = Path("geotrace_forensics_x_demo.spec").read_text(encoding="utf-8")

    assert "(\'demo_evidence\', \'demo_evidence\')" not in prod_spec
    assert "assets/app_icon.ico" in prod_spec
    assert "demo_evidence" in demo_spec
    assert Path("assets/app_icon.ico").exists()


def test_manifest_hashes_chart_assets_and_verifier_checks_them(tmp_path: Path) -> None:
    report = tmp_path / "report.txt"
    report.write_text("internal report", encoding="utf-8")
    chart = tmp_path / "chart_timeline.png"
    chart.write_bytes(b"timeline-chart")

    service = ReportService(tmp_path)
    manifest_path = service.export_package_manifest({"report": str(report)}, privacy_level="full")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert "chart_timeline.png" in manifest["report_assets"]
    assert manifest["report_assets"]["chart_timeline.png"]["sha256"]

    result = verify_export_package(tmp_path, privacy_level="full")
    assert result.passed


def test_strict_manifest_allows_safe_charts_but_omits_sensitive_map_assets(tmp_path: Path) -> None:
    report = tmp_path / "report.txt"
    report.write_text("redacted report", encoding="utf-8")
    (tmp_path / "chart_timeline.png").write_bytes(b"timeline-chart")
    (tmp_path / "chart_map.png").write_bytes(b"map-chart")

    service = ReportService(tmp_path)
    manifest_path = service.export_package_manifest({"report": str(report)}, privacy_level="courtroom_redacted")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert "chart_timeline.png" in manifest["report_assets"]
    assert "chart_map.png" not in manifest["report_assets"]

    result = verify_export_package(tmp_path, privacy_level="courtroom_redacted")
    assert not result.passed
    assert any("chart_map.png" in failure for failure in result.failures)
