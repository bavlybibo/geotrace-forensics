from __future__ import annotations

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import QFrame, QLabel, QPlainTextEdit, QVBoxLayout


class StatCard(QFrame):
    def __init__(self, title: str, value: str = "0") -> None:
        super().__init__()
        self.setObjectName("StatCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(8)

        accent = QFrame()
        accent.setObjectName("StatCardAccent")

        self.value_label = QLabel(value)
        self.value_label.setObjectName("CardValue")
        self.value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.value_label.setWordWrap(True)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")
        self.title_label.setWordWrap(True)

        layout.addWidget(accent)
        layout.addWidget(self.value_label)
        layout.addWidget(self.title_label)
        layout.addStretch(1)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)
        length = len(value)
        if length > 28:
            size = 13
        elif length > 20:
            size = 16
        elif length > 12:
            size = 19
        else:
            size = 26
        self.value_label.setStyleSheet(f"font-size: {size}pt; font-weight: 900; color: #ffffff;")


class ResizableImageLabel(QLabel):
    def __init__(self, placeholder: str = "", min_height: int = 260) -> None:
        super().__init__(placeholder)
        self._source_pixmap: QPixmap | None = None
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(min_height)
        self.setWordWrap(True)

    def set_source_pixmap(self, pixmap: QPixmap | None) -> None:
        self._source_pixmap = pixmap if pixmap and not pixmap.isNull() else None
        self._refresh_pixmap()

    def clear_source(self, text: str = "") -> None:
        self._source_pixmap = None
        self.clear()
        self.setText(text)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._refresh_pixmap()

    def _refresh_pixmap(self) -> None:
        if self._source_pixmap is None:
            return
        target = self.size() - QSize(24, 24)
        scaled = self._source_pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
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


class ChartCard(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("PanelFrame")
        self._pixmap: QPixmap | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("SectionLabel")
        self.image_label = ResizableImageLabel("Chart will appear after evidence is loaded.", min_height=260)
        self.image_label.setObjectName("ChartCanvas")
        self.caption = QLabel("")
        self.caption.setObjectName("MutedLabel")
        self.caption.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(self.image_label, 1)
        layout.addWidget(self.caption)

    def set_chart_pixmap(self, pixmap: QPixmap | None, placeholder: str = "Chart unavailable") -> None:
        self._pixmap = pixmap if pixmap and not pixmap.isNull() else None
        if self._pixmap is None:
            self.image_label.clear_source(placeholder)
        else:
            self.image_label.set_source_pixmap(self._pixmap)
