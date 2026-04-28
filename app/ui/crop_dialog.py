from __future__ import annotations

"""Manual OCR crop picker.

A small PyQt dialog that lets analysts preview an evidence image, draw a crop box,
and return normalized coordinates for CaseManager.manual_crop_ocr().
"""

from pathlib import Path

from PyQt5.QtCore import QPoint, QRect, Qt
from PyQt5.QtGui import QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout


class CropImageLabel(QLabel):
    def __init__(self, image_path: Path):
        super().__init__()
        self.image_path = Path(image_path)
        self.original = QPixmap(str(self.image_path))
        self.scaled = QPixmap()
        self.start = QPoint()
        self.end = QPoint()
        self.selection = QRect()
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(720, 420)
        self.setText("Image preview unavailable." if self.original.isNull() else "")
        self._refresh_pixmap()

    def resizeEvent(self, event):  # pragma: no cover - UI runtime
        super().resizeEvent(event)
        self._refresh_pixmap()

    def _refresh_pixmap(self) -> None:
        if self.original.isNull():
            return
        self.scaled = self.original.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.update()

    def _pixmap_rect(self) -> QRect:
        if self.scaled.isNull():
            return QRect()
        x = (self.width() - self.scaled.width()) // 2
        y = (self.height() - self.scaled.height()) // 2
        return QRect(x, y, self.scaled.width(), self.scaled.height())

    def paintEvent(self, event):  # pragma: no cover - UI runtime
        super().paintEvent(event)
        if self.scaled.isNull():
            return
        painter = QPainter(self)
        painter.drawPixmap(self._pixmap_rect().topLeft(), self.scaled)
        if not self.selection.isNull():
            painter.setPen(QPen(Qt.cyan, 2, Qt.SolidLine))
            painter.drawRect(self.selection.normalized())

    def mousePressEvent(self, event):  # pragma: no cover - UI runtime
        if event.button() == Qt.LeftButton:
            self.start = event.pos()
            self.end = event.pos()
            self.selection = QRect(self.start, self.end)
            self.update()

    def mouseMoveEvent(self, event):  # pragma: no cover - UI runtime
        if event.buttons() & Qt.LeftButton:
            self.end = event.pos()
            self.selection = QRect(self.start, self.end).intersected(self._pixmap_rect())
            self.update()

    def mouseReleaseEvent(self, event):  # pragma: no cover - UI runtime
        if event.button() == Qt.LeftButton:
            self.end = event.pos()
            self.selection = QRect(self.start, self.end).normalized().intersected(self._pixmap_rect())
            self.update()

    def normalized_crop_box(self) -> tuple[float, float, float, float] | None:
        rect = self.selection.normalized()
        pix = self._pixmap_rect()
        if rect.isNull() or pix.isNull() or rect.width() < 8 or rect.height() < 8:
            return None
        left = max(0.0, min(1.0, (rect.left() - pix.left()) / pix.width()))
        top = max(0.0, min(1.0, (rect.top() - pix.top()) / pix.height()))
        right = max(0.0, min(1.0, (rect.right() - pix.left()) / pix.width()))
        bottom = max(0.0, min(1.0, (rect.bottom() - pix.top()) / pix.height()))
        if right <= left or bottom <= top:
            return None
        return (left, top, right, bottom)


class ManualCropDialog(QDialog):
    def __init__(self, image_path: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manual Crop OCR Preview")
        self.setMinimumSize(820, 560)
        layout = QVBoxLayout(self)
        help_label = QLabel("Draw a rectangle around map labels/search bars/coordinates, then press OK. The crop stays local and is saved as case evidence.")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        self.image_label = CropImageLabel(Path(image_path))
        layout.addWidget(self.image_label, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def crop_box(self) -> tuple[float, float, float, float] | None:
        return self.image_label.normalized_crop_box()


def select_crop_box(image_path: str | Path, parent=None) -> tuple[float, float, float, float] | None:
    dialog = ManualCropDialog(Path(image_path), parent=parent)
    if dialog.exec_() != QDialog.Accepted:
        return None
    return dialog.crop_box()
