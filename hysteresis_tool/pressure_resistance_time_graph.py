"""Create a dual-axis pressure/resistance sequence graph from plotted points.

Expected input CSV columns:
    average_pressure_mmhg, average_resistance_ohms

Because the plotted-points CSV does not include timestamps, the x-axis is the
point number in collection order.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


INPUT_NAME = "plotted_pressure_resistance_points.csv"
DEFAULT_OUTPUT_NAME = "pressure_resistance_over_points.svg"


@dataclass(frozen=True)
class Point:
    index: int
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
                points.append(Point(len(points) + 1, float(pressure), float(resistance)))
            except ValueError:
                continue
    return points


def padded_range(values: list[float], minimum_pad: float) -> tuple[float, float]:
    low = min(values)
    high = max(values)
    if low == high:
        low -= minimum_pad
        high += minimum_pad
    pad = max((high - low) * 0.08, minimum_pad)
    return low - pad, high + pad


def write_svg(points: list[Point], output_path: Path) -> None:
    width, height = 1040, 520
    left, top, right, bottom = 86, 58, 92, 72
    plot_w = width - left - right
    plot_h = height - top - bottom

    if points:
        min_x, max_x = 1, max(point.index for point in points)
        if min_x == max_x:
            max_x += 1
        min_pressure, max_pressure = padded_range([point.pressure_mmhg for point in points], 1.0)
        min_resistance, max_resistance = padded_range([point.resistance_ohms for point in points], 0.001)

        def x_map(index: int) -> float:
            return left + (index - min_x) / (max_x - min_x) * plot_w

        def pressure_y(value: float) -> float:
            return top + (max_pressure - value) / (max_pressure - min_pressure) * plot_h

        def resistance_y(value: float) -> float:
            return top + (max_resistance - value) / (max_resistance - min_resistance) * plot_h

        pressure_polyline = " ".join(f"{x_map(point.index):.2f},{pressure_y(point.pressure_mmhg):.2f}" for point in points)
        resistance_polyline = " ".join(f"{x_map(point.index):.2f},{resistance_y(point.resistance_ohms):.2f}" for point in points)
        pressure_dots = "\n".join(
            f'<circle cx="{x_map(point.index):.2f}" cy="{pressure_y(point.pressure_mmhg):.2f}" r="3" fill="#1f77b4"/>'
            for point in points
        )
        resistance_dots = "\n".join(
            f'<circle cx="{x_map(point.index):.2f}" cy="{resistance_y(point.resistance_ohms):.2f}" r="3" fill="#d95f02"/>'
            for point in points
        )
        empty = ""
        x_min_text, x_max_text = str(min_x), str(max_x)
        pressure_min_text, pressure_max_text = f"{min_pressure:.5g}", f"{max_pressure:.5g}"
        resistance_min_text, resistance_max_text = f"{min_resistance:.5g}", f"{max_resistance:.5g}"
    else:
        pressure_polyline = resistance_polyline = ""
        pressure_dots = resistance_dots = ""
        empty = '<text x="520" y="260" text-anchor="middle" fill="#53606d">No pressure/resistance points found</text>'
        x_min_text = x_max_text = pressure_min_text = pressure_max_text = resistance_min_text = resistance_max_text = ""

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#f8fafc"/>
  <text x="{left}" y="32" font-family="Arial" font-size="20" font-weight="700" fill="#22313f">Pressure and resistance over collected points</text>
  <line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#53606d"/>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#1f77b4"/>
  <line x1="{left + plot_w}" y1="{top}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#d95f02"/>
  <text x="14" y="{top + 8}" font-family="Arial" font-size="12" fill="#1f77b4">{pressure_max_text}</text>
  <text x="14" y="{top + plot_h}" font-family="Arial" font-size="12" fill="#1f77b4">{pressure_min_text}</text>
  <text x="{left + plot_w + 16}" y="{top + 8}" font-family="Arial" font-size="12" fill="#d95f02">{resistance_max_text}</text>
  <text x="{left + plot_w + 16}" y="{top + plot_h}" font-family="Arial" font-size="12" fill="#d95f02">{resistance_min_text}</text>
  <text x="{left}" y="{height - 42}" font-family="Arial" font-size="12" fill="#53606d">{x_min_text}</text>
  <text x="{left + plot_w - 12}" y="{height - 42}" font-family="Arial" font-size="12" fill="#53606d">{x_max_text}</text>
  <text x="{left + plot_w / 2}" y="{height - 18}" text-anchor="middle" font-family="Arial" font-size="14" fill="#53606d">Collected point number</text>
  <text x="22" y="{top + plot_h / 2}" transform="rotate(-90 22 {top + plot_h / 2})" text-anchor="middle" font-family="Arial" font-size="14" fill="#1f77b4">Pressure (mmHg)</text>
  <text x="{width - 22}" y="{top + plot_h / 2}" transform="rotate(90 {width - 22} {top + plot_h / 2})" text-anchor="middle" font-family="Arial" font-size="14" fill="#d95f02">Resistance (Ohms)</text>
  <polyline points="{pressure_polyline}" fill="none" stroke="#1f77b4" stroke-width="2.5"/>
  <polyline points="{resistance_polyline}" fill="none" stroke="#d95f02" stroke-width="2.5"/>
  {pressure_dots}
  {resistance_dots}
  <line x1="{left + plot_w - 190}" y1="{top + 22}" x2="{left + plot_w - 160}" y2="{top + 22}" stroke="#1f77b4" stroke-width="3"/>
  <text x="{left + plot_w - 152}" y="{top + 26}" font-family="Arial" font-size="12" fill="#22313f">Pressure</text>
  <line x1="{left + plot_w - 190}" y1="{top + 46}" x2="{left + plot_w - 160}" y2="{top + 46}" stroke="#d95f02" stroke-width="3"/>
  <text x="{left + plot_w - 152}" y="{top + 50}" font-family="Arial" font-size="12" fill="#22313f">Resistance</text>
  {empty}
</svg>
"""
    output_path.write_text(svg, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a dual-axis pressure/resistance graph from plotted points.")
    parser.add_argument("input", help="Path to plotted_pressure_resistance_points.csv or the run folder containing it.")
    parser.add_argument("--output", help="Optional SVG output path.")
    args = parser.parse_args()

    input_path = resolve_input_path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Could not find {input_path}")
    output_path = Path(args.output).expanduser() if args.output else input_path.with_name(DEFAULT_OUTPUT_NAME)
    points = read_points(input_path)
    write_svg(points, output_path)
    print(f"Wrote {output_path} from {len(points)} points.")


if __name__ == "__main__":
    main()
