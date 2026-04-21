from __future__ import annotations

from PyQt5.QtCore import QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QFrame, QLabel, QPlainTextEdit, QTextEdit, QVBoxLayout, QWidget


class StatCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, title: str, value: str = "0", subtitle: str = "", chip: str = "Interactive") -> None:
        super().__init__()
        self.setObjectName("StatCard")
        self.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(6)

        accent = QFrame()
        accent.setObjectName("StatCardAccent")

        self.value_label = QLabel(value)
        self.value_label.setObjectName("CardValue")
        self.value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.value_label.setWordWrap(True)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")
        self.title_label.setWordWrap(True)

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("CardSubtext")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setVisible(bool(subtitle))

        self.chip_label = QLabel(chip)
        self.chip_label.setObjectName("CardChip")
        self.chip_label.setVisible(bool(chip))

        layout.addWidget(accent)
        layout.addWidget(self.value_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)
        layout.addStretch(1)
        layout.addWidget(self.chip_label, alignment=Qt.AlignLeft)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)
        length = len(value)
        if length > 28:
            size = 12
        elif length > 20:
            size = 15
        elif length > 12:
            size = 18
        else:
            size = 26
        self.value_label.setStyleSheet(f"font-size: {size}pt; font-weight: 900; color: #ffffff;")

    def set_subtitle(self, text: str) -> None:
        self.subtitle_label.setText(text)
        self.subtitle_label.setVisible(bool(text))

    def set_chip(self, text: str) -> None:
        self.chip_label.setText(text)
        self.chip_label.setVisible(bool(text))


class ResizableImageLabel(QLabel):
    def __init__(self, placeholder: str = "", min_height: int = 260) -> None:
        super().__init__(placeholder)
        self._source_pixmap: QPixmap | None = None
        self._zoom_factor = 1.0
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(min_height)
        self.setWordWrap(True)

    def set_source_pixmap(self, pixmap: QPixmap | None) -> None:
        self._source_pixmap = pixmap if pixmap and not pixmap.isNull() else None
        self._zoom_factor = 1.0
        self._refresh_pixmap(fit=True)

    def clear_source(self, text: str = "") -> None:
        self._source_pixmap = None
        self._zoom_factor = 1.0
        self.clear()
        self.setText(text)

    def zoom_in(self) -> None:
        if self._source_pixmap is None:
            return
        self._zoom_factor = min(5.0, self._zoom_factor * 1.2)
        self._refresh_pixmap()

    def zoom_out(self) -> None:
        if self._source_pixmap is None:
            return
        self._zoom_factor = max(0.15, self._zoom_factor / 1.2)
        self._refresh_pixmap()

    def reset_zoom(self) -> None:
        if self._source_pixmap is None:
            return
        self._zoom_factor = 1.0
        self._refresh_pixmap()

    def fit_to_window(self) -> None:
        if self._source_pixmap is None:
            return
        self._zoom_factor = 1.0
        self._refresh_pixmap(fit=True)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._refresh_pixmap(fit=abs(self._zoom_factor - 1.0) < 0.01)

    def _refresh_pixmap(self, fit: bool = False) -> None:
        if self._source_pixmap is None:
            return
        target = self.size() - QSize(26, 26)
        if target.width() <= 20 or target.height() <= 20:
            return
        base = self._source_pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if fit or abs(self._zoom_factor - 1.0) < 0.01:
            scaled = base
        else:
            w = max(40, int(base.width() * self._zoom_factor))
            h = max(40, int(base.height() * self._zoom_factor))
            scaled = base.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.clear()
        self.setPixmap(scaled)


class TerminalView(QPlainTextEdit):
    def __init__(self, placeholder: str = "") -> None:
        super().__init__()
        self.setReadOnly(True)
        self.setObjectName("TerminalView")
        self.setPlaceholderText(placeholder)
        font = QFont("Consolas")
        if not font.exactMatch():
            font = QFont("Courier New")
        font.setPointSize(10)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setTabStopDistance(32)


class NarrativeView(QTextEdit):
    def __init__(self, placeholder: str = "") -> None:
        super().__init__()
        self.setObjectName("NarrativeView")
        self.setReadOnly(True)
        self.setPlaceholderText(placeholder)
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setFont(QFont("Segoe UI", 10))


class ChartCard(QFrame):
    def __init__(self, title: str, subtitle: str = "") -> None:
        super().__init__()
        self.setObjectName("PanelFrame")
        self._pixmap: QPixmap | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("SectionLabel")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("MutedLabel")
        self.subtitle_label.setWordWrap(True)
        self.image_label = ResizableImageLabel("Chart will appear after evidence is loaded.", min_height=240)
        self.image_label.setObjectName("ChartCanvas")

        layout.addWidget(self.title_label)
        if subtitle:
            layout.addWidget(self.subtitle_label)
        layout.addWidget(self.image_label, 1)

    def set_chart_pixmap(self, pixmap: QPixmap | None, placeholder: str = "Chart unavailable") -> None:
        self._pixmap = pixmap if pixmap and not pixmap.isNull() else None
        if self._pixmap is None:
            self.image_label.clear_source(placeholder)
        else:
            self.image_label.set_source_pixmap(self._pixmap)


class ScoreRing(QWidget):
    def __init__(self, diameter: int = 138) -> None:
        super().__init__()
        self._value = 0
        self._caption = "Evidence Score"
        self._subcaption = "Awaiting selection"
        self.setMinimumSize(diameter, diameter)
        self.setMaximumSize(diameter, diameter)

    def set_value(self, value: int) -> None:
        self._value = max(0, min(100, value))
        self.update()

    def set_caption(self, caption: str, subcaption: str = "") -> None:
        self._caption = caption
        self._subcaption = subcaption
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(10, 10, -10, -10)
        center = rect.center()
        size = min(rect.width(), rect.height())
        ring_rect = QRectF(center.x() - size / 2, center.y() - size / 2, size, size)

        background_pen = QPen(QColor("#14304c"), 10)
        painter.setPen(background_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(ring_rect)

        tone = QColor("#2ed2ff")
        if self._value >= 70:
            tone = QColor("#4be69e")
        elif self._value >= 40:
            tone = QColor("#ffd166")
        elif self._value > 0:
            tone = QColor("#ff8fa4")

        value_pen = QPen(tone, 10)
        value_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(value_pen)
        start_angle = 90 * 16
        span_angle = int(-360 * 16 * (self._value / 100.0))
        painter.drawArc(ring_rect, start_angle, span_angle)

        painter.setPen(QColor("#ffffff"))
        font = QFont("Segoe UI", 22, QFont.Bold)
        painter.setFont(font)
        painter.drawText(ring_rect, Qt.AlignCenter, str(self._value))

        painter.setPen(QColor("#8bb0cb"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Medium))
        label_rect = QRectF(ring_rect.left(), ring_rect.center().y() + 18, ring_rect.width(), 30)
        painter.drawText(label_rect, Qt.AlignHCenter | Qt.AlignTop, self._caption)

        if self._subcaption:
            painter.setPen(QColor("#6f95b4"))
            painter.setFont(QFont("Segoe UI", 7))
            sub_rect = QRectF(ring_rect.left(), ring_rect.center().y() + 34, ring_rect.width(), 24)
            painter.drawText(sub_rect, Qt.AlignHCenter | Qt.AlignTop, self._subcaption)
