from __future__ import annotations

from pathlib import Path
from typing import List
from datetime import datetime
import re

from PyQt5.QtCore import QObject, pyqtSignal

try:
    from ..core.case_manager import AnalysisCancelled, CaseManager
    from ..core.models import EvidenceRecord
    from ..core.report_service import ReportService
    from ..core.reports import write_verification_report
    from ..core.reports.package_assets import copy_package_assets
except ImportError:  # pragma: no cover - fallback for direct script execution
    from app.core.case_manager import AnalysisCancelled, CaseManager
    from app.core.models import EvidenceRecord
    from app.core.report_service import ReportService
    from app.core.reports import write_verification_report
    from app.core.reports.package_assets import copy_package_assets


class AnalysisWorker(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, manager: CaseManager, paths: List[Path]) -> None:
        super().__init__()
        self.manager = manager
        self.paths = paths
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            records = self.manager.load_images(
                self.paths,
                progress_callback=lambda value, text: self.progress.emit(value, text),
                cancel_callback=lambda: self._cancelled,
            )
        except AnalysisCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.error.emit(str(exc))
        else:
            self.finished.emit(records)


class ReportWorker(QObject):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, report_service: ReportService, records: List[EvidenceRecord], case_id: str, case_name: str, custody_log: str, privacy_level: str = "redacted_text", export_mode: str = "Shareable Redacted") -> None:
        super().__init__()
        self.report_service = report_service
        self.records = records
        self.case_id = case_id
        self.case_name = case_name
        self.custody_log = custody_log
        self.privacy_level = privacy_level
        self.export_mode = export_mode

    def _package_service(self) -> ReportService:
        safe_mode = re.sub(r"[^A-Za-z0-9_.-]+", "_", self.export_mode.strip().lower()).strip("_") or "export"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        package_dir = self.report_service.export_dir / f"{stamp}_{safe_mode}"
        package_dir.mkdir(parents=True, exist_ok=True)
        copy_package_assets(self.report_service.export_dir, package_dir, self.privacy_level)
        return ReportService(package_dir)

    def run(self) -> None:
        try:
            package_service = self._package_service()
            privacy_guardian_path = package_service.export_privacy_guardian_summary(self.records, self.case_id, self.case_name, privacy_level=self.privacy_level)
            html_path = package_service.export_html(self.records, self.case_id, self.case_name, custody_log=self.custody_log, privacy_level=self.privacy_level)
            pdf_path = package_service.export_pdf(self.records, self.case_id, self.case_name, privacy_level=self.privacy_level)
            csv_path = package_service.export_csv(self.records, privacy_level=self.privacy_level)
            json_path = package_service.export_json(self.records, privacy_level=self.privacy_level)
            courtroom_path = package_service.export_courtroom_summary(self.records, self.case_id, self.case_name, privacy_level=self.privacy_level)
            executive_path = package_service.export_executive_summary(self.records, self.case_id, self.case_name, privacy_level=self.privacy_level)
            validation_path = package_service.export_validation_summary(self.records, self.case_id, self.case_name, privacy_level=self.privacy_level)
            ai_guardian_path = package_service.export_ai_guardian_summary(self.records, self.case_id, self.case_name, privacy_level=self.privacy_level)
            osint_appendix_path = package_service.export_osint_appendix(self.records, self.case_id, self.case_name, privacy_level=self.privacy_level)
            ctf_writeup_path = package_service.export_ctf_geolocator_writeup(self.records, self.case_id, self.case_name, privacy_level=self.privacy_level)
            payload = {
                "html": str(html_path),
                "pdf": str(pdf_path),
                "csv": str(csv_path),
                "json": str(json_path),
                "courtroom": str(courtroom_path),
                "executive": str(executive_path),
                "validation": str(validation_path),
                "ai_guardian": str(ai_guardian_path),
                "privacy_guardian": str(privacy_guardian_path),
                "osint_appendix": str(osint_appendix_path),
                "ctf_writeup": str(ctf_writeup_path),
            }
            manifest_path = package_service.export_package_manifest(payload, privacy_level=self.privacy_level)
            payload["manifest"] = str(manifest_path)
            manifest_signature_path = package_service.export_dir / "export_manifest.sha256"
            if manifest_signature_path.exists():
                payload["manifest_signature"] = str(manifest_signature_path)
            verification_payload = write_verification_report(package_service.export_dir, privacy_level=self.privacy_level)
            payload["verification"] = verification_payload.get("text", "")
            payload["verification_json"] = verification_payload.get("json", "")
            payload["verification_passed"] = str(bool(verification_payload.get("passed")))
            payload["export_mode"] = self.export_mode
            payload["privacy_level"] = self.privacy_level
            payload["export_folder"] = str(package_service.export_dir)
            self.finished.emit(payload)
        except Exception as exc:
            self.error.emit(str(exc))

