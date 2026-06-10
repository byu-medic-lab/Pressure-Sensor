"""Lightweight plot widgets.

These avoid extra plotting dependencies for the first hardware bring-up stages.
They can be replaced by pyqtgraph later without changing controller logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QLabel, QWidget


class PlotPlaceholder(QLabel):
    def __init__(self, title: str) -> None:
        super().__init__(f"{title}\n(simulated plot surface)")
        self.setMinimumHeight(110)
        self.setStyleSheet("border: 1px solid #b7c0ca; background: #f8fafc; padding: 8px;")


@dataclass(slots=True)
class AveragePressurePoint:
    timestamp: datetime
    pressure_mmhg: float
    label: str


class AveragePressurePlot(QWidget):
    """Draw averaged pressure calibration points and a simple time trendline."""

    def __init__(self) -> None:
        super().__init__()
        self.points: list[AveragePressurePoint] = []
        self.show_trendline = False
        self.setMinimumHeight(170)
        self.setToolTip("A dot appears each time a recording window average is saved; fitting draws the trendline.")

    def add_average_point(self, timestamp: datetime, pressure_mmhg: float, label: str = "") -> None:
        self.points.append(AveragePressurePoint(timestamp=timestamp, pressure_mmhg=pressure_mmhg, label=label))
        self.show_trendline = False
        self.update()

    def draw_trendline(self) -> None:
        self.show_trendline = len(self.points) >= 2
        self.update()

    def clear(self) -> None:
        self.points.clear()
        self.show_trendline = False
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = self.rect()
        painter.fillRect(bounds, QColor("#f8fafc"))
        painter.setPen(QPen(QColor("#b7c0ca"), 1))
        painter.drawRect(bounds.adjusted(0, 0, -1, -1))

        plot = QRectF(bounds).adjusted(52, 18, -20, -38)
        painter.setPen(QPen(QColor("#53606d"), 1))
        painter.drawLine(plot.bottomLeft(), plot.bottomRight())
        painter.drawLine(plot.bottomLeft(), plot.topLeft())
        painter.setFont(QFont("Arial", 9))
        painter.drawText(bounds.adjusted(8, 4, -8, -4), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, "Averaged pressure vs time")

        if not self.points:
            painter.setPen(QColor("#53606d"))
            painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, "No averaged points yet")
            return

        xs = [point.timestamp.timestamp() for point in self.points]
        ys = [point.pressure_mmhg for point in self.points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        if min_x == max_x:
            min_x -= 1
            max_x += 1
        if min_y == max_y:
            min_y -= 1
            max_y += 1
        y_padding = max((max_y - min_y) * 0.12, 1.0)
        min_y -= y_padding
        max_y += y_padding

        def map_point(x_value: float, y_value: float) -> QPointF:
            x = plot.left() + (x_value - min_x) / (max_x - min_x) * plot.width()
            y = plot.bottom() - (y_value - min_y) / (max_y - min_y) * plot.height()
            return QPointF(x, y)

        painter.setPen(QColor("#53606d"))
        painter.drawText(8, int(plot.top()) + 6, f"{max_y:.1f}")
        painter.drawText(8, int(plot.bottom()), f"{min_y:.1f}")
        painter.drawText(int(plot.left()), bounds.bottom() - 12, "start")
        painter.drawText(int(plot.right()) - 26, bounds.bottom() - 12, "latest")

        if self.show_trendline and len(self.points) >= 2:
            slope, intercept = self._time_fit(xs, ys)
            start = map_point(min_x, slope * min_x + intercept)
            end = map_point(max_x, slope * max_x + intercept)
            painter.setPen(QPen(QColor("#d05a28"), 2))
            painter.drawLine(start, end)

        painter.setPen(QPen(QColor("#145c9e"), 1))
        painter.setBrush(QColor("#1f7acb"))
        for point, x_value, y_value in zip(self.points, xs, ys):
            mapped = map_point(x_value, y_value)
            painter.drawEllipse(mapped, 4.5, 4.5)
            if point.label:
                painter.drawText(mapped + QPointF(6, -6), point.label)

    @staticmethod
    def _time_fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        denominator = sum((x - mean_x) ** 2 for x in xs)
        if denominator == 0:
            return 0.0, mean_y
        slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator
        intercept = mean_y - slope * mean_x
        return slope, intercept
