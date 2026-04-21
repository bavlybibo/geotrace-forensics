from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class StatCard(QFrame):
    def __init__(self, title: str, value: str = "0") -> None:
        super().__init__()
        self.setObjectName("StatCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 14)
        layout.setSpacing(10)

        accent = QFrame()
        accent.setObjectName("StatCardAccent")

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(16, 2, 16, 0)
        inner_layout.setSpacing(6)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("CardValue")
        self.value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.value_label.setWordWrap(True)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")
        self.title_label.setWordWrap(True)

        inner_layout.addWidget(self.value_label)
        inner_layout.addWidget(self.title_label)

        layout.addWidget(accent)
        layout.addWidget(inner)
        layout.addStretch(1)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)
        length = len(value)
        if length > 28:
            self.value_label.setStyleSheet("font-size: 16pt; font-weight: 900; color: #ffffff;")
        elif length > 16:
            self.value_label.setStyleSheet("font-size: 18pt; font-weight: 900; color: #ffffff;")
        else:
            self.value_label.setStyleSheet("font-size: 22pt; font-weight: 900; color: #ffffff;")
