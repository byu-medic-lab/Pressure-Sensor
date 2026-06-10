"""Create a Fluke resistance-vs-time graph with an exponential 3-tau overlay.

This reads CSV files created by ``fluke_resistance_logger.py`` and writes a new
SVG graph. It does not open serial ports and can be run after the logger stops.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from math import exp, isfinite, log
from pathlib import Path
from statistics import fmean


DEFAULT_INPUT_DIR = Path.cwd() / "fluke_logs"
DEFAULT_OUTPUT_SUFFIX = "_with_3tau_decay.svg"


@dataclass(frozen=True)
class ExponentialFit:
    final_value: float
    amplitude: float
    tau_seconds: float
    rmse: float
    elapsed_seconds: float

    def predict(self, seconds: float) -> float:
        return self.final_value + self.amplitude * exp(-seconds / self.tau_seconds)

    @property
    def three_tau_seconds(self) -> float:
        return 3.0 * self.tau_seconds


def resolve_input_path(path_text: str | None) -> Path:
    path = Path(path_text).expanduser() if path_text else DEFAULT_INPUT_DIR
    if path.is_dir():
        matches = sorted(path.glob("fluke_resistance_*.csv"), key=lambda item: item.stat().st_mtime)
        if not matches:
            raise FileNotFoundError(f"No fluke_resistance_*.csv files found in {path}")
        return matches[-1]
    return path


def read_points(path: Path) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        for row in reader:
            time_seconds = row.get("time_seconds")
            resistance = row.get("resistance_ohms")
            if time_seconds in {None, ""} or resistance in {None, ""}:
                continue
            try:
                points.append((float(time_seconds), float(resistance)))
            except ValueError:
                continue
    return points


def fit_exponential(points: list[tuple[float, float]]) -> ExponentialFit | None:
    """Fit y = final + amplitude * exp(-t / tau) using a small search."""
    if len(points) < 6:
        return None
    start_time = points[0][0]
    normalized = [(time_value - start_time, value) for time_value, value in points]
    elapsed = normalized[-1][0]
    if elapsed <= 0:
        return None
    values = [value for _, value in normalized]
    value_range = max(values) - min(values)
    if value_range <= 0:
        return None

    trend = values[-1] - values[0]
    best: ExponentialFit | None = None
    for final_value in final_value_candidates(values, trend):
        signed_offsets = [value - final_value for _, value in normalized]
        sign = 1.0 if fmean(signed_offsets) >= 0 else -1.0
        offsets = [sign * offset for offset in signed_offsets]
        if min(offsets) <= value_range * 1e-9:
            continue

        log_offsets = [log(offset) for offset in offsets]
        mean_time = fmean([time_value for time_value, _ in normalized])
        mean_log = fmean(log_offsets)
        denominator = sum((time_value - mean_time) ** 2 for time_value, _ in normalized)
        if denominator <= 0:
            continue

        slope = sum(
            (time_value - mean_time) * (log_value - mean_log)
            for (time_value, _), log_value in zip(normalized, log_offsets)
        ) / denominator
        if slope >= 0:
            continue

        intercept = mean_log - slope * mean_time
        tau_seconds = -1.0 / slope
        amplitude = sign * exp(intercept)
        if not isfinite(tau_seconds) or tau_seconds <= 0:
            continue

        residuals = [value - (final_value + amplitude * exp(-time_value / tau_seconds)) for time_value, value in normalized]
        rmse = (sum(residual * residual for residual in residuals) / len(residuals)) ** 0.5
        fit = ExponentialFit(
            final_value=final_value,
            amplitude=amplitude,
            tau_seconds=tau_seconds,
            rmse=rmse,
            elapsed_seconds=elapsed,
        )
        if best is None or fit.rmse < best.rmse:
            best = fit
    return best


def final_value_candidates(values: list[float], trend: float) -> list[float]:
    value_min = min(values)
    value_max = max(values)
    value_range = max(value_max - value_min, 1e-12)
    last = values[-1]
    if trend < 0:
        low = value_min - 2.0 * value_range
        high = min(last, value_min - value_range * 0.001)
    else:
        low = max(last, value_max + value_range * 0.001)
        high = value_max + 2.0 * value_range
    if high <= low:
        return []
    return [low + (high - low) * index / 80 for index in range(81)]


def write_svg(path: Path, points: list[tuple[float, float]], fit: ExponentialFit | None) -> None:
    width = 1200
    height = 720
    left = 95
    right = 220
    top = 70
    bottom = 90
    plot_width = width - left - right
    plot_height = height - top - bottom

    if not points:
        body = "<text x='600' y='360' text-anchor='middle'>No resistance samples found</text>"
        path.write_text(svg_document(width, height, body), encoding="utf-8")
        return

    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    if fit is not None:
        curve_times = curve_time_values(min(x_values), max(x_values), 240)
        curve_values = [fit.predict(time_value - min(x_values)) for time_value in curve_times]
        y_values = y_values + curve_values
        if fit.three_tau_seconds <= max(x_values) - min(x_values):
            x_values = x_values + [min(x_values) + fit.three_tau_seconds]

    x_min, x_max = min(x_values), max(x_values)
    y_min, y_max = min(y_values), max(y_values)
    if x_min == x_max:
        x_max = x_min + 1.0
    if y_min == y_max:
        padding = max(abs(y_min) * 0.02, 1.0)
        y_min -= padding
        y_max += padding
    else:
        padding = (y_max - y_min) * 0.08
        y_min -= padding
        y_max += padding

    def sx(value: float) -> float:
        return left + ((value - x_min) / (x_max - x_min)) * plot_width

    def sy(value: float) -> float:
        return top + plot_height - ((value - y_min) / (y_max - y_min)) * plot_height

    raw_line = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in points)
    raw_dots = "\n".join(
        f"<circle cx='{sx(x):.2f}' cy='{sy(y):.2f}' r='2.2' fill='#1f77b4' fill-opacity='0.65' />"
        for x, y in points[:: max(1, len(points) // 450)]
    )

    overlay = ""
    fit_text = "Exponential fit could not be calculated."
    if fit is not None:
        start_x = min(point[0] for point in points)
        end_x = max(point[0] for point in points)
        curve_points = [(time_value, fit.predict(time_value - start_x)) for time_value in curve_time_values(start_x, end_x, 260)]
        curve_line = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in curve_points)
        three_tau_x_value = start_x + fit.three_tau_seconds
        marker = ""
        if x_min <= three_tau_x_value <= x_max:
            marker_x = sx(three_tau_x_value)
            marker = (
                f"<line x1='{marker_x:.2f}' y1='{top}' x2='{marker_x:.2f}' y2='{top + plot_height}' "
                "stroke='#d62728' stroke-width='2' stroke-dasharray='7 6' />"
                f"<text x='{marker_x + 8:.2f}' y='{top + 22}' fill='#d62728'>3 tau = {fit.three_tau_seconds:.2f}s</text>"
            )
        else:
            marker = (
                f"<text x='{left + 18}' y='{top + 24}' fill='#d62728'>"
                f"3 tau = {fit.three_tau_seconds:.2f}s, outside recorded window</text>"
            )
        overlay = f"""
        <polyline points='{curve_line}' fill='none' stroke='#d62728' stroke-width='3.2' stroke-linejoin='round' stroke-linecap='round' />
        {marker}
        """
        fit_text = (
            f"final={fit.final_value:.6g} Ohms, amplitude={fit.amplitude:.6g}, "
            f"tau={fit.tau_seconds:.3f}s, 3 tau={fit.three_tau_seconds:.3f}s, RMSE={fit.rmse:.6g}"
        )

    tick_markup = []
    for tick in axis_ticks(x_min, x_max, 6):
        x = sx(tick)
        tick_markup.append(f"<line x1='{x:.2f}' y1='{top + plot_height}' x2='{x:.2f}' y2='{top + plot_height + 8}' stroke='#5b6775' />")
        tick_markup.append(f"<text x='{x:.2f}' y='{top + plot_height + 34}' text-anchor='middle'>{tick:.1f}</text>")
    for tick in axis_ticks(y_min, y_max, 6):
        y = sy(tick)
        tick_markup.append(f"<line x1='{left - 8}' y1='{y:.2f}' x2='{left}' y2='{y:.2f}' stroke='#5b6775' />")
        tick_markup.append(f"<text x='{left - 14}' y='{y + 5:.2f}' text-anchor='end'>{tick:.6g}</text>")

    body = f"""
    <rect x='0' y='0' width='{width}' height='{height}' fill='#f7f9fb' />
    <text x='{left}' y='42' class='title'>Fluke resistance vs time</text>
    <text x='{left + 430}' y='42' class='small'>{fit_text}</text>
    <line x1='{left}' y1='{top}' x2='{left}' y2='{top + plot_height}' stroke='#334155' stroke-width='2' />
    <line x1='{left}' y1='{top + plot_height}' x2='{left + plot_width}' y2='{top + plot_height}' stroke='#334155' stroke-width='2' />
    {''.join(tick_markup)}
    <polyline points='{raw_line}' fill='none' stroke='#1f77b4' stroke-width='2.2' stroke-linejoin='round' stroke-linecap='round' />
    {raw_dots}
    {overlay}
    <line x1='{left + plot_width + 40}' y1='{top + 30}' x2='{left + plot_width + 78}' y2='{top + 30}' stroke='#1f77b4' stroke-width='3' />
    <text x='{left + plot_width + 88}' y='{top + 35}' class='legend'>Measured</text>
    <line x1='{left + plot_width + 40}' y1='{top + 58}' x2='{left + plot_width + 78}' y2='{top + 58}' stroke='#d62728' stroke-width='3' />
    <text x='{left + plot_width + 88}' y='{top + 63}' class='legend'>Exponential fit</text>
    <line x1='{left + plot_width + 40}' y1='{top + 86}' x2='{left + plot_width + 78}' y2='{top + 86}' stroke='#d62728' stroke-width='2' stroke-dasharray='7 6' />
    <text x='{left + plot_width + 88}' y='{top + 91}' class='legend'>3 tau</text>
    <text x='{left + plot_width / 2:.2f}' y='{height - 28}' text-anchor='middle' class='axis-label'>Time (s)</text>
    <text x='28' y='{top + plot_height / 2:.2f}' text-anchor='middle' class='axis-label' transform='rotate(-90 28 {top + plot_height / 2:.2f})'>Resistance (Ohms)</text>
    """
    path.write_text(svg_document(width, height, body), encoding="utf-8")


def curve_time_values(start: float, end: float, count: int) -> list[float]:
    if count <= 1:
        return [start]
    return [start + (end - start) * index / (count - 1) for index in range(count)]


def axis_ticks(min_value: float, max_value: float, count: int) -> list[float]:
    if count <= 1:
        return [min_value]
    step = (max_value - min_value) / (count - 1)
    return [min_value + step * index for index in range(count)]


def svg_document(width: int, height: int, body: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<style>
text {{ font-family: Arial, Helvetica, sans-serif; fill: #243447; font-size: 18px; }}
.title {{ font-size: 30px; font-weight: 700; }}
.axis-label {{ font-size: 22px; }}
.small {{ font-size: 13px; fill: #53606d; }}
.legend {{ font-size: 15px; }}
</style>
{body}
</svg>
"""


def default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}{DEFAULT_OUTPUT_SUFFIX}")


def create_graph(input_path: Path, output_path: Path) -> None:
    points = read_points(input_path)
    fit = fit_exponential(points)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_svg(output_path, points, fit)
    print(f"Wrote {output_path} from {len(points)} samples.")
    if fit is None:
        print("Exponential fit could not be calculated from this data.")
    else:
        print(f"tau={fit.tau_seconds:.6g}s, 3 tau={fit.three_tau_seconds:.6g}s, final={fit.final_value:.12g}, RMSE={fit.rmse:.6g}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create Fluke resistance-vs-time SVG with exponential decay and 3-tau overlay.")
    parser.add_argument(
        "input",
        nargs="?",
        help="Path to a fluke_resistance_*.csv file or the fluke_logs folder. Defaults to newest CSV in fluke_logs.",
    )
    parser.add_argument("--output", help="Optional SVG output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = resolve_input_path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Could not find {input_path}")
    output_path = Path(args.output).expanduser() if args.output else default_output_path(input_path)
    create_graph(input_path, output_path)


if __name__ == "__main__":
    main()
