"""Add average increasing/decreasing equations to resistance-vs-pressure SVGs.

The script walks a folder such as ``Resistance vs Pressure Graphs``, visits each
subfolder, reads ``plotted_pressure_resistance_points.csv``, and inserts only
equation text into ``resistance_vs_pressure_mmhg.svg``.

It does not draw trendlines. It also skips SVGs that already contain the marker
inserted by this script.
"""

from __future__ import annotations

import argparse
import csv
import html
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean


DEFAULT_ROOT = r"C:\Users\troy\Desktop\BYU-MEDIC LAB\Resistance vs Pressure Graphs"
CSV_NAME = "plotted_pressure_resistance_points.csv"
SVG_NAME = "resistance_vs_pressure_mmhg.svg"
INSERT_MARKER = "average-trendline-equations-added"


@dataclass(frozen=True)
class Point:
    pressure_mmhg: float
    resistance_ohms: float


@dataclass(frozen=True)
class LinearFit:
    slope: float
    intercept: float

    def equation_text(self) -> str:
        sign = "+" if self.intercept >= 0 else "-"
        return f"R = {self.slope:.6g}P {sign} {abs(self.intercept):.6g}"


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
    """Split 0-to-peak-to-0 style data into cycles."""
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


def split_increasing_decreasing(cycle: list[Point]) -> tuple[list[Point], list[Point]]:
    if len(cycle) < 3:
        return cycle, []
    peak_index = max(range(len(cycle)), key=lambda index: cycle[index].pressure_mmhg)
    return cycle[: peak_index + 1], cycle[peak_index:]


def averaged_points(cycles: list[list[Point]], direction: str) -> list[Point]:
    values_by_pressure: dict[float, list[float]] = {}
    for cycle in cycles:
        increasing, decreasing = split_increasing_decreasing(cycle)
        source = increasing if direction == "increasing" else decreasing
        for point in source:
            pressure_key = round(point.pressure_mmhg, 3)
            values_by_pressure.setdefault(pressure_key, []).append(point.resistance_ohms)
    return [
        Point(pressure, fmean(resistances))
        for pressure, resistances in sorted(values_by_pressure.items())
        if resistances
    ]


def fit_linear(points: list[Point]) -> LinearFit | None:
    if len(points) < 2:
        return None
    xs = [point.pressure_mmhg for point in points]
    ys = [point.resistance_ohms for point in points]
    if len(set(xs)) < 2:
        return None
    mean_x = fmean(xs)
    mean_y = fmean(ys)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        return None
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator
    intercept = mean_y - slope * mean_x
    return LinearFit(slope=slope, intercept=intercept)


def build_equation_block(increasing_fit: LinearFit, decreasing_fit: LinearFit, cycles_count: int) -> str:
    inc_text = html.escape(f"Average increasing: {increasing_fit.equation_text()}")
    dec_text = html.escape(f"Average decreasing: {decreasing_fit.equation_text()}")
    count_text = html.escape(f"Computed from {cycles_count} inferred cycle(s)")
    return f"""
  <!-- {INSERT_MARKER} -->
  <g id="{INSERT_MARKER}">
    <rect x="92" y="36" width="510" height="58" rx="4" fill="#f8fafc" fill-opacity="0.86" stroke="#cbd5e1" stroke-width="1"/>
    <text x="106" y="56" font-family="Arial" font-size="12" fill="#22313f">{inc_text}</text>
    <text x="106" y="75" font-family="Arial" font-size="12" fill="#22313f">{dec_text}</text>
    <text x="106" y="90" font-family="Arial" font-size="10" fill="#53606d">{count_text}</text>
  </g>
"""


def svg_already_updated(svg_text: str) -> bool:
    return INSERT_MARKER in svg_text or "Average increasing:" in svg_text and "Average decreasing:" in svg_text


def inject_before_closing_svg(svg_text: str, block: str) -> str:
    closing = svg_text.rfind("</svg>")
    if closing == -1:
        return svg_text + block
    return svg_text[:closing] + block + svg_text[closing:]


def process_folder(folder: Path) -> str:
    csv_path = folder / CSV_NAME
    svg_path = folder / SVG_NAME
    if not csv_path.exists() or not svg_path.exists():
        return "missing files"

    svg_text = svg_path.read_text(encoding="utf-8")
    if svg_already_updated(svg_text):
        return "already had equations"

    points = read_points(csv_path)
    cycles = split_cycles(points)
    increasing_fit = fit_linear(averaged_points(cycles, "increasing"))
    decreasing_fit = fit_linear(averaged_points(cycles, "decreasing"))
    if increasing_fit is None or decreasing_fit is None:
        return "not enough data"

    block = build_equation_block(increasing_fit, decreasing_fit, len(cycles))
    svg_path.write_text(inject_before_closing_svg(svg_text, block), encoding="utf-8")
    return "updated"


def iter_candidate_folders(root: Path) -> list[Path]:
    folders: list[Path] = []
    if (root / CSV_NAME).exists() and (root / SVG_NAME).exists():
        folders.append(root)
    for child in root.rglob(CSV_NAME):
        folder = child.parent
        if (folder / SVG_NAME).exists() and folder not in folders:
            folders.append(folder)
    return sorted(folders)


def main() -> None:
    parser = argparse.ArgumentParser(description="Add average increasing/decreasing equation text to resistance-vs-pressure SVGs.")
    parser.add_argument(
        "root",
        nargs="?",
        default=DEFAULT_ROOT,
        help=f"Root folder containing subfolders. Default: {DEFAULT_ROOT}",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"Could not find folder: {root}")

    folders = iter_candidate_folders(root)
    if not folders:
        print(f"No folders with both {CSV_NAME} and {SVG_NAME} were found under {root}.")
        return

    counts: dict[str, int] = {}
    for folder in folders:
        result = process_folder(folder)
        counts[result] = counts.get(result, 0) + 1
        print(f"{result}: {folder}")
    print("Summary: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))


if __name__ == "__main__":
    main()
