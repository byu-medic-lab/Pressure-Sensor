"""Calibration point storage, fitting, residuals, and timestamp correlation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from statistics import fmean


CM_H2O_TO_MMHG = 0.735559


@dataclass(slots=True)
class LinearFit:
    slope: float
    intercept: float
    residuals: list[float]

    def predict(self, x: float) -> float:
        return self.slope * x + self.intercept


@dataclass(slots=True)
class ManometerPoint:
    timestamp: datetime
    reference_cm_h2o: float
    reference_mmhg: float
    raw_values: list[int]
    average_raw: float


@dataclass(slots=True)
class SyringePoint:
    timestamp: datetime
    cycle_index: int
    direction: str
    rate_setting: float
    movement_seconds: float
    before_average_raw: float
    after_average_raw: float
    before_pressure_mmhg: float
    after_pressure_mmhg: float
    delta_pressure_mmhg: float
    cumulative_motion_seconds: float | None = None

    @property
    def signed_motion_seconds(self) -> float:
        sign = 1.0 if self.direction.upper() == "INF" else -1.0
        return sign * self.movement_seconds


@dataclass(slots=True)
class CalibrationStore:
    manometer_points: list[ManometerPoint] = field(default_factory=list)
    syringe_points: list[SyringePoint] = field(default_factory=list)
    pressure_fit: LinearFit | None = None
    syringe_fit: LinearFit | None = None
    syringe_increasing_fit: LinearFit | None = None
    syringe_decreasing_fit: LinearFit | None = None

    def add_manometer_window(self, timestamp: datetime, reference_cm_h2o: float, raw_values: list[int]) -> ManometerPoint:
        if not raw_values:
            raise ValueError("Cannot calibrate from an empty recording window.")
        point = ManometerPoint(
            timestamp=timestamp,
            reference_cm_h2o=reference_cm_h2o,
            reference_mmhg=reference_cm_h2o * CM_H2O_TO_MMHG,
            raw_values=list(raw_values),
            average_raw=fmean(raw_values),
        )
        self.manometer_points.append(point)
        return point

    def fit_pressure(self) -> LinearFit:
        fit = fit_linear(
            [point.average_raw for point in self.manometer_points],
            [point.reference_mmhg for point in self.manometer_points],
        )
        self.pressure_fit = fit
        return fit

    def convert_raw_pressure(self, raw_value: int | float) -> float | None:
        if self.pressure_fit is None:
            return None
        return max(0.0, self.pressure_fit.predict(float(raw_value)))

    def add_syringe_movement_point(
        self,
        timestamp: datetime,
        movement_seconds: float,
        direction: str,
        rate_setting: float,
        before_raw_values: list[int],
        after_raw_values: list[int],
        cycle_index: int = 0,
        cumulative_motion_seconds: float | None = None,
    ) -> SyringePoint:
        if not before_raw_values or not after_raw_values:
            raise ValueError("Syringe movement calibration needs before and after pressure recording windows.")
        if movement_seconds <= 0:
            raise ValueError("Pump movement time must be positive.")
        before_average = fmean(before_raw_values)
        after_average = fmean(after_raw_values)
        before_pressure = self.convert_raw_pressure(before_average)
        after_pressure = self.convert_raw_pressure(after_average)
        if before_pressure is None or after_pressure is None:
            raise ValueError("Pressure calibration is required before syringe calibration.")
        point = SyringePoint(
            timestamp=timestamp,
            cycle_index=cycle_index,
            direction=direction.upper(),
            rate_setting=rate_setting,
            movement_seconds=movement_seconds,
            before_average_raw=before_average,
            after_average_raw=after_average,
            before_pressure_mmhg=before_pressure,
            after_pressure_mmhg=after_pressure,
            delta_pressure_mmhg=after_pressure - before_pressure,
            cumulative_motion_seconds=cumulative_motion_seconds,
        )
        self.syringe_points.append(point)
        return point

    def add_syringe_point(self, timestamp: datetime, volume_ml: float, average_raw: float) -> SyringePoint:
        """Backward-compatible helper for older manual volume tests."""
        return self.add_syringe_movement_point(timestamp, volume_ml, "INF", 0.0, [average_raw], [average_raw])

    def fit_syringe(self) -> LinearFit:
        if any(point.cumulative_motion_seconds is None for point in self.syringe_points):
            raise ValueError("Syringe calibration points need cumulative pump motion time.")
        fit = fit_linear(
            [point.cumulative_motion_seconds for point in self.syringe_points if point.cumulative_motion_seconds is not None],
            [point.after_pressure_mmhg for point in self.syringe_points],
        )
        self.syringe_fit = fit
        self.syringe_increasing_fit = self._fit_syringe_direction(increasing=True)
        self.syringe_decreasing_fit = self._fit_syringe_direction(increasing=False)
        return fit

    def _fit_syringe_direction(self, increasing: bool) -> LinearFit | None:
        points = [
            point
            for point in self.syringe_points
            if point.cumulative_motion_seconds is not None
            and ((point.delta_pressure_mmhg >= 0) if increasing else (point.delta_pressure_mmhg < 0))
        ]
        if len(points) < 2:
            return None
        try:
            return fit_linear(
                [point.cumulative_motion_seconds for point in points if point.cumulative_motion_seconds is not None],
                [point.after_pressure_mmhg for point in points],
            )
        except ValueError:
            return None

    def fit_for_pressure_delta(self, delta_mmhg: float) -> LinearFit | None:
        """Return the syringe timing fit that matches the desired pressure direction."""
        if delta_mmhg > 0 and self.syringe_increasing_fit is not None:
            return self.syringe_increasing_fit
        if delta_mmhg < 0 and self.syringe_decreasing_fit is not None:
            return self.syringe_decreasing_fit
        return self.syringe_fit

    def motion_seconds_for_pressure_delta(self, delta_mmhg: float) -> float | None:
        """Return signed pump motion seconds for a requested pressure change."""
        fit = self.fit_for_pressure_delta(delta_mmhg)
        if fit is None:
            return None
        if fit.slope == 0:
            raise ValueError("Syringe calibration slope is zero; cannot compute pump motion time.")
        return delta_mmhg / fit.slope

    def movement_for_pressure_delta(self, delta_mmhg: float, syringe_diameter_mm: float | None = None) -> float | None:
        """Return signed motion seconds for compatibility with older call sites."""
        return self.motion_seconds_for_pressure_delta(delta_mmhg)


def fit_linear(xs: list[float], ys: list[float]) -> LinearFit:
    """Fit y = slope*x + intercept using ordinary least squares."""
    if len(xs) != len(ys):
        raise ValueError("x and y lengths must match.")
    if len(xs) < 2:
        raise ValueError("At least two points are required for a linear fit.")
    mean_x = fmean(xs)
    mean_y = fmean(ys)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        raise ValueError("Cannot fit a line when all x values are identical.")
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator
    intercept = mean_y - slope * mean_x
    residuals = [y - (slope * x + intercept) for x, y in zip(xs, ys)]
    return LinearFit(slope=slope, intercept=intercept, residuals=residuals)


def nearest_neighbor_merge(
    pressure_rows: list[tuple[datetime, float]],
    resistance_rows: list[tuple[datetime, float]],
) -> list[tuple[datetime, float, float | None]]:
    """Attach nearest resistance value to each pressure row by timestamp."""
    if not resistance_rows:
        return [(ts, pressure, None) for ts, pressure in pressure_rows]
    merged: list[tuple[datetime, float, float | None]] = []
    for pressure_ts, pressure in pressure_rows:
        nearest = min(resistance_rows, key=lambda row: abs((row[0] - pressure_ts).total_seconds()))
        merged.append((pressure_ts, pressure, nearest[1]))
    return merged
