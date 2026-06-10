"""Create a standalone hysteresis graph from plotted pressure/resistance points.

Expected input CSV columns:
    average_pressure_mmhg, average_resistance_ohms

The script intentionally uses only the Python standard library so it can run
beside the PyQt GUI without sharing imports, serial ports, or application state.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from time import sleep


INPUT_NAME = "plotted_pressure_resistance_points.csv"
DEFAULT_OUTPUT_NAME = "hysteresis_resistance_pressure.svg"
SKIP_FIRST_CYCLE_OUTPUT_NAME = "hysteresis_resistance_pressure_without_first_cycle.svg"
NORMALIZED_OUTPUT_NAME = "hysteresis_resistance_pressure_normalized.svg"
FIGURE_B_OUTPUT_NAME = "figure_b_normalized_resistance_vs_pressure.svg"
FIGURE_C_OUTPUT_NAME = "figure_c_hysteresis_area_vs_cycle.svg"


@dataclass(frozen=True)
class Point:
    pressure_mmhg: float
    resistance_ohms: float


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


def hysteresis_area(points: list[Point]) -> float | None:
    if len(points) < 3:
        return None
    area = 0.0
    for current, next_point in zip(points, points[1:] + points[:1]):
        area += current.pressure_mmhg * next_point.resistance_ohms
        area -= next_point.pressure_mmhg * current.resistance_ohms
    return abs(area) / 2.0


def cycle_areas(cycles: list[list[Point]]) -> list[tuple[int, float]]:
    areas: list[tuple[int, float]] = []
    for index, cycle in enumerate(cycles, start=1):
        area = hysteresis_area(cycle)
        if area is not None:
            areas.append((index, area))
    return areas


def without_first_cycle(points: list[Point]) -> list[Point]:
    """Return points after the first complete return to the starting pressure."""
    if len(points) < 4:
        return []
    start_pressure = points[0].pressure_mmhg
    pressure_span = max(point.pressure_mmhg for point in points) - min(point.pressure_mmhg for point in points)
    tolerance = max(pressure_span * 0.03, 0.5)
    moved_away = False
    for index, point in enumerate(points[1:], start=1):
        if abs(point.pressure_mmhg - start_pressure) > tolerance:
            moved_away = True
        elif moved_away and abs(point.pressure_mmhg - start_pressure) <= tolerance:
            return points[index:]
    midpoint = max(1, len(points) // 2)
    return points[midpoint:]


def split_cycles(points: list[Point]) -> list[list[Point]]:
    """Split data into cycles using returns to the starting pressure."""
    if len(points) < 4:
        return [points] if points else []
    start_pressure = points[0].pressure_mmhg
    pressure_span = max(point.pressure_mmhg for point in points) - min(point.pressure_mmhg for point in points)
    tolerance = max(pressure_span * 0.03, 0.5)
    cycles: list[list[Point]] = []
    cycle_start = 0
    moved_away = False
    for index, point in enumerate(points[1:], start=1):
        if abs(point.pressure_mmhg - start_pressure) > tolerance:
            moved_away = True
        elif moved_away and abs(point.pressure_mmhg - start_pressure) <= tolerance:
            cycles.append(points[cycle_start : index + 1])
            cycle_start = index
            moved_away = False
    if cycle_start < len(points) - 1:
        cycles.append(points[cycle_start:])
    return [cycle for cycle in cycles if len(cycle) >= 2]


def normalized_cycles(points: list[Point]) -> list[list[Point]]:
    normalized: list[list[Point]] = []
    for cycle in split_cycles(points):
        baseline = cycle[0].resistance_ohms
        normalized.append([Point(point.pressure_mmhg, point.resistance_ohms - baseline) for point in cycle])
    return normalized


def cycle_gray(index: int, count: int) -> str:
    start = 20
    end = 205
    value = round(start + (end - start) * index / max(1, count - 1))
    return f"#{value:02x}{value:02x}{value:02x}"


def smooth_path(points: list[tuple[float, float]]) -> str:
    """Build a Catmull-Rom spline converted to SVG cubic Beziers."""
    if not points:
        return ""
    if len(points) == 1:
        x, y = points[0]
        return f"M {x:.2f} {y:.2f}"
    if len(points) == 2:
        (x1, y1), (x2, y2) = points
        return f"M {x1:.2f} {y1:.2f} L {x2:.2f} {y2:.2f}"
    path = [f"M {points[0][0]:.2f} {points[0][1]:.2f}"]
    extended = [points[0], *points, points[-1]]
    for index in range(1, len(extended) - 2):
        p0 = extended[index - 1]
        p1 = extended[index]
        p2 = extended[index + 1]
        p3 = extended[index + 2]
        c1x = p1[0] + (p2[0] - p0[0]) / 6.0
        c1y = p1[1] + (p2[1] - p0[1]) / 6.0
        c2x = p2[0] - (p3[0] - p1[0]) / 6.0
        c2y = p2[1] - (p3[1] - p1[1]) / 6.0
        path.append(f"C {c1x:.2f} {c1y:.2f}, {c2x:.2f} {c2y:.2f}, {p2[0]:.2f} {p2[1]:.2f}")
    return " ".join(path)


def write_svg(
    points: list[Point],
    output_path: Path,
    title: str = "Resistance vs pressure hysteresis",
    y_axis_label: str = "Resistance (Ohms)",
    cycles_override: list[list[Point]] | None = None,
) -> None:
    width, height = 980, 520
    left, top, right, bottom = 92, 54, 170, 74
    plot_w = width - left - right
    plot_h = height - top - bottom

    cycles = cycles_override if cycles_override is not None else split_cycles(points)
    plot_points = [point for cycle in cycles for point in cycle]

    if plot_points:
        pressures = [point.pressure_mmhg for point in plot_points]
        resistances = [point.resistance_ohms for point in plot_points]
        min_x, max_x = min(pressures), max(pressures)
        min_y, max_y = min(resistances), max(resistances)
        if min_x == max_x:
            min_x -= 1.0
            max_x += 1.0
        if min_y == max_y:
            min_y -= 1.0
            max_y += 1.0
        x_pad = max((max_x - min_x) * 0.08, 1.0)
        y_pad = max((max_y - min_y) * 0.08, 0.001)
        min_x -= x_pad
        max_x += x_pad
        min_y -= y_pad
        max_y += y_pad

        def mapped(point: Point) -> tuple[float, float]:
            x = left + (point.pressure_mmhg - min_x) / (max_x - min_x) * plot_w
            y = top + (max_y - point.resistance_ohms) / (max_y - min_y) * plot_h
            return x, y

        elements: list[str] = []
        legend: list[str] = []
        for cycle_index, cycle in enumerate(cycles):
            color = cycle_gray(cycle_index, len(cycles))
            mapped_cycle = [mapped(point) for point in cycle]
            elements.append(
                f'<path d="{smooth_path(mapped_cycle)}" fill="none" stroke="{color}" '
                'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
            )
            legend_y = top + 24 + cycle_index * 24
            legend.append(
                f'<line x1="{left + plot_w + 24}" y1="{legend_y}" x2="{left + plot_w + 52}" y2="{legend_y}" '
                f'stroke="{color}" stroke-width="3"/>'
            )
            legend.append(
                f'<text x="{left + plot_w + 60}" y="{legend_y + 4}" font-family="Arial" font-size="12" fill="#22313f">'
                f'Cycle {cycle_index + 1}</text>'
            )
        for cycle_index, cycle in enumerate(cycles):
            color = cycle_gray(cycle_index, len(cycles))
            for point_index, point in enumerate(cycle):
                x, y = mapped(point)
                fill = "#22313f" if cycle_index == 0 and point_index == 0 else "#ffffff"
                elements.append(
                    f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3.5" fill="{fill}" '
                    f'stroke="{color}" stroke-width="1.4"/>'
                )

        area = hysteresis_area(plot_points)
        area_text = "" if area is None else f"Hysteresis loop area: {area:.5g} mmHg*Ohm"
        empty = ""
        x_min_text, x_max_text = f"{min_x:.5g}", f"{max_x:.5g}"
        y_min_text, y_max_text = f"{min_y:.5g}", f"{max_y:.5g}"
    else:
        elements = []
        legend = []
        area_text = ""
        empty = '<text x="490" y="260" text-anchor="middle" fill="#53606d">No pressure/resistance points found</text>'
        x_min_text = x_max_text = y_min_text = y_max_text = ""

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#f8fafc"/>
  <text x="{left}" y="30" font-family="Arial" font-size="20" font-weight="700" fill="#22313f">{title}</text>
  <text x="{left + 360}" y="30" font-family="Arial" font-size="12" fill="#53606d">{area_text}</text>
  <line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#53606d"/>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#53606d"/>
  <text x="14" y="{top + 8}" font-family="Arial" font-size="12" fill="#53606d">{y_max_text}</text>
  <text x="14" y="{top + plot_h}" font-family="Arial" font-size="12" fill="#53606d">{y_min_text}</text>
  <text x="{left}" y="{height - 44}" font-family="Arial" font-size="12" fill="#53606d">{x_min_text}</text>
  <text x="{left + plot_w - 48}" y="{height - 44}" font-family="Arial" font-size="12" fill="#53606d">{x_max_text}</text>
  <text x="{left + plot_w / 2}" y="{height - 20}" text-anchor="middle" font-family="Arial" font-size="14" fill="#53606d">Pressure (mmHg)</text>
  <text x="22" y="{top + plot_h / 2}" transform="rotate(-90 22 {top + plot_h / 2})" text-anchor="middle" font-family="Arial" font-size="14" fill="#53606d">{y_axis_label}</text>
  {"".join(elements)}
  {"".join(legend)}
  {empty}
</svg>
"""
    output_path.write_text(svg, encoding="utf-8")


