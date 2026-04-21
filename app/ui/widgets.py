from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


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
            size = 20
        else:
            size = 26
        self.value_label.setStyleSheet(f"font-size: {size}pt; font-weight: 900; color: #ffffff;")


class ChartCard(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("PanelFrame")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("SectionLabel")
        self.image_label = QLabel("Chart will appear after evidence is loaded.")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(220)
        self.image_label.setObjectName("ChartCanvas")
        self.caption = QLabel("")
        self.caption.setObjectName("MutedLabel")
        self.caption.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(self.image_label, 1)
        layout.addWidget(self.caption)
