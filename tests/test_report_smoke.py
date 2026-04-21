from __future__ import annotations

from pathlib import Path

from app.core.case_manager import CaseManager
from app.core.report_service import ReportService


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_extended_report_package_outputs(tmp_path: Path):
    root = project_root()
    manager = CaseManager(tmp_path)
    manager.new_case("Extended Report")
    records = manager.load_images([root / "demo_evidence"])
    report_service = ReportService(tmp_path / "exports")
    payload = {
        "html": str(report_service.export_html(records, manager.active_case_id, manager.active_case_name, manager.export_chain_of_custody())),
        "pdf": str(report_service.export_pdf(records, manager.active_case_id, manager.active_case_name)),
        "csv": str(report_service.export_csv(records)),
        "json": str(report_service.export_json(records)),
        "courtroom": str(report_service.export_courtroom_summary(records, manager.active_case_id, manager.active_case_name)),
        "executive": str(report_service.export_executive_summary(records, manager.active_case_id, manager.active_case_name)),
        "validation": str(report_service.export_validation_summary(records, manager.active_case_id, manager.active_case_name)),
    }
    manifest = report_service.export_package_manifest(payload)
    for path in list(payload.values()) + [str(manifest)]:
        assert Path(path).exists()
