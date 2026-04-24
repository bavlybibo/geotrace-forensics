from __future__ import annotations

from typing import List, Optional

from PIL import Image, ImageSequence
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QImage, QKeySequence, QPixmap
from PyQt5.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QShortcut, QVBoxLayout

try:
    from ...core.models import EvidenceRecord
except ImportError:  # pragma: no cover - fallback for direct script execution
    from app.core.models import EvidenceRecord
from ..styles import APP_STYLESHEET
from ..widgets import ResizableImageLabel


class PreviewInteractionMixin:
    """Preview loading, frame navigation, zooming, and fullscreen behavior."""

    def _prepare_frames(self, record: EvidenceRecord) -> None:
        self.current_frame_record = record.evidence_id
        self.current_frame_index = 0
        cached = self.frame_cache.get(record.evidence_id)
        if cached is not None:
            self.current_frames = cached
            return
        frames: List[QPixmap] = []
        if record.parser_status == "Valid":
            try:
                with Image.open(record.file_path) as image:
                    if getattr(image, "is_animated", False):
                        for frame in ImageSequence.Iterator(image):
                            rgba = frame.copy().convert("RGBA")
                            data = rgba.tobytes("raw", "RGBA")
                            qimg = QImage(data, rgba.width, rgba.height, QImage.Format_RGBA8888)
                            frames.append(QPixmap.fromImage(qimg.copy()))
                            if len(frames) >= 20:
                                break
                    else:
                        pixmap = self._load_pixmap_from_record(record)
                        if pixmap is not None:
                            frames.append(pixmap)
            except Exception:
                frames = []
        if not frames:
            pixmap = self._load_pixmap_from_record(record)
            if pixmap is not None:
                frames.append(pixmap)
        self.frame_cache[record.evidence_id] = frames
        self.current_frames = frames

    def _show_previous_frame(self) -> None:
        if len(self.current_frames) <= 1:
            return
        self.current_frame_index = (self.current_frame_index - 1) % len(self.current_frames)
        self.image_preview.set_source_pixmap(self.current_frames[self.current_frame_index])
        self.frame_index_badge.setText(f"Frame {self.current_frame_index + 1}/{len(self.current_frames)}")
        self._refresh_zoom_pill()

    def _show_next_frame(self) -> None:
        if len(self.current_frames) <= 1:
            return
        self.current_frame_index = (self.current_frame_index + 1) % len(self.current_frames)
        self.image_preview.set_source_pixmap(self.current_frames[self.current_frame_index])
        self.frame_index_badge.setText(f"Frame {self.current_frame_index + 1}/{len(self.current_frames)}")
        self._refresh_zoom_pill()

    def _build_parser_fallback_text(self, record: EvidenceRecord) -> str:
        return (
            "Forensic Fallback View\n\n"
            f"Parser: {record.parser_status}\n"
            f"Signature: {record.signature_status} ({record.format_signature})\n"
            f"Trust: {record.format_trust}\n"
            f"File Size: {record.file_size:,} bytes\n"
            f"SHA-256: {record.sha256}\n"
            f"MD5: {record.md5}\n"
            f"Reason: {record.parse_error or 'Preview unavailable.'}\n\n"
            "Recommended validation workflow:\n"
            "1) Preserve hashes and original path.\n"
            "2) Confirm header signature separately from decoder output.\n"
            "3) Validate timeline anchors externally before relying on preview content."
        )

    def _refresh_zoom_pill(self) -> None:
        self.preview_zoom_pill.setText(f"Zoom {self.image_preview.zoom_percent()}%")

    def _zoom_preview_in(self) -> None:
        self.image_preview.zoom_in()
        self._refresh_zoom_pill()

    def _zoom_preview_out(self) -> None:
        self.image_preview.zoom_out()
        self._refresh_zoom_pill()

    def _zoom_preview_fit(self) -> None:
        self.image_preview.fit_to_window()
        self._refresh_zoom_pill()

    def _zoom_preview_reset(self) -> None:
        self.image_preview.reset_zoom()
        self._refresh_zoom_pill()

    def _open_preview_fullscreen(self) -> None:
        record = self.selected_record()
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Fullscreen Evidence Stage — {record.evidence_id if record else 'Preview'}")
        dialog.resize(1380, 900)
        dialog.setStyleSheet(APP_STYLESHEET)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        title = QLabel(f"{record.evidence_id if record else 'Preview'} • fullscreen review")
        title.setObjectName("SectionLabel")
        toolbar.addWidget(title)
        toolbar.addStretch(1)
        zoom_label = QLabel("Zoom 100%")
        zoom_label.setObjectName("PreviewZoomPill")
        toolbar.addWidget(zoom_label)

        viewer = ResizableImageLabel("Preview unavailable.", min_height=760)
        if self.current_preview_pixmap is not None:
            viewer.set_source_pixmap(self.current_preview_pixmap)
        else:
            viewer.clear_source(self.image_preview.text())

        def sync_zoom() -> None:
            zoom_label.setText(f"Zoom {viewer.zoom_percent()}%")

        controls = []
        for label, callback in [("−", viewer.zoom_out), ("+", viewer.zoom_in), ("Fit", viewer.fit_to_window), ("100%", viewer.reset_zoom)]:
            btn = QPushButton(label)
            btn.setObjectName("SmallGhostButton")
            btn.clicked.connect(lambda checked=False, cb=callback: (cb(), sync_zoom()))
            toolbar.addWidget(btn)
            controls.append(btn)
        close_btn = QPushButton("Close")
        close_btn.setObjectName("SmallGhostButton")
        close_btn.clicked.connect(dialog.accept)
        toolbar.addWidget(close_btn)

        hint = QLabel("Esc close • +/- zoom • F fit")
        hint.setObjectName("MutedLabel")
        layout.addLayout(toolbar)
        layout.addWidget(viewer, 1)

        QShortcut(QKeySequence(Qt.Key_Escape), dialog, activated=dialog.reject)
        QShortcut(QKeySequence(Qt.Key_Plus), dialog, activated=lambda: (viewer.zoom_in(), sync_zoom()))
        QShortcut(QKeySequence(Qt.Key_Minus), dialog, activated=lambda: (viewer.zoom_out(), sync_zoom()))
        QShortcut(QKeySequence("F"), dialog, activated=lambda: (viewer.fit_to_window(), sync_zoom()))
        dialog.exec_()

    def open_selected_file(self) -> None:
        record = self.selected_record()
        if record is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(record.file_path)))

    def _load_pixmap_from_record(self, record: EvidenceRecord) -> Optional[QPixmap]:
        if record.evidence_id in self.preview_cache:
            return self.preview_cache[record.evidence_id]
        pixmap = QPixmap(str(record.file_path))
        if not pixmap.isNull():
            self.preview_cache[record.evidence_id] = pixmap
            return pixmap
        try:
            with Image.open(record.file_path) as image:
                frame = next(iter(ImageSequence.Iterator(image))).copy() if getattr(image, "is_animated", False) else image.copy()
                rgba = frame.convert("RGBA")
                data = rgba.tobytes("raw", "RGBA")
                qimg = QImage(data, rgba.width, rgba.height, QImage.Format_RGBA8888)
                pixmap = QPixmap.fromImage(qimg.copy())
                self.preview_cache[record.evidence_id] = pixmap
                return pixmap
        except Exception:
            self.preview_cache[record.evidence_id] = None
            return None

    def _select_default_tab(self, record: EvidenceRecord) -> None:
        if hasattr(self, "review_tabs"):
            if record.parser_status != "Valid":
                self.review_tabs.setCurrentIndex(0)
            elif record.hidden_code_indicators:
                self.review_tabs.setCurrentIndex(3)
            elif record.note:
                self.review_tabs.setCurrentIndex(4)
            else:
                self.review_tabs.setCurrentIndex(0)
        self._set_workspace_page("Review")

    def _highlight_selected_inventory_card(self) -> None:
        for index in range(self.inventory_list.count()):
            item = self.inventory_list.item(index)
            widget = self.inventory_list.itemWidget(item)
            if widget is not None:
                widget.setProperty("selected", item is self.inventory_list.currentItem())
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()

