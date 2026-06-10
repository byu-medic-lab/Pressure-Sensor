"""Reusable GUI widgets."""

from __future__ import annotations

from PyQt6.QtGui import QDoubleValidator, QIntValidator
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget


class StatusIndicator(QWidget):
    """Simple colored text status indicator."""

    def __init__(self, label: str) -> None:
        super().__init__()
        self.text = QLabel(label)
        self.state = QLabel("Disconnected")
        self.state.setStyleSheet("color: #9b1c1c; font-weight: 600;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.text)
        layout.addWidget(self.state)

    def set_connected(self, connected: bool) -> None:
        self.state.setText("Connected" if connected else "Disconnected")
        self.state.setStyleSheet(f"color: {'#167a3d' if connected else '#9b1c1c'}; font-weight: 600;")


def make_button(text: str, tooltip: str) -> QPushButton:
    button = QPushButton(text)
    button.setToolTip(tooltip)
    return button


class NumberInput(QLineEdit):
    """Compact numeric input with a spinbox-like value API."""

    def __init__(self, value: float = 0.0, decimals: int = 3) -> None:
        super().__init__()
        self._decimals = decimals
        self._minimum = float("-inf")
        self._maximum = float("inf")
        validator = QDoubleValidator(self)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        validator.setDecimals(decimals)
        self.setValidator(validator)
        self.setValue(value)

    def setRange(self, minimum: float, maximum: float) -> None:  # noqa: N802 - Qt-like API
        self._minimum = minimum
        self._maximum = maximum
        validator = self.validator()
        if isinstance(validator, QDoubleValidator):
            validator.setBottom(minimum)
            validator.setTop(maximum)

    def setDecimals(self, decimals: int) -> None:  # noqa: N802 - Qt-like API
        self._decimals = decimals
        validator = self.validator()
        if isinstance(validator, QDoubleValidator):
            validator.setDecimals(decimals)

    def setSuffix(self, suffix: str) -> None:  # noqa: N802 - compatibility no-op
        self.setPlaceholderText(suffix.strip())

    def setValue(self, value: float) -> None:  # noqa: N802 - Qt-like API
        value = max(self._minimum, min(self._maximum, float(value)))
        self.setText(f"{value:.{self._decimals}f}")

    def value(self) -> float:
        try:
            return float(self.text())
        except ValueError:
            return 0.0


class IntegerInput(QLineEdit):
    """Compact integer input with a spinbox-like value API."""

    def __init__(self, value: int = 0) -> None:
        super().__init__()
        self._minimum = -2147483648
        self._maximum = 2147483647
        self.setValidator(QIntValidator(self))
        self.setValue(value)

    def setRange(self, minimum: int, maximum: int) -> None:  # noqa: N802
        self._minimum = minimum
        self._maximum = maximum
        validator = self.validator()
        if isinstance(validator, QIntValidator):
            validator.setBottom(minimum)
            validator.setTop(maximum)

    def setValue(self, value: int) -> None:  # noqa: N802
        value = max(self._minimum, min(self._maximum, int(value)))
        self.setText(str(value))

    def value(self) -> int:
        try:
            return int(self.text())
        except ValueError:
            return 0
