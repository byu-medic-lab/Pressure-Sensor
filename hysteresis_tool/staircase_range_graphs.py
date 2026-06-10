"""Create staircase conditioning comparison graphs.

Expected input CSV columns:
    average_pressure_mmhg, average_resistance_ohms

The tool infers 0->peak->0 cycles from the pressure sequence and creates
separate resistance-vs-pressure SVGs for 0-50, 0-100, and 0-150 ranges.
For ranges that appear twice in the staircase, the first block is red and the
second block is blue. Increasing pressure is solid; decreasing pressure is
dashed.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


INPUT_NAME = "plotted_pressure_resistance_points.csv"
RANGES = [50.0, 100.0, 150.0]


@dataclass(frozen=True)
class Point:
    pressure_mmhg: float
    resistance_ohms: float


@dataclass(frozen=True)
class Cycle:
    peak_mmhg: float
    points: list[Point]


@dataclass(frozen=True)
class LinearFit:
    slope: float
    intercept: float

    def predict(self, pressure: float) -> float:
        return self.slope * pressure + self.intercept


@dataclass(frozen=True)
class EquationTrace:
    label: str
    color: str
    dashed: bool
    averaged_points: list[Point]
    fit: LinearFit | None


def resolve_input_path(path_text: str) -> Path:
    path = Path(path_text).expanduser()
    if path.is_dir():
        path = path / INPUT_NAME
    return path


def read_points(path: Path) -> list[Point]:
    points: list[Point] = []
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        for row in reader:
            pressure = row.get("average_pressure_mmhg")
            resistance = row.get("average_resistance_ohms")
            if pressure in {None, ""} or resistance in {None, ""}:
                continue
            try:
                points.append(Point(float(pressure), float(resistance)))
            except ValueError:
                continue
    return points


def infer_cycles(points: list[Point]) -> list[Cycle]:
    if len(points) < 3:
        return []
    pressure_span = max(point.pressure_mmhg for point in points) - min(point.pressure_mmhg for point in points)
    zero_tolerance = max(pressure_span * 0.02, 1.0)
    cycles: list[Cycle] = []
    start = 0
    moved_away = False
    for index, point in enumerate(points[1:], start=1):
        if abs(point.pressure_mmhg) > zero_tolerance:
            moved_away = True
        elif moved_away and abs(point.pressure_mmhg) <= zero_tolerance:
            cycle_points = points[start : index + 1]
            peak = max(point.pressure_mmhg for point in cycle_points)
            cycles.append(Cycle(peak_mmhg=peak, points=cycle_points))
            start = index
            moved_away = False
    return cycles


def nearest_range(peak: float) -> float | None:
    nearest = min(RANGES, key=lambda value: abs(value - peak))
    return nearest if abs(nearest - peak) <= 12.0 else None


def cycles_by_range(cycles: list[Cycle]) -> dict[float, list[Cycle]]:
    grouped = {range_peak: [] for range_peak in RANGES}
    for cycle in cycles:
        range_peak = nearest_range(cycle.peak_mmhg)
        if range_peak is not None:
            grouped[range_peak].append(cycle)
    return grouped


def mapped_path(points: list[tuple[float, float]]) -> str:
    if len(points) < 2:
        return ""
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)


def split_increasing_decreasing(points: list[Point]) -> tuple[list[Point], list[Point]]:
    if not points:
        return [], []
    peak_index = max(range(len(points)), key=lambda index: points[index].pressure_mmhg)
    increasing = points[: peak_index + 1]
    decreasing = points[peak_index:]
    return increasing, decreasing


def fit_line(points: list[Point]) -> LinearFit | None:
    if len(points) < 2:
        return None
    xs = [point.pressure_mmhg for point in points]
    ys = [point.resistance_ohms for point in points]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        return None
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator
    return LinearFit(slope=slope, intercept=mean_y - slope * mean_x)


def averaged_trace(cycles: list[Cycle], direction: str) -> list[Point]:
    by_pressure: dict[float, list[float]] = {}
    for cycle in cycles:
        increasing, decreasing = split_increasing_decreasing(cycle.points)
        source = increasing if direction == "increasing" else decreasing
        for point in source:
            pressure_key = round(point.pressure_mmhg, 3)
            by_pressure.setdefault(pressure_key, []).append(point.resistance_ohms)
    return [
        Point(pressure, sum(values) / len(values))
        for pressure, values in sorted(by_pressure.items())
        if values
    ]


def equation_traces(cycles: list[Cycle]) -> list[EquationTrace]:
    specs = [
        ("First increasing", cycles[:3], "increasing", "#d62728", False),
        ("First decreasing", cycles[:3], "decreasing", "#d62728", True),
        ("Second increasing", cycles[3:6], "increasing", "#1f77b4", False),
        ("Second decreasing", cycles[3:6], "decreasing", "#1f77b4", True),
    ]
    traces: list[EquationTrace] = []
    for label, source_cycles, direction, color, dashed in specs:
        points = averaged_trace(source_cycles, direction)
        traces.append(EquationTrace(label=label, color=color, dashed=dashed, averaged_points=points, fit=fit_line(points)))
    return traces


def normalize_cycles(cycles: list[Cycle]) -> list[Cycle]:
    normalized: list[Cycle] = []
    for cycle in cycles:
        if not cycle.points:
            continue
        baseline = cycle.points[0].resistance_ohms
        normalized.append(
            Cycle(
                peak_mmhg=cycle.peak_mmhg,
                points=[Point(point.pressure_mmhg, point.resistance_ohms - baseline) for point in cycle.points],
            )
        )
    return normalized


def write_range_svg(
    range_peak: float,
    cycles: list[Cycle],
    output_path: Path,
    title_suffix: str = "staircase comparison",
    y_axis_label: str = "Resistance (Ohms)",
) -> None:
    width, height = 980, 520
    left, top, right, bottom = 90, 54, 185, 74
    plot_w = width - left - right
    plot_h = height - top - bottom

    all_points = [point for cycle in cycles for point in cycle.points]
    if all_points:
        min_x, max_x = min(point.pressure_mmhg for point in all_points), max(point.pressure_mmhg for point in all_points)
        min_y, max_y = min(point.resistance_ohms for point in all_points), max(point.resistance_ohms for point in all_points)
        if min_x == max_x:
            min_x -= 1
            max_x += 1
        if min_y == max_y:
            min_y -= 1
            max_y += 1
        x_pad = max((max_x - min_x) * 0.08, 1.0)
        y_pad = max((max_y - min_y) * 0.08, 0.001)
        min_x -= x_pad
        max_x += x_pad
        min_y -= y_pad
        max_y += y_pad

        def map_point(point: Point) -> tuple[float, float]:
            x = left + (point.pressure_mmhg - min_x) / (max_x - min_x) * plot_w
            y = top + (max_y - point.resistance_ohms) / (max_y - min_y) * plot_h
            return x, y

        traces = equation_traces(cycles)
        fit_values = [
            trace.fit.predict(point.pressure_mmhg)
            for trace in traces
            if trace.fit is not None
            for point in trace.averaged_points
        ]
        if fit_values:
            min_y = min(min_y, min(fit_values))
            max_y = max(max_y, max(fit_values))

        elements: list[str] = []
        for index, cycle in enumerate(cycles):
            block_color = "#d62728" if index < 3 else "#1f77b4"
            increasing, decreasing = split_increasing_decreasing(cycle.points)
            inc_path = mapped_path([map_point(point) for point in increasing])
            dec_path = mapped_path([map_point(point) for point in decreasing])
            if inc_path:
                elements.append(f'<polyline points="{inc_path}" fill="none" stroke="{block_color}" stroke-width="2.5"/>')
            if dec_path:
                elements.append(
                    f'<polyline points="{dec_path}" fill="none" stroke="{block_color}" stroke-width="2.5" stroke-dasharray="8 5"/>'
                )
            for point in cycle.points:
                x, y = map_point(point)
                elements.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3.5" fill="#ffffff" stroke="{block_color}" stroke-width="1.2"/>')
        equation_elements: list[str] = []
        equation_text: list[str] = []
        for index, trace in enumerate(traces):
            if trace.fit is None or not trace.averaged_points:
                equation_text.append(
                    f'<text x="{left + plot_w + 24}" y="{top + 142 + index * 20}" font-family="Arial" font-size="10" fill="#53606d">{trace.label}: insufficient data</text>'
                )
                continue
            min_pressure = min(point.pressure_mmhg for point in trace.averaged_points)
            max_pressure = max(point.pressure_mmhg for point in trace.averaged_points)
            x1, y1 = map_point(Point(min_pressure, trace.fit.predict(min_pressure)))
            x2, y2 = map_point(Point(max_pressure, trace.fit.predict(max_pressure)))
            dash = ' stroke-dasharray="8 5"' if trace.dashed else ""
            equation_elements.append(
                f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                f'stroke="{trace.color}" stroke-width="4" stroke-opacity="0.55"{dash}/>'
            )
            equation_text.append(
                f'<text x="{left + plot_w + 24}" y="{top + 142 + index * 20}" font-family="Arial" font-size="10" fill="#22313f">'
                f'{trace.label}: R = {trace.fit.slope:.5g}P + {trace.fit.intercept:.5g}</text>'
            )
        empty = ""
        x_min_text, x_max_text = f"{min_x:.5g}", f"{max_x:.5g}"
        y_min_text, y_max_text = f"{min_y:.5g}", f"{max_y:.5g}"
    else:
        elements = []
        equation_elements = []
        equation_text = []
        empty = f'<text x="490" y="260" text-anchor="middle" fill="#53606d">No 0-{range_peak:.0f} staircase cycles found</text>'
        x_min_text = x_max_text = y_min_text = y_max_text = ""

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#f8fafc"/>
  <text x="{left}" y="30" font-family="Arial" font-size="20" font-weight="700" fill="#22313f">0-{range_peak:.0f} mmHg {title_suffix}</text>
  <line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#53606d"/>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#53606d"/>
  <text x="14" y="{top + 8}" font-family="Arial" font-size="12" fill="#53606d">{y_max_text}</text>
  <text x="14" y="{top + plot_h}" font-family="Arial" font-size="12" fill="#53606d">{y_min_text}</text>
  <text x="{left}" y="{height - 44}" font-family="Arial" font-size="12" fill="#53606d">{x_min_text}</text>
  <text x="{left + plot_w - 48}" y="{height - 44}" font-family="Arial" font-size="12" fill="#53606d">{x_max_text}</text>
  <text x="{left + plot_w / 2}" y="{height - 20}" text-anchor="middle" font-family="Arial" font-size="14" fill="#53606d">Pressure (mmHg)</text>
  <text x="22" y="{top + plot_h / 2}" transform="rotate(-90 22 {top + plot_h / 2})" text-anchor="middle" font-family="Arial" font-size="14" fill="#53606d">{y_axis_label}</text>
  {"".join(equation_elements)}
  {"".join(elements)}
  <line x1="{left + plot_w + 24}" y1="{top + 24}" x2="{left + plot_w + 56}" y2="{top + 24}" stroke="#d62728" stroke-width="3"/>
  <text x="{left + plot_w + 64}" y="{top + 28}" font-family="Arial" font-size="12" fill="#22313f">First 3 cycles</text>
  <line x1="{left + plot_w + 24}" y1="{top + 48}" x2="{left + plot_w + 56}" y2="{top + 48}" stroke="#1f77b4" stroke-width="3"/>
  <text x="{left + plot_w + 64}" y="{top + 52}" font-family="Arial" font-size="12" fill="#22313f">Second 3 cycles</text>
  <line x1="{left + plot_w + 24}" y1="{top + 78}" x2="{left + plot_w + 56}" y2="{top + 78}" stroke="#22313f" stroke-width="3"/>
  <text x="{left + plot_w + 64}" y="{top + 82}" font-family="Arial" font-size="12" fill="#22313f">Increasing</text>
  <line x1="{left + plot_w + 24}" y1="{top + 102}" x2="{left + plot_w + 56}" y2="{top + 102}" stroke="#22313f" stroke-width="3" stroke-dasharray="8 5"/>
  <text x="{left + plot_w + 64}" y="{top + 106}" font-family="Arial" font-size="12" fill="#22313f">Decreasing</text>
  {"".join(equation_text)}
  {empty}
</svg>
"""
    output_path.write_text(svg, encoding="utf-8")


