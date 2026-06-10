"""Export simple SVG plots from logged rows without external dependencies."""

from __future__ import annotations

from math import sqrt
from pathlib import Path
from typing import Any

from app.calibration import CalibrationStore, fit_linear


def export_run_graphs(
    folder: Path,
    rows: list[dict[str, Any]],
    calibration: CalibrationStore,
    closed_loop_observations: list[dict[str, Any]] | None = None,
    closed_loop_settled_points: list[dict[str, Any]] | None = None,
) -> list[Path]:
    """Write the requested end-of-run SVG graphs into the run folder."""
    folder.mkdir(parents=True, exist_ok=True)
    outputs = []
    settled_points = closed_loop_settled_points or []
    if settled_points:
        outputs.append(_write_grouped_resistance_svg(folder / "resistance_vs_pressure_mmhg.svg", settled_points))
        outputs.append(_write_resistance_fit_svg(folder / "resistance_vs_pressure_fits.svg", settled_points))
    else:
        outputs.append(_write_xy_svg(folder / "resistance_vs_pressure_mmhg.svg", "Resistance vs pressure", "Pressure (mmHg)", "Resistance (Ohms)", _resistance_pressure_points(rows)))
    return outputs


def _pressure_calibration_points(calibration: CalibrationStore) -> list[tuple[float, float]]:
    return [(point.reference_cm_h2o, point.reference_mmhg) for point in calibration.manometer_points]


def _resistance_pressure_points(rows: list[dict[str, Any]]) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for row in rows:
        pressure = row.get("pressure_mmhg")
        resistance = row.get("fluke_resistance_ohms")
        if pressure in {None, ""} or resistance in {None, ""}:
            continue
        points.append((float(pressure), float(resistance)))
    return points


def _settled_resistance_pressure_points(points: list[dict[str, Any]]) -> list[tuple[float, float]]:
    plotted: list[tuple[float, float]] = []
    for point in points:
        pressure = point.get("average_pressure_mmhg")
        resistance = point.get("average_resistance_ohms")
        if pressure in {None, ""} or resistance in {None, ""}:
            continue
        plotted.append((float(pressure), float(resistance)))
    return plotted


def _settled_resistance_pressure_groups(points: list[dict[str, Any]]) -> list[tuple[str, str, list[tuple[float, float]]]]:
    groups: list[tuple[str, str, list[tuple[float, float]]]] = []
    index_by_key: dict[tuple[int, str], int] = {}

    def add_point(half_cycle: int, direction: str, plot_point: tuple[float, float]) -> None:
        key = (half_cycle, direction)
        label = f"{direction} half-cycle {half_cycle + 1}"
        if key not in index_by_key:
            index_by_key[key] = len(groups)
            groups.append((label, direction, []))
        groups[index_by_key[key]][2].append(plot_point)

    valid_points = [
        point
        for point in points
        if point.get("average_pressure_mmhg") not in {None, ""}
        and point.get("average_resistance_ohms") not in {None, ""}
    ]
    for index, point in enumerate(valid_points):
        pressure = point.get("average_pressure_mmhg")
        resistance = point.get("average_resistance_ohms")
        half_cycle = int(point.get("half_cycle_index") or 0)
        direction = str(point.get("sweep_direction") or "unknown")
        plot_point = (float(pressure), float(resistance))
        add_point(half_cycle, direction, plot_point)
        if index + 1 < len(valid_points):
            next_point = valid_points[index + 1]
            next_direction = str(next_point.get("sweep_direction") or "unknown")
            if next_direction != direction:
                next_half_cycle = int(next_point.get("half_cycle_index") or half_cycle + 1)
                add_point(next_half_cycle, next_direction, plot_point)
    return groups


def _settled_points_for_direction(points: list[dict[str, Any]], direction: str) -> list[dict[str, Any]]:
    return [point for point in points if str(point.get("sweep_direction") or "").lower() == direction]


