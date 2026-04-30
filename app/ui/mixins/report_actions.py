from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QThread, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QInputDialog, QMessageBox

try:
    from ..workers import ReportWorker
    from ...core.reports import write_verification_report
except ImportError:  # pragma: no cover - fallback for direct script execution
    from app.ui.workers import ReportWorker
    from app.core.reports import write_verification_report


class ReportActionsMixin:

    def _refresh_report_artifact_cards(self) -> None:
        labels = getattr(self, "report_artifact_labels", {})
        buttons = getattr(self, "report_artifact_buttons", {})
        payload = self.last_export_payload or {}
        for key, label in labels.items():
            path = payload.get(key, "")
            if path:
                label.setText(Path(path).name)
            else:
                label.setText("Not generated yet")
        for key, button in buttons.items():
            button.setEnabled(bool(payload.get(key)))

    def _open_export_artifact(self, artifact: str) -> None:
        path = self.last_export_payload.get(artifact)
        if not path:
            self.show_info("Not Generated", f"No {artifact} artifact is available for the active case yet.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def open_export_folder(self) -> None:
        self.export_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.export_dir)))

    def generate_reports(self) -> None:
        if not self.case_manager.records:
            self.show_info("No Evidence", "Import evidence before generating reports.")
            return
        if self.report_thread is not None:
            self.show_info("Export Running", "A report package is already being generated.")
            return
        modes = [
            "Shareable Redacted — safest for external sharing",
            "Internal Full — includes raw previews and unredacted text",
            "Courtroom Redacted — conservative package without preview leakage",
        ]
        choice, ok = QInputDialog.getItem(self, "Export Mode", "Choose report package mode:", modes, 0, False)
        if not ok:
            return
        export_mode = choice.split(" — ", 1)[0]
        privacy_level = "full" if export_mode == "Internal Full" else "courtroom_redacted" if export_mode == "Courtroom Redacted" else "redacted_text"
        if export_mode == "Internal Full":
            reply = QMessageBox.warning(
                self,
                "Internal Full Export",
                "Internal Full can include previews, local paths, raw OCR text, and sensitive OSINT pivots. Use Shareable Redacted or Courtroom Redacted for external sharing. Continue anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        custody = self.case_manager.export_chain_of_custody()
        self.command_progress.setText(f"Generating {export_mode} report package in background…")
        self.export_summary.setPlainText(
            f"Background export started…\n\nMode: {export_mode}\nPrivacy level: {privacy_level}\n"
            "Creating HTML, PDF, CSV, JSON, manifest, validation, executive, courtroom, AI Guardian, OSINT appendix, CTF GeoLocator, claim matrix, and report-builder index outputs."
        )
        self.report_thread = QThread(self)
        self.report_worker = ReportWorker(
            self.report_service,
            list(self.case_manager.records),
            self.case_manager.active_case_id,
            self.case_manager.active_case_name,
            custody,
            privacy_level=privacy_level,
            export_mode=export_mode,
        )
        self.report_worker.moveToThread(self.report_thread)
        self.report_thread.started.connect(self.report_worker.run)
        self.report_worker.finished.connect(self._on_report_finished)
        self.report_worker.error.connect(self._on_report_error)
        self.report_worker.finished.connect(self.report_thread.quit)
        self.report_worker.error.connect(self.report_thread.quit)
        self.report_thread.finished.connect(self._cleanup_report_thread)
        self.report_thread.start()

    def _on_report_finished(self, payload: dict) -> None:
        self.last_export_payload = dict(payload)
        self._refresh_report_artifact_cards()
        if hasattr(self, "reports_metric_package_value"):
            privacy_level = payload.get("privacy_level", "redacted_text")
            mode = payload.get("export_mode", "Shareable Redacted")
            passed = payload.get("verification_passed") == "True"
            top_readiness = max([int(getattr(record, "map_answer_readiness_score", 0) or 0) for record in self.case_manager.records], default=0)
            self.reports_metric_package_value.setText("Ready")
            self.reports_metric_package_note.setText(f"{mode} • {Path(payload.get('export_folder', '')).name or 'timestamped folder'}")
            self.reports_metric_privacy_value.setText("Internal Full" if privacy_level == "full" else "Redacted")
            self.reports_metric_privacy_note.setText("Do not share externally without redaction." if privacy_level == "full" else f"Privacy level: {privacy_level}")
            self.reports_metric_verify_value.setText("PASS" if passed else "REVIEW")
            self.reports_metric_verify_note.setText("Manifest/hash verification completed." if passed else "Run Verify Last Package before handoff.")
            self.reports_metric_ctf_value.setText(f"{top_readiness}%")
            self.reports_metric_ctf_note.setText("Final answers require GPS/OCR/URL/place anchors; visual-only stays as lead.")
        self.export_badge.setText("Report Package Generated")
        self.command_progress.setText("Export package ready")
        self.export_summary.setPlainText(
            "Generated files for the active case:\n\n"
            f"HTML: {Path(payload['html']).name}\n"
            f"PDF: {Path(payload['pdf']).name}\n"
            f"CSV: {Path(payload['csv']).name}\n"
            f"JSON: {Path(payload['json']).name}\n"
            f"Courtroom: {Path(payload['courtroom']).name}\n"
            f"Validation: {Path(payload['validation']).name}\n"
            f"Validation Template: {Path(payload.get('validation_template', '')).name if payload.get('validation_template') else 'not generated'}\n"
            f"AI Guardian: {Path(payload.get('ai_guardian', '')).name if payload.get('ai_guardian') else 'not generated'}\n"
            f"Privacy Guardian: {Path(payload.get('privacy_guardian', '')).name if payload.get('privacy_guardian') else 'not generated'}\n"
            f"OSINT Appendix: {Path(payload.get('osint_appendix', '')).name if payload.get('osint_appendix') else 'not generated'}\n"
            f"CTF GeoLocator: {Path(payload.get('ctf_writeup', '')).name if payload.get('ctf_writeup') else 'not generated'}\n"
            f"Claim Matrix: {Path(payload.get('claim_matrix', '')).name if payload.get('claim_matrix') else 'not generated'}\n"
            f"Report Builder: {Path(payload.get('report_builder', '')).name if payload.get('report_builder') else 'not generated'}\n"
            f"Verification: {Path(payload.get('verification', '')).name if payload.get('verification') else 'not generated'} ({'PASS' if payload.get('verification_passed') == 'True' else 'REVIEW'})\n"
            f"Manifest: {Path(payload['manifest']).name}\n"
            f"Manifest Signature: {Path(payload.get('manifest_signature', '')).name if payload.get('manifest_signature') else 'not generated'}\n\n"
            f"Mode: {payload.get('export_mode', 'Shareable Redacted')}\n"
            f"Privacy level: {payload.get('privacy_level', 'redacted_text')}\n"
            "CSV follows the selected privacy level; each export mode now uses an isolated timestamped folder. report_assets are included in manifest hashes when present. Launch Gate blockers are listed in report_builder_index.\n"
            f"Export folder: {payload.get('export_folder', str(self.export_dir))}"
        )
        self.populate_custody_log()
        self.report_notes_view.setPlainText(
            "Corroboration checklist:\n"
            "- confirm timeline anchors against uploads/chats\n"
            "- validate GPS externally before courtroom claims\n"
            "- preserve original hashes and acquisition path\n"
            "- verify screenshot context with source application or browser logs\n"
            "- review the AI corroboration plan before external sharing"
        )


    def verify_last_export_package(self) -> None:
        payload = self.last_export_payload or {}
        folder = payload.get("export_folder")
        if not folder:
            self.show_info("No Package", "Generate a report package before running the courtroom verifier.")
            return
        try:
            result = write_verification_report(Path(folder), privacy_level=payload.get("privacy_level", "redacted_text"))
            self.last_export_payload["verification"] = result.get("text", "")
            self.last_export_payload["verification_json"] = result.get("json", "")
            self.last_export_payload["verification_passed"] = str(bool(result.get("passed")))
            self._refresh_report_artifact_cards()
            self.export_summary.setPlainText(result.get("summary", "Verification finished."))
            if hasattr(self, "reports_metric_verify_value"):
                self.reports_metric_verify_value.setText("PASS" if result.get("passed") else "REVIEW")
                self.reports_metric_verify_note.setText("Manifest, artifacts, and report assets verified." if result.get("passed") else "Verifier found warnings/failures; inspect package_verification.")
            self._show_toast("Package verified", "Courtroom package verifier completed.", tone="success" if result.get("passed") else "warning")
        except Exception as exc:
            self._log_error("Package Verification Error", str(exc))
            self.show_info("Verification Error", str(exc))

    def _on_report_error(self, message: str) -> None:
        self.command_progress.setText("Export failed")
        self._log_error("Export Error", message)
        self.show_info("Export Error", message)

    def _cleanup_report_thread(self) -> None:
        if self.report_worker is not None:
            self.report_worker.deleteLater()
        if self.report_thread is not None:
            self.report_thread.deleteLater()
        self.report_worker = None
        self.report_thread = None
