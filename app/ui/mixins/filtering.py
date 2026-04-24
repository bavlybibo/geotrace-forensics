from __future__ import annotations

from datetime import datetime
from typing import List

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QColor, QPixmap
from PyQt5.QtWidgets import QListWidgetItem

try:
    from ...core.anomalies import parse_timestamp
    from ...core.models import EvidenceRecord
    from ..widgets import EvidenceListCard
except ImportError:  # pragma: no cover - fallback for direct script execution
    from app.core.anomalies import parse_timestamp
    from app.core.models import EvidenceRecord
    from app.ui.widgets import EvidenceListCard


class FilteringMixin:

    def populate_table(self, records: List[EvidenceRecord]) -> None:
        self.inventory_list.clear()
        for record in records:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, record.evidence_id)
            item.setSizeHint(QSize(0, 148))
            card = EvidenceListCard()
            badge_bits = [
                f"● {record.risk_level}",
                f"● {'GPS' if record.has_gps else 'No GPS'}",
                f"● {record.source_subtype if record.source_subtype not in {'Unknown', record.source_type} else record.source_type}",
            ]
            if record.duplicate_group:
                badge_bits.append(record.duplicate_group)
            if record.bookmarked:
                badge_bits.append('★ bookmarked')
            support = (
                f"Time: {record.timestamp_source} {record.timestamp_confidence}% • OCR {record.ocr_confidence}%\n"
                f"Value: {record.evidentiary_value}% • Courtroom: {record.courtroom_strength}%"
            )
            card.set_content(
                self._thumbnail_for_record(record),
                f"{record.evidence_id} — {record.file_name}",
                (
                    f"{self._display_timestamp(record.timestamp)}\n"
                    f"{record.source_subtype if record.source_subtype not in {'Unknown', record.source_type} else record.source_type}"
                ),
                " • ".join(badge_bits),
                risk=record.risk_level,
                support=support,
                score=record.suspicion_score,
                evidentiary_value=record.evidentiary_value,
                evidentiary_label=record.evidentiary_label,
            )
            self.inventory_list.addItem(item)
            self.inventory_list.setItemWidget(item, card)
        self.inventory_meta.setText(self._inventory_status_message(records))

    def _thumbnail_for_record(self, record: EvidenceRecord) -> QPixmap:
        cached = self.thumbnail_cache.get(record.evidence_id)
        if cached is not None:
            return cached
        placeholder = QPixmap(104, 72)
        placeholder.fill(QColor("#0a1728"))
        pixmap = self._load_pixmap_from_record(record)
        thumb = placeholder if pixmap is None or pixmap.isNull() else pixmap.scaled(104, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.thumbnail_cache[record.evidence_id] = thumb
        return thumb

    def _display_timestamp(self, timestamp: str) -> str:
        if timestamp == "Unknown":
            return timestamp
        return timestamp.replace(":", "-", 2)

    def _inventory_status_message(self, records: List[EvidenceRecord]) -> str:
        if not self.case_manager.records:
            return "This case has no evidence yet. Import files or a folder to begin the review."
        if not records:
            return "No results match the current filters. Clear filters or search terms to bring evidence back into view."
        return f"Showing {len(records)} evidence item(s) from the active case. Select one item to begin review."

    def _auto_select_visible_record(self, preferred_evidence_id: str | None = None) -> None:
        if self.inventory_list.count() == 0:
            self.clear_details(reason=self._inventory_status_message([]))
            return
        target_row = 0
        if preferred_evidence_id:
            for row in range(self.inventory_list.count()):
                item = self.inventory_list.item(row)
                if item and item.data(Qt.UserRole) == preferred_evidence_id:
                    target_row = row
                    break
        self.inventory_list.blockSignals(True)
        self.inventory_list.setCurrentRow(target_row)
        self.inventory_list.blockSignals(False)
        self.populate_details()

    def apply_filters(self) -> None:
        query = self.search_box.text().strip()
        mode = self.filter_combo.currentText()
        current = self.selected_record()
        preferred_evidence_id = current.evidence_id if current else None
        filtered: List[EvidenceRecord] = []
        tokens = [token for token in query.lower().split() if token]
        for record in self.case_manager.records:
            if not self._record_matches_query(record, tokens):
                continue
            if mode == "Has GPS" and not record.has_gps:
                continue
            if mode == "High Risk" and record.risk_level != "High":
                continue
            if mode == "Medium Risk" and record.risk_level != "Medium":
                continue
            if mode == "Low Risk" and record.risk_level != "Low":
                continue
            if mode == "Screenshots / Exports" and not ("Screenshot" in record.source_type or "Messaging" in record.source_type):
                continue
            if mode == "Camera Photos" and record.source_type != "Camera Photo":
                continue
            if mode == "Edited / Exported" and record.source_type != "Edited / Exported":
                continue
            if mode == "Duplicate Cluster" and not record.duplicate_group:
                continue
            if mode == "Parser Issues" and record.parser_status == "Valid" and record.signature_status != "Mismatch":
                continue
            if mode == "Bookmarked" and not record.bookmarked:
                continue
            filtered.append(record)

        sort_mode = self.sort_combo.currentText() if hasattr(self, "sort_combo") else "Score ↓"
        filtered = self._sort_records(filtered, sort_mode)
        self.filtered_records = filtered
        self.populate_table(filtered)
        if filtered:
            self._auto_select_visible_record(preferred_evidence_id)
        else:
            self.clear_details(reason=self._inventory_status_message([]))

    def _record_search_haystack(self, record: EvidenceRecord) -> str:
        parts = [
            record.evidence_id, record.file_name, str(record.file_path), record.device_model, record.gps_display,
            record.timestamp, record.timestamp_source, record.software, record.source_type, record.parser_status,
            record.signature_status, record.format_trust, record.duplicate_group, record.analyst_verdict, record.tags, record.note,
            record.parse_error, record.hidden_code_summary, record.hidden_content_overview, record.format_name, record.dimensions,
            " ".join(record.anomaly_reasons), " ".join(record.osint_leads), " ".join(record.extracted_strings),
            " ".join(record.hidden_code_indicators), " ".join(record.urls_found),
        ]
        return " ".join(part for part in parts if part).lower()

    def _record_matches_query(self, record: EvidenceRecord, tokens: List[str]) -> bool:
        if not tokens:
            return True
        haystack = self._record_search_haystack(record)
        for token in tokens:
            if ':' in token:
                key, value = token.split(':', 1)
                value = value.strip()
                if key == 'gps':
                    expected = value in {'yes', 'true', '1', 'on'}
                    if record.has_gps != expected:
                        return False
                    continue
                if key == 'risk' and record.risk_level.lower() != value:
                    return False
                elif key == 'parser' and value not in record.parser_status.lower():
                    return False
                elif key == 'source' and value not in record.source_type.lower():
                    return False
                elif key == 'tag' and value not in (record.tags or '').lower():
                    return False
                elif key == 'note' and value not in (record.note or '').lower():
                    return False
                elif key in {'hidden', 'code'}:
                    expected = value in {'yes', 'true', '1', 'on'}
                    if bool(record.hidden_code_indicators) != expected:
                        return False
                    continue
                elif key == 'url':
                    expected = value in {'yes', 'true', '1', 'on'}
                    if bool(record.urls_found) != expected:
                        return False
                    continue
                elif token not in haystack:
                    return False
            elif token not in haystack:
                return False
        return True

    def _sort_records(self, records: List[EvidenceRecord], mode: str) -> List[EvidenceRecord]:
        def ts(record: EvidenceRecord):
            parsed = parse_timestamp(record.timestamp)
            return parsed or datetime.max

        if mode == "Time ↑":
            return sorted(records, key=lambda r: (ts(r), r.evidence_id))
        if mode == "Time ↓":
            return sorted(records, key=lambda r: (ts(r), r.evidence_id), reverse=True)
        if mode == "Filename A→Z":
            return sorted(records, key=lambda r: (r.file_name.lower(), r.evidence_id))
        if mode == "Filename Z→A":
            return sorted(records, key=lambda r: (r.file_name.lower(), r.evidence_id), reverse=True)
        if mode == "Confidence ↓":
            return sorted(records, key=lambda r: (-r.confidence_score, -r.suspicion_score, r.evidence_id))
        if mode == "Bookmarked First":
            return sorted(records, key=lambda r: (not r.bookmarked, -r.suspicion_score, r.evidence_id))
        return sorted(records, key=lambda r: (-r.suspicion_score, -r.confidence_score, r.evidence_id))
