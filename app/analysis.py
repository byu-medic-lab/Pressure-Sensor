"""Analysis helpers for timestamp-based post-processing and settling fits."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, isfinite, log
from statistics import fmean

from app.calibration import nearest_neighbor_merge


@dataclass(slots=True)
class ExponentialSettlingFit:
    final_value: float
    amplitude: float
    tau_seconds: float
    rmse: float
    sample_count: int
    elapsed_seconds: float

    def predict(self, seconds: float) -> float:
        return self.final_value + self.amplitude * exp(-seconds / self.tau_seconds)

    @property
    def three_tau_seconds(self) -> float:
        return 3.0 * self.tau_seconds


def fit_exponential_settling(samples: list[tuple[float, float]]) -> ExponentialSettlingFit | None:
    """Fit y = final + amplitude * exp(-t / tau) using a small dependency-free search."""
    if len(samples) < 6:
        return None
    start_time = samples[0][0]
    normalized = [(time_value - start_time, value) for time_value, value in samples]
    elapsed = normalized[-1][0]
    if elapsed <= 0:
        return None
    values = [value for _, value in normalized]
    value_range = max(values) - min(values)
    if value_range <= 0:
        return None
    trend = values[-1] - values[0]
    final_candidates = _final_value_candidates(values, trend)
    best: ExponentialSettlingFit | None = None
    for final_value in final_candidates:
        signed_offsets = [value - final_value for _, value in normalized]
        sign = 1.0 if fmean(signed_offsets) >= 0 else -1.0
        offsets = [sign * offset for offset in signed_offsets]
        if min(offsets) <= value_range * 1e-6:
            continue
        log_offsets = [log(offset) for offset in offsets]
        mean_t = fmean([time_value for time_value, _ in normalized])
        mean_log = fmean(log_offsets)
        denominator = sum((time_value - mean_t) ** 2 for time_value, _ in normalized)
        if denominator <= 0:
            continue
        slope = sum((time_value - mean_t) * (log_value - mean_log) for (time_value, _), log_value in zip(normalized, log_offsets)) / denominator
        if slope >= 0:
            continue
        intercept = mean_log - slope * mean_t
        tau_seconds = -1.0 / slope
        amplitude = sign * exp(intercept)
        if not isfinite(tau_seconds) or tau_seconds <= 0:
            continue
        residuals = [value - (final_value + amplitude * exp(-time_value / tau_seconds)) for time_value, value in normalized]
        rmse = (sum(residual * residual for residual in residuals) / len(residuals)) ** 0.5
        fit = ExponentialSettlingFit(
            final_value=final_value,
            amplitude=amplitude,
            tau_seconds=tau_seconds,
            rmse=rmse,
            sample_count=len(samples),
            elapsed_seconds=elapsed,
        )
        if best is None or fit.rmse < best.rmse:
            best = fit
    return best


def _final_value_candidates(values: list[float], trend: float) -> list[float]:
    value_min = min(values)
    value_max = max(values)
    value_range = max(value_max - value_min, 1e-9)
    last = values[-1]
    if trend < 0:
        low = value_min - 2.0 * value_range
        high = min(last, value_min - value_range * 0.001)
    else:
        low = max(last, value_max + value_range * 0.001)
        high = value_max + 2.0 * value_range
    if high <= low:
        return []
    return [low + (high - low) * index / 40 for index in range(41)]


__all__ = ["ExponentialSettlingFit", "fit_exponential_settling", "nearest_neighbor_merge"]