def _cycle_shade(group_index: int, group_count: int) -> str:
    cycle_index = group_index // 2
    cycle_count = max(1, (group_count + 1) // 2)
    start = 0
    end = 205
    value = round(start + (end - start) * cycle_index / max(1, cycle_count - 1))
    return f"#{value:02x}{value:02x}{value:02x}"


def _cycle_label(group_index: int) -> str:
    return f"Cycle {group_index // 2 + 1}"


def _direction_dash(direction: str) -> str:
    return "" if direction == "increasing" else ' stroke-dasharray="8 5"'


def _average_points_for_direction(
    groups: list[tuple[str, str, list[tuple[float, float]]]],
    direction: str,
) -> list[tuple[float, float]]:
    values_by_pressure: dict[float, list[float]] = {}
    for _, group_direction, group_points in groups:
        if group_direction != direction:
            continue
        for pressure, resistance in group_points:
            values_by_pressure.setdefault(round(pressure, 3), []).append(resistance)
    return [
        (pressure, sum(resistances) / len(resistances))
        for pressure, resistances in sorted(values_by_pressure.items())
        if resistances
    ]


def _direction_fit_equations(groups: list[tuple[str, str, list[tuple[float, float]]]]) -> list[str]:
    equations: list[str] = []
    for label, direction in [("Average increasing", "increasing"), ("Average decreasing", "decreasing")]:
        points = _average_points_for_direction(groups, direction)
        if len(points) < 2 or len({point[0] for point in points}) < 2:
            continue
        fit = fit_linear([point[0] for point in points], [point[1] for point in points])
        sign = "+" if fit.intercept >= 0 else "-"
        equations.append(f"{label}: R = {fit.slope:.6g}P {sign} {abs(fit.intercept):.6g}")
    return equations


def _equation_svg_block(left: int, top: int, equations: list[str]) -> str:
    if not equations:
        return ""
    rows = "\n".join(
        f'<text x="{left + 14}" y="{top + 22 + index * 18}" font-family="Arial" font-size="12" fill="#22313f">{equation}</text>'
        for index, equation in enumerate(equations)
    )
    height = 28 + len(equations) * 18
    return f"""
  <g id="average-direction-equations">
    <rect x="{left}" y="{top}" width="465" height="{height}" rx="4" fill="#f8fafc" fill-opacity="0.9" stroke="#cbd5e1" stroke-width="1"/>
    {rows}
  </g>
"""


def _write_svg(path: Path, title: str, y_label: str, points: list[tuple[float, float]]) -> Path:
    width, height = 900, 420
    left, top, right, bottom = 72, 36, 24, 58
    plot_w = width - left - right
    plot_h = height - top - bottom
    if points:
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        if min_x == max_x:
            max_x = min_x + 1
        if min_y == max_y:
            min_y -= 1
            max_y += 1
        y_pad = max((max_y - min_y) * 0.08, 1.0)
        min_y -= y_pad
        max_y += y_pad

        def mapped(point: tuple[float, float]) -> tuple[float, float]:
            x_value, y_value = point
            x = left + (x_value - min_x) / (max_x - min_x) * plot_w
            y = top + (max_y - y_value) / (max_y - min_y) * plot_h
            return x, y

        polyline = " ".join(f"{x:.2f},{y:.2f}" for x, y in map(mapped, points))
        dots = "\n".join(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="#1f7acb" />' for x, y in map(mapped, points))
        empty = ""
        y_min_text, y_max_text = f"{min_y:.3g}", f"{max_y:.3g}"
        x_max_text = f"{max_x:.1f}s"
    else:
        polyline = ""
        dots = ""
        empty = '<text x="450" y="210" text-anchor="middle" fill="#53606d">No data recorded</text>'
        y_min_text = y_max_text = x_max_text = ""

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#f8fafc"/>
  <text x="{left}" y="24" font-family="Arial" font-size="18" font-weight="700" fill="#22313f">{title}</text>
  <line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#53606d"/>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#53606d"/>
  <text x="12" y="{top + 8}" font-family="Arial" font-size="12" fill="#53606d">{y_max_text}</text>
  <text x="12" y="{top + plot_h}" font-family="Arial" font-size="12" fill="#53606d">{y_min_text}</text>
  <text x="{left + plot_w - 40}" y="{height - 20}" font-family="Arial" font-size="12" fill="#53606d">{x_max_text}</text>
  <text x="{left + plot_w / 2}" y="{height - 16}" text-anchor="middle" font-family="Arial" font-size="13" fill="#53606d">time</text>
  <text x="18" y="{top + plot_h / 2}" transform="rotate(-90 18 {top + plot_h / 2})" text-anchor="middle" font-family="Arial" font-size="13" fill="#53606d">{y_label}</text>
  <polyline points="{polyline}" fill="none" stroke="#d05a28" stroke-width="2"/>
  {dots}
  {empty}
</svg>
"""
    path.write_text(svg, encoding="utf-8")
    return path


def _write_xy_svg(path: Path, title: str, x_label: str, y_label: str, points: list[tuple[float, float]]) -> Path:
    width, height = 900, 420
    left, top, right, bottom = 80, 40, 30, 62
    plot_w = width - left - right
    plot_h = height - top - bottom
    fit = None
    residuals: list[float] = []
    if len(points) >= 2 and len({point[0] for point in points}) >= 2:
        fit = fit_linear([point[0] for point in points], [point[1] for point in points])
        residuals = fit.residuals

    if points:
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        if fit is not None:
            ys = ys + [fit.predict(min(xs)), fit.predict(max(xs))]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        if min_x == max_x:
            min_x -= 1
            max_x += 1
        if min_y == max_y:
            min_y -= 1
            max_y += 1
        x_pad = max((max_x - min_x) * 0.08, 1.0)
        y_pad = max((max_y - min_y) * 0.08, 1.0)
        min_x -= x_pad
        max_x += x_pad
        min_y -= y_pad
        max_y += y_pad

        def mapped(point: tuple[float, float]) -> tuple[float, float]:
            x_value, y_value = point
            x = left + (x_value - min_x) / (max_x - min_x) * plot_w
            y = top + (max_y - y_value) / (max_y - min_y) * plot_h
            return x, y

        dots = []
        for point in points:
            x, y = mapped(point)
            dots.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="#1f7acb" />')
        trend = ""
        fit_text = ""
        if fit is not None:
            rmse = sqrt(sum(residual * residual for residual in residuals) / len(residuals))
            fit_text = f"y = {fit.slope:.5g}x + {fit.intercept:.5g}; trendline RMSE = {rmse:.5g}"
        empty = ""
        y_min_text, y_max_text = f"{min_y:.3g}", f"{max_y:.3g}"
        x_min_text, x_max_text = f"{min_x:.3g}", f"{max_x:.3g}"
    else:
        dots = []
        trend = ""
        fit_text = ""
        empty = '<text x="450" y="210" text-anchor="middle" fill="#53606d">No data recorded</text>'
        y_min_text = y_max_text = x_min_text = x_max_text = ""

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#f8fafc"/>
  <text x="{left}" y="24" font-family="Arial" font-size="18" font-weight="700" fill="#22313f">{title}</text>
  <text x="{left + 300}" y="24" font-family="Arial" font-size="12" fill="#53606d">{fit_text}</text>
  <line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#53606d"/>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#53606d"/>
  <text x="12" y="{top + 8}" font-family="Arial" font-size="12" fill="#53606d">{y_max_text}</text>
  <text x="12" y="{top + plot_h}" font-family="Arial" font-size="12" fill="#53606d">{y_min_text}</text>
  <text x="{left}" y="{height - 36}" font-family="Arial" font-size="12" fill="#53606d">{x_min_text}</text>
  <text x="{left + plot_w - 42}" y="{height - 36}" font-family="Arial" font-size="12" fill="#53606d">{x_max_text}</text>
  <text x="{left + plot_w / 2}" y="{height - 16}" text-anchor="middle" font-family="Arial" font-size="13" fill="#53606d">{x_label}</text>
  <text x="18" y="{top + plot_h / 2}" transform="rotate(-90 18 {top + plot_h / 2})" text-anchor="middle" font-family="Arial" font-size="13" fill="#53606d">{y_label}</text>
  {trend}
  {"".join(dots)}
  {empty}
</svg>
"""
    path.write_text(svg, encoding="utf-8")
    return path


def _write_grouped_resistance_svg(path: Path, settled_points: list[dict[str, Any]], title: str = "Resistance vs pressure") -> Path:
    groups = _settled_resistance_pressure_groups(settled_points)
    points = [point for _, _, group_points in groups for point in group_points]
    width, height = 980, 460
    left, top, right, bottom = 88, 44, 170, 68
    plot_w = width - left - right
    plot_h = height - top - bottom
    equations = _direction_fit_equations(groups)

    if points:
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
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

        def mapped(point: tuple[float, float]) -> tuple[float, float]:
            x_value, y_value = point
            x = left + (x_value - min_x) / (max_x - min_x) * plot_w
            y = top + (max_y - y_value) / (max_y - min_y) * plot_h
            return x, y

        elements: list[str] = []
        legend: list[str] = []
        legend_cycles: set[int] = set()
        for index, (label, direction, group_points) in enumerate(groups):
            color = _cycle_shade(index, len(groups))
            mapped_points = [mapped(point) for point in group_points]
            if len(mapped_points) >= 2:
                polyline = " ".join(f"{x:.2f},{y:.2f}" for x, y in mapped_points)
                elements.append(
                    f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2.5"{_direction_dash(direction)}/>'
                )
            for x, y in mapped_points:
                elements.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="{color}" stroke="#ffffff" stroke-width="1.2"/>')
            cycle_index = index // 2
            if cycle_index not in legend_cycles:
                legend_cycles.add(cycle_index)
                legend_y = top + 18 + cycle_index * 22
                legend.append(
                    f'<line x1="{left + plot_w + 22}" y1="{legend_y}" x2="{left + plot_w + 48}" y2="{legend_y}" '
                    f'stroke="{color}" stroke-width="3"/>'
                )
                legend.append(
                    f'<text x="{left + plot_w + 56}" y="{legend_y + 4}" font-family="Arial" font-size="11" fill="#22313f">{_cycle_label(index)}</text>'
                )
        empty = ""
        y_min_text, y_max_text = f"{min_y:.5g}", f"{max_y:.5g}"
        x_min_text, x_max_text = f"{min_x:.5g}", f"{max_x:.5g}"
    else:
        elements = []
        legend = []
        empty = '<text x="490" y="230" text-anchor="middle" fill="#53606d">No stopped average points recorded</text>'
        y_min_text = y_max_text = x_min_text = x_max_text = ""

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#f8fafc"/>
  <text x="{left}" y="26" font-family="Arial" font-size="18" font-weight="700" fill="#22313f">{title}</text>
  <line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#53606d"/>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#53606d"/>
  <text x="14" y="{top + 8}" font-family="Arial" font-size="12" fill="#53606d">{y_max_text}</text>
  <text x="14" y="{top + plot_h}" font-family="Arial" font-size="12" fill="#53606d">{y_min_text}</text>
  <text x="{left}" y="{height - 40}" font-family="Arial" font-size="12" fill="#53606d">{x_min_text}</text>
  <text x="{left + plot_w - 48}" y="{height - 40}" font-family="Arial" font-size="12" fill="#53606d">{x_max_text}</text>
  <text x="{left + plot_w / 2}" y="{height - 18}" text-anchor="middle" font-family="Arial" font-size="14" fill="#53606d">Pressure (mmHg)</text>
  <text x="20" y="{top + plot_h / 2}" transform="rotate(-90 20 {top + plot_h / 2})" text-anchor="middle" font-family="Arial" font-size="14" fill="#53606d">Resistance (Ohms)</text>
  {"".join(elements)}
  {_equation_svg_block(left + 10, top + 8, equations)}
  {"".join(legend)}
  {empty}
</svg>
"""
    path.write_text(svg, encoding="utf-8")
    return path


def _write_resistance_fit_svg(path: Path, settled_points: list[dict[str, Any]]) -> Path:
    groups = _settled_resistance_pressure_groups(settled_points)
    points = [point for _, _, group_points in groups for point in group_points]
    width, height = 980, 500
    left, top, right, bottom = 88, 44, 220, 68
    plot_w = width - left - right
    plot_h = height - top - bottom
    equations = _direction_fit_equations(groups)

    if points:
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
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

        elements: list[str] = []
        empty = ""
        y_min_text, y_max_text = f"{min_y:.5g}", f"{max_y:.5g}"
        x_min_text, x_max_text = f"{min_x:.5g}", f"{max_x:.5g}"
    else:
        elements = []
        empty = '<text x="490" y="250" text-anchor="middle" fill="#53606d">No stopped average points recorded</text>'
        y_min_text = y_max_text = x_min_text = x_max_text = ""

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#f8fafc"/>
  <text x="{left}" y="26" font-family="Arial" font-size="18" font-weight="700" fill="#22313f">Resistance vs pressure fits</text>
  <line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#53606d"/>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#53606d"/>
  <text x="14" y="{top + 8}" font-family="Arial" font-size="12" fill="#53606d">{y_max_text}</text>
  <text x="14" y="{top + plot_h}" font-family="Arial" font-size="12" fill="#53606d">{y_min_text}</text>
  <text x="{left}" y="{height - 40}" font-family="Arial" font-size="12" fill="#53606d">{x_min_text}</text>
  <text x="{left + plot_w - 48}" y="{height - 40}" font-family="Arial" font-size="12" fill="#53606d">{x_max_text}</text>
  <text x="{left + plot_w / 2}" y="{height - 18}" text-anchor="middle" font-family="Arial" font-size="14" fill="#53606d">Pressure (mmHg)</text>
  <text x="20" y="{top + plot_h / 2}" transform="rotate(-90 20 {top + plot_h / 2})" text-anchor="middle" font-family="Arial" font-size="14" fill="#53606d">Resistance (Ohms)</text>
  {"".join(elements)}
  {_equation_svg_block(left + 10, top + 8, equations)}
  {empty}
</svg>
"""
    path.write_text(svg, encoding="utf-8")
    return path