def write_area_svg(areas: list[tuple[int, float]], output_path: Path) -> None:
    width, height = 760, 460
    left, top, right, bottom = 86, 54, 38, 70
    plot_w = width - left - right
    plot_h = height - top - bottom
    if areas:
        xs = [cycle for cycle, _ in areas]
        ys = [area for _, area in areas]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        if min_x == max_x:
            min_x -= 1
            max_x += 1
        if min_y == max_y:
            min_y = 0
            max_y += 1
        y_pad = max((max_y - min_y) * 0.12, 1.0)
        min_y = max(0.0, min_y - y_pad)
        max_y += y_pad

        def mapped(cycle: int, area: float) -> tuple[float, float]:
            x = left + (cycle - min_x) / (max_x - min_x) * plot_w
            y = top + (max_y - area) / (max_y - min_y) * plot_h
            return x, y

        mapped_points = [mapped(cycle, area) for cycle, area in areas]
        polyline = " ".join(f"{x:.2f},{y:.2f}" for x, y in mapped_points)
        elements = [f'<polyline points="{polyline}" fill="none" stroke="#22313f" stroke-width="2.5"/>']
        for cycle, area in areas:
            x, y = mapped(cycle, area)
            elements.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="#ffffff" stroke="#22313f" stroke-width="1.5"/>')
            elements.append(f'<text x="{x:.2f}" y="{y - 8:.2f}" text-anchor="middle" font-family="Arial" font-size="10" fill="#53606d">{area:.3g}</text>')
        empty = ""
        x_min_text, x_max_text = str(min(xs)), str(max(xs))
        y_min_text, y_max_text = f"{min_y:.5g}", f"{max_y:.5g}"
    else:
        elements = []
        empty = '<text x="380" y="230" text-anchor="middle" fill="#53606d">No complete cycles found</text>'
        x_min_text = x_max_text = y_min_text = y_max_text = ""

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#f8fafc"/>
  <text x="{left}" y="30" font-family="Arial" font-size="20" font-weight="700" fill="#22313f">Figure C. Hysteresis area vs cycle number</text>
  <line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#53606d"/>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#53606d"/>
  <text x="14" y="{top + 8}" font-family="Arial" font-size="12" fill="#53606d">{y_max_text}</text>
  <text x="14" y="{top + plot_h}" font-family="Arial" font-size="12" fill="#53606d">{y_min_text}</text>
  <text x="{left}" y="{height - 42}" font-family="Arial" font-size="12" fill="#53606d">{x_min_text}</text>
  <text x="{left + plot_w - 12}" y="{height - 42}" font-family="Arial" font-size="12" fill="#53606d">{x_max_text}</text>
  <text x="{left + plot_w / 2}" y="{height - 18}" text-anchor="middle" font-family="Arial" font-size="14" fill="#53606d">Cycle number</text>
  <text x="22" y="{top + plot_h / 2}" transform="rotate(-90 22 {top + plot_h / 2})" text-anchor="middle" font-family="Arial" font-size="14" fill="#53606d">Hysteresis area (mmHg*Ohm)</text>
  {"".join(elements)}
  {empty}
