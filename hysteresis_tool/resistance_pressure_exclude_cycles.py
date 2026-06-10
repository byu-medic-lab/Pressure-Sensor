"""Create resistance-vs-pressure graph while excluding selected cycles.

Expected input CSV columns:
    average_pressure_mmhg, average_resistance_ohms

By default this removes cycles 9 and 10, then writes a new SVG beside the CSV.
The script uses only the Python standard library and does not touch the main GUI.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


INPUT_NAME = "plotted_pressure_resistance_points.csv"
DEFAULT_OUTPUT_NAME = "resistance_vs_pressure_mmhg_without_cycles_9_10.svg"


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


def split_cycles(points: list[Point]) -> list[list[Point]]:
    """Split points into cycles using returns to the starting pressure."""
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


def parse_cycle_list(text: str) -> set[int]:
    cycles: set[int] = set()
    for part in text.split(","):
        stripped = part.strip()
        if not stripped:
            continue
        cycles.add(int(stripped))
    return cycles


def cycle_shade(index: int, count: int) -> str:
    start = 0
    end = 205
    value = round(start + (end - start) * index / max(1, count - 1))
    return f"#{value:02x}{value:02x}{value:02x}"


def split_increasing_decreasing(cycle: list[Point]) -> tuple[list[Point], list[Point]]:
    if len(cycle) < 3:
        return cycle, []
    peak_index = max(range(len(cycle)), key=lambda index: cycle[index].pressure_mmhg)
    increasing = cycle[: peak_index + 1]
    decreasing = cycle[peak_index:]
    return increasing, decreasing


def write_svg(path: Path, cycles: list[list[Point]], excluded_cycles: set[int], original_cycle_count: int) -> None:
    width, height = 980, 460
    left, top, right, bottom = 88, 44, 170, 68
    plot_w = width - left - right
    plot_h = height - top - bottom
    points = [point for cycle in cycles for point in cycle]

    if points:
        xs = [point.pressure_mmhg for point in points]
        ys = [point.resistance_ohms for point in points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
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
        for index, cycle in enumerate(cycles):
            color = cycle_shade(index, len(cycles))
            increasing, decreasing = split_increasing_decreasing(cycle)
            for segment, dash in ((increasing, ""), (decreasing, ' stroke-dasharray="8 5"')):
                if len(segment) >= 2:
                    polyline = " ".join(f"{x:.2f},{y:.2f}" for x, y in (mapped(point) for point in segment))
                    elements.append(f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2.5"{dash}/>')
            for point in cycle:
                x, y = mapped(point)
                elements.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="{color}" stroke="#ffffff" stroke-width="1.2"/>')
            legend_y = top + 18 + index * 22
            legend.append(
                f'<line x1="{left + plot_w + 22}" y1="{legend_y}" x2="{left + plot_w + 48}" y2="{legend_y}" '
                f'stroke="{color}" stroke-width="3"/>'
            )
            legend.append(
                f'<text x="{left + plot_w + 56}" y="{legend_y + 4}" font-family="Arial" font-size="11" fill="#22313f">Cycle {index + 1}</text>'
            )
        y_min_text, y_max_text = f"{min_y:.5g}", f"{max_y:.5g}"
        x_min_text, x_max_text = f"{min_x:.5g}", f"{max_x:.5g}"
        empty = ""
    else:
        elements = []
        legend = []
        y_min_text = y_max_text = x_min_text = x_max_text = ""
        empty = '<text x="490" y="230" text-anchor="middle" fill="#53606d">No points remain after excluded cycles</text>'

    excluded_text = ", ".join(str(cycle) for cycle in sorted(excluded_cycles))
    subtitle = f"Excluded original cycle(s): {excluded_text}; inferred {original_cycle_count} total cycle(s)"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#f8fafc"/>
  <text x="{left}" y="26" font-family="Arial" font-size="18" font-weight="700" fill="#22313f">Resistance vs pressure</text>
  <text x="{left + 220}" y="26" font-family="Arial" font-size="12" fill="#53606d">{subtitle}</text>
  <line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#53606d"/>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#53606d"/>
  <text x="14" y="{top + 8}" font-family="Arial" font-size="12" fill="#53606d">{y_max_text}</text>
  <text x="14" y="{top + plot_h}" font-family="Arial" font-size="12" fill="#53606d">{y_min_text}</text>
  <text x="{left}" y="{height - 40}" font-family="Arial" font-size="12" fill="#53606d">{x_min_text}</text>
  <text x="{left + plot_w - 48}" y="{height - 40}" font-family="Arial" font-size="12" fill="#53606d">{x_max_text}</text>
  <text x="{left + plot_w / 2}" y="{height - 18}" text-anchor="middle" font-family="Arial" font-size="14" fill="#53606d">Pressure (mmHg)</text>
  <text x="20" y="{top + plot_h / 2}" transform="rotate(-90 20 {top + plot_h / 2})" text-anchor="middle" font-family="Arial" font-size="14" fill="#53606d">Resistance (Ohms)</text>
  {"".join(elements)}
  {"".join(legend)}
  {empty}
</svg>
"""
    path.write_text(svg, encoding="utf-8")


def create_graph(input_path: Path, output_path: Path, excluded_cycles: set[int]) -> None:
    points = read_points(input_path)
    cycles = split_cycles(points)
    kept_cycles = [cycle for index, cycle in enumerate(cycles, start=1) if index not in excluded_cycles]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_svg(output_path, kept_cycles, excluded_cycles, len(cycles))
    kept_points = sum(len(cycle) for cycle in kept_cycles)
    print(
        f"Wrote {output_path} from {kept_points} points "
        f"after excluding cycle(s) {', '.join(str(cycle) for cycle in sorted(excluded_cycles))}."
    )
    print(f"Inferred {len(cycles)} total cycle(s) from {len(points)} input point(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create resistance_vs_pressure_mmhg graph while excluding selected cycles.")
    parser.add_argument("input", help="Path to plotted_pressure_resistance_points.csv or the run folder containing it.")
    parser.add_argument("--exclude", default="9,10", help="Comma-separated 1-based cycle numbers to remove. Default: 9,10.")
    parser.add_argument("--output", help="Optional SVG output path.")
    args = parser.parse_args()

    input_path = resolve_input_path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Could not find {input_path}")
    excluded_cycles = parse_cycle_list(args.exclude)
    output_path = Path(args.output).expanduser() if args.output else input_path.with_name(DEFAULT_OUTPUT_NAME)
    create_graph(input_path, output_path, excluded_cycles)


if __name__ == "__main__":
    main()
