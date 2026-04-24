from __future__ import annotations

from pathlib import Path
from typing import List

from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QFileDialog

try:
    from ..workers import AnalysisWorker
except ImportError:  # pragma: no cover - fallback for direct script execution
    from app.ui.workers import AnalysisWorker


class AnalysisActionsMixin:

    def _refresh_batch_queue_view(self) -> None:
        if not hasattr(self, "batch_queue_view"):
            return
        lines = []
        if self.current_batch_manifest:
            lines.append("Current batch:")
            lines.append(f"- {len(self.current_batch_manifest)} path(s) in active analysis")
            for path in self.current_batch_manifest[:5]:
                lines.append(f"  • {path.name}")
        else:
            lines.append("No active analysis batch.")
        lines.append("")
        lines.append(f"Queued batches: {len(self.pending_batches)}")
        for idx, batch in enumerate(self.pending_batches[:6], start=1):
            names = ", ".join(path.name for path in batch[:3])
            if len(batch) > 3:
                names += f" … (+{len(batch) - 3} more)"
            lines.append(f"{idx}. {len(batch)} path(s) — {names}")
        self.batch_queue_view.setPlainText("\n".join(lines).strip())

    def _queue_or_start_analysis(self, paths: List[Path]) -> None:
        if self.analysis_thread is not None:
            self.pending_batches.append(paths)
            self.command_progress.setText(f"Batch queued ({len(self.pending_batches)} waiting)")
            self._refresh_batch_queue_view()
            self._show_toast("Batch queued", f"Queued {len(paths)} path(s) to start after the current batch.", tone="info")
            return
        self._start_analysis(paths)

    def _consume_next_batch(self) -> None:
        if self.analysis_thread is not None or not self.pending_batches:
            return
        next_batch = self.pending_batches.pop(0)
        self._refresh_batch_queue_view()
        self._start_analysis(next_batch)

    def import_images(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Evidence Images",
            str(self.project_root),
            "Images (*.jpg *.jpeg *.png *.tif *.tiff *.webp *.bmp *.gif *.heic *.heif)",
        )
        if files:
            self._queue_or_start_analysis([Path(file) for file in files])

    def import_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Evidence Folder", str(self.project_root))
        if folder:
            self._queue_or_start_analysis([Path(folder)])

    def _start_analysis(self, paths: List[Path]) -> None:
        if self.analysis_thread is not None:
            self.show_info("Analysis Running", "Wait for the current batch to finish or cancel it before starting another one.")
            return
        self.current_batch_manifest = list(paths)
        self.thumbnail_cache.clear()
        self.preview_cache.clear()
        self.frame_cache.clear()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Queued")
        self.command_progress.setText("Launching background analysis worker…")
        self.btn_cancel_analysis.setEnabled(True)
        self.btn_load_images.setEnabled(False)
        self.btn_load_folder.setEnabled(False)
        self.btn_generate_report.setEnabled(False)
        self.btn_courtroom.setEnabled(False)
        self.btn_compare.setEnabled(False)
        self._refresh_batch_queue_view()

        self.analysis_thread = QThread(self)
        self.analysis_worker = AnalysisWorker(self.case_manager, paths)
        self.analysis_worker.moveToThread(self.analysis_thread)
        self.analysis_thread.started.connect(self.analysis_worker.run)
        self.analysis_worker.progress.connect(self._on_analysis_progress)
        self.analysis_worker.finished.connect(self._on_analysis_finished)
        self.analysis_worker.error.connect(self._on_analysis_error)
        self.analysis_worker.cancelled.connect(self._on_analysis_cancelled)
        self.analysis_worker.finished.connect(self.analysis_thread.quit)
        self.analysis_worker.error.connect(self.analysis_thread.quit)
        self.analysis_worker.cancelled.connect(self.analysis_thread.quit)
        self.analysis_thread.finished.connect(self._cleanup_analysis_thread)
        self.analysis_thread.start()

    def cancel_analysis(self) -> None:
        if self.analysis_worker is not None:
            self.analysis_worker.cancel()
            self.command_progress.setText("Cancellation requested…")

    def _on_analysis_progress(self, value: int, text: str) -> None:
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(text)
        self.command_progress.setText(text)

    def _on_analysis_finished(self, records: object) -> None:
        self.records = list(records) if isinstance(records, list) else []
        self.filtered_records = list(self.records)
        self.current_map_path = self.map_service.create_map(self.records)
        self.populate_table(self.filtered_records)
        self.refresh_dashboard()
        self.update_charts()
        self.populate_timeline()
        self.populate_custody_log()
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Analysis finished")
        self.command_progress.setText("Analysis finished")
        self.inventory_meta.setText(f"Loaded {len(self.records)} evidence item(s) into {self.case_manager.active_case_id}.")
        self._set_info_badge(self.status_label, "Status", f"{len(self.records)} evidence item(s) analyzed")
        self.btn_open_map.setEnabled(self.current_map_path is not None)
        self.btn_generate_report.setEnabled(bool(self.records))
        self.btn_courtroom.setEnabled(bool(self.records))
        self.btn_compare.setEnabled(len(self.records) >= 2)
        if self.filtered_records:
            self._auto_select_visible_record()
        else:
            self.clear_details(reason=self._inventory_status_message([]))
        self._refresh_batch_queue_view()
        self._refresh_cases_page()
        self._show_toast("Analysis finished", f"Processed {len(self.records)} evidence item(s).", tone="success")

    def _on_analysis_error(self, message: str) -> None:
        self.progress_bar.setFormat("Analysis failed")
        self.command_progress.setText("Analysis failed")
        self._log_error("Analysis Error", message)
        self.show_info("Analysis Error", message)
        self._refresh_batch_queue_view()

    def _on_analysis_cancelled(self) -> None:
        self.progress_bar.setFormat("Analysis cancelled")
        self.command_progress.setText("Analysis cancelled")
        self.show_info("Cancelled", "Background analysis was cancelled before completion.")
        self._show_toast("Analysis cancelled", "The active batch was cancelled.", tone="warning")
        self._refresh_batch_queue_view()

    def _cleanup_analysis_thread(self) -> None:
        self.btn_cancel_analysis.setEnabled(False)
        self.btn_load_images.setEnabled(True)
        self.btn_load_folder.setEnabled(True)
        if self.analysis_worker is not None:
            self.analysis_worker.deleteLater()
        if self.analysis_thread is not None:
            self.analysis_thread.deleteLater()
        self.analysis_worker = None
        self.analysis_thread = None
        self.current_batch_manifest = []
        self._refresh_batch_queue_view()
        self._consume_next_batch()