</svg>
"""
    output_path.write_text(svg, encoding="utf-8")


def create_graph(input_path: Path, output_path: Path) -> None:
    points = read_points(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_svg(points, output_path)
    print(f"Wrote {output_path} from {len(points)} points.")
    skip_output_path = output_path.with_name(SKIP_FIRST_CYCLE_OUTPUT_NAME)
    skip_points = without_first_cycle(points)
    write_svg(skip_points, skip_output_path)
    print(f"Wrote {skip_output_path} from {len(skip_points)} points after removing the first cycle.")
    normalized_output_path = output_path.with_name(NORMALIZED_OUTPUT_NAME)
    normalized = normalized_cycles(points)
    normalized_points = [point for cycle in normalized for point in cycle]
    write_svg(
        normalized_points,
        normalized_output_path,
        title="Normalized resistance vs pressure hysteresis",
        y_axis_label="Resistance change from cycle start (Ohms)",
        cycles_override=normalized,
    )
    print(f"Wrote {normalized_output_path} from {len(normalized_points)} normalized points.")
    figure_b_path = output_path.with_name(FIGURE_B_OUTPUT_NAME)
    write_svg(
        normalized_points,
        figure_b_path,
        title="Figure B. Normalized resistance vs pressure",
        y_axis_label="Resistance change from cycle start (Ohms)",
        cycles_override=normalized,
    )
    print(f"Wrote {figure_b_path} from {len(normalized_points)} normalized points.")
    figure_c_path = output_path.with_name(FIGURE_C_OUTPUT_NAME)
    write_area_svg(cycle_areas(split_cycles(points)), figure_c_path)
    print(f"Wrote {figure_c_path}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a hysteresis graph from plotted pressure/resistance CSV points.")
    parser.add_argument("input", help="Path to plotted_pressure_resistance_points.csv or the run folder containing it.")
    parser.add_argument("--output", help="Optional SVG output path.")
    parser.add_argument("--watch", type=float, default=0.0, help="Regenerate every N seconds until Ctrl+C.")
    args = parser.parse_args()

    input_path = resolve_input_path(args.input)
    output_path = Path(args.output).expanduser() if args.output else input_path.with_name(DEFAULT_OUTPUT_NAME)
    if args.watch and args.watch > 0:
        print(f"Watching {input_path}; writing {output_path}; press Ctrl+C to stop.")
        while True:
            try:
                if input_path.exists():
                    create_graph(input_path, output_path)
                else:
                    print(f"Waiting for {input_path}...")
                sleep(args.watch)
            except KeyboardInterrupt:
                print("Stopped.")
                return
    else:
        if not input_path.exists():
            raise FileNotFoundError(f"Could not find {input_path}")
        create_graph(input_path, output_path)


if __name__ == "__main__":
    main()
