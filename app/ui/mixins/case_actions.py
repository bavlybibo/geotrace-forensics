from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QFileDialog, QInputDialog, QListWidgetItem, QMessageBox

try:
    from ...core.map_service import MapService
    from ...core.report_service import ReportService
    from ..dialogs import RecentCasesDialog
except ImportError:  # pragma: no cover - fallback for direct script execution
    from app.core.map_service import MapService
    from app.core.report_service import ReportService
    from app.ui.dialogs import RecentCasesDialog


class CaseActionsMixin:

    def _refresh_cases_page(self) -> None:
        if not hasattr(self, "cases_summary"):
            return
        cases = self.case_manager.list_cases()
        lines = [f"Total cases in library: {len(cases)}", f"Active case: {self.case_manager.active_case_id} — {self.case_manager.active_case_name}", "", "Recent cases:"]
        for case in cases[:10]:
            lines.append(f"- {case.case_name} | {case.case_id} | {case.item_count} item(s) | updated {case.updated_at}")
        self.cases_summary.setPlainText("\n".join(lines))
        self.cases_list.clear()
        for case in cases:
            item = QListWidgetItem(f"{case.case_name} — {case.case_id} — {case.item_count} item(s)")
            item.setData(Qt.UserRole, case.case_id)
            self.cases_list.addItem(item)
            if case.case_id == self.case_manager.active_case_id:
                self.cases_list.setCurrentItem(item)

    def _case_export_dir(self) -> Path:
        path = self.project_root / "exports" / self.case_manager.active_case_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _switch_case_from_combo(self, index: int) -> None:
        if index < 0:
            return
        case_id = self.case_switch_combo.itemData(index)
        if not case_id or case_id == self.case_manager.active_case_id:
            return
        switched = self.case_manager.switch_case(case_id)
        if switched is None:
            return
        self.records = list(self.case_manager.records)
        self.filtered_records = list(self.records)
        self.export_dir = self._case_export_dir()
        self.map_service = MapService(self.export_dir)
        self.report_service = ReportService(self.export_dir)
        self.current_map_path = None
        self.thumbnail_cache.clear()
        self.preview_cache.clear()
        self.frame_cache.clear()
        self.populate_table(self.filtered_records)
        self.refresh_dashboard()
        self.update_charts()
        self.populate_timeline()
        self.populate_custody_log()
        if self.filtered_records:
            self._auto_select_visible_record()
        else:
            self.clear_details(reason=self._inventory_status_message([]))
        self._refresh_case_badges()
        self._refresh_cases_page()
        self._show_toast("Case reopened", f"Loaded {self.case_manager.active_case_name}", tone="success")

    def _refresh_case_switcher(self) -> None:
        if not hasattr(self, "case_switch_combo"):
            return
        self.case_switch_combo.blockSignals(True)
        self.case_switch_combo.clear()
        for case in self.case_manager.list_cases():
            label = f"{case.case_name} • {case.item_count} item(s)"
            self.case_switch_combo.addItem(label, case.case_id)
            if case.case_id == self.case_manager.active_case_id:
                self.case_switch_combo.setCurrentIndex(self.case_switch_combo.count() - 1)
        self.case_switch_combo.blockSignals(False)

    def start_new_case(self) -> None:
        if self.settings.value("confirm_before_new_case", True, type=bool) and self.records:
            answer = QMessageBox.question(self, "Start New Case", "Create a new active case and clear the current review context? Existing cases remain saved.")
            if answer != QMessageBox.Yes:
                return
        name, ok = QInputDialog.getText(self, "New Case", "Case name:", text=f"Case {self.case_manager.active_case_name}")
        if not ok:
            return
        case = self.case_manager.new_case(name.strip() or None)
        self.records = []
        self.filtered_records = []
        self.thumbnail_cache.clear()
        self.preview_cache.clear()
        self.frame_cache.clear()
        self.current_frames = []
        self.current_frame_index = 0
        self.current_frame_record = None
        self.export_dir = self._case_export_dir()
        self.map_service = MapService(self.export_dir)
        self.report_service = ReportService(self.export_dir)
        self.inventory_list.clear()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Ready")
        self.command_progress.setText("New isolated case created")
        self.current_map_path = None
        self._refresh_case_badges()
        self.refresh_dashboard()
        self.clear_details()
        self.populate_custody_log()
        self.export_summary.setPlainText(f"Active case changed to {case.case_id}. Previous case logs remain isolated.")
        self.last_export_payload = {}
        self._refresh_report_artifact_cards()
        self._refresh_cases_page()
        self._show_toast("New case created", case.case_id, tone="success")

    def _refresh_case_badges(self) -> None:
        count = len(self.records)
        self.case_badge.setText(f"{self.case_manager.active_case_id} — {self.case_manager.active_case_name}")
        self.export_badge.setText("Import → Review → Export" if not count else f"{count} item(s) ready for review")
        self._set_info_badge(self.case_label, "Case ID", self.case_manager.active_case_id)
        self._set_info_badge(self.status_label, "Status", "Awaiting evidence" if not count else f"{count} evidence item(s) analyzed")

    def open_recent_cases_dialog(self) -> None:
        dialog = RecentCasesDialog(self.case_manager.list_cases(), self)
        if dialog.exec_() and dialog.selected_case_id:
            idx = self.case_switch_combo.findData(dialog.selected_case_id)
            if idx >= 0:
                self.case_switch_combo.setCurrentIndex(idx)
                self._set_workspace_page("Cases")

    def open_selected_case_from_page(self) -> None:
        item = self.cases_list.currentItem()
        if item is None:
            return
        case_id = item.data(Qt.UserRole)
        idx = self.case_switch_combo.findData(case_id)
        if idx >= 0:
            self.case_switch_combo.setCurrentIndex(idx)

    def open_case_snapshot_folder(self) -> None:
        snapshot_path = self.case_manager.case_snapshot_path()
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(snapshot_path.parent)))


    def create_case_backup_from_ui(self) -> None:
        try:
            backup_path = self.case_manager.create_case_backup()
            self._refresh_cases_page()
            self.populate_custody_log()
            self._show_toast("Backup created", backup_path.name, tone="success")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(backup_path.parent)))
        except Exception as exc:
            self._log_error("Backup Error", str(exc))
            self.show_info("Backup Error", str(exc))

    def restore_case_backup_from_ui(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Restore GeoTrace Case Backup", str(self.project_root), "GeoTrace Backups (*.zip)")
        if not path:
            return
        try:
            restored_case_id = self.case_manager.restore_case_backup(Path(path))
            self._refresh_cases_page()
            self._refresh_case_switcher()
            self.populate_custody_log()
            self._show_toast("Backup restored", restored_case_id, tone="success")
        except Exception as exc:
            self._log_error("Restore Error", str(exc))
            self.show_info("Restore Error", str(exc))

    def rename_active_case(self) -> None:
        name, ok = QInputDialog.getText(self, "Rename Active Case", "Case name:", text=self.case_manager.active_case_name)
        if not ok or not name.strip():
            return
        self.case_manager.db.rename_case(self.case_manager.active_case_id, name.strip())
        self.case_manager.active_case = self.case_manager.db.get_active_case() or self.case_manager.active_case
        self.case_manager._write_case_snapshot()
        self._refresh_case_badges()
        self._refresh_case_switcher()
        self._refresh_cases_page()
        self._show_toast("Case renamed", self.case_manager.active_case_name, tone="success")