def create_graphs(input_path: Path, output_folder: Path) -> None:
    points = read_points(input_path)
    cycles = infer_cycles(points)
    grouped = cycles_by_range(cycles)
    output_folder.mkdir(parents=True, exist_ok=True)
    for range_peak in RANGES:
        output_path = output_folder / f"staircase_0_{int(range_peak)}_comparison.svg"
        write_range_svg(range_peak, grouped[range_peak], output_path)
        print(f"Wrote {output_path} from {len(grouped[range_peak])} inferred cycles.")
        normalized_output_path = output_folder / f"staircase_0_{int(range_peak)}_comparison_normalized.svg"
        normalized_cycles = normalize_cycles(grouped[range_peak])
        write_range_svg(
            range_peak,
            normalized_cycles,
            normalized_output_path,
            title_suffix="normalized staircase comparison",
            y_axis_label="Resistance change from cycle start (Ohms)",
        )
        print(f"Wrote {normalized_output_path} from {len(normalized_cycles)} normalized inferred cycles.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create staircase comparison graphs from plotted pressure/resistance points.")
    parser.add_argument("input", help="Path to plotted_pressure_resistance_points.csv or the run folder containing it.")
    parser.add_argument("--output-folder", help="Optional folder for SVG outputs. Defaults to the input CSV folder.")
    args = parser.parse_args()

    input_path = resolve_input_path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Could not find {input_path}")
    output_folder = Path(args.output_folder).expanduser() if args.output_folder else input_path.parent
    create_graphs(input_path, output_folder)


if __name__ == "__main__":
    main()
