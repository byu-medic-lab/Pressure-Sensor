# Hysteresis Graph Tool

Standalone tool for creating a resistance-vs-pressure hysteresis graph from:

```text
plotted_pressure_resistance_points.csv
```

It does not import or control the calibration GUI, does not open serial ports, and only reads the CSV file you give it.

## Run

From this folder:

```powershell
python hysteresis_graph.py "C:\path\to\run_folder\plotted_pressure_resistance_points.csv"
```

Or pass the run folder itself:

```powershell
python hysteresis_graph.py "C:\path\to\run_folder"
```

By default it writes:

```text
hysteresis_resistance_pressure.svg
hysteresis_resistance_pressure_without_first_cycle.svg
hysteresis_resistance_pressure_normalized.svg
figure_b_normalized_resistance_vs_pressure.svg
figure_c_hysteresis_area_vs_cycle.svg
```

next to the input CSV.

## Optional Output Path

```powershell
python hysteresis_graph.py "C:\path\to\plotted_pressure_resistance_points.csv" --output "C:\path\to\hysteresis.svg"
```

## Watch Mode

To keep regenerating the graph while a CSV is updated:

```powershell
python hysteresis_graph.py "C:\path\to\run_folder" --watch 10
```

That refreshes every 10 seconds. The tool still only reads the input file and writes its own SVG.

## Pressure And Resistance Over Points

To create a dual-axis graph with pressure and resistance as separate lines:

```powershell
python pressure_resistance_time_graph.py "C:\path\to\run_folder"
```

It writes:

```text
pressure_resistance_over_points.svg
```

## Staircase Range Graphs

To compare the first and second staircase blocks for 0-50, 0-100, and 0-150:

```powershell
python staircase_range_graphs.py "C:\path\to\run_folder"
```

It writes:

```text
staircase_0_50_comparison.svg
staircase_0_100_comparison.svg
staircase_0_150_comparison.svg
staircase_0_50_comparison_normalized.svg
staircase_0_100_comparison_normalized.svg
staircase_0_150_comparison_normalized.svg
```

In each graph, the first three cycles for that range are red, the later three cycles are blue, increasing pressure is solid, and decreasing pressure is dashed.

## Resistance Vs Pressure Without Cycles 9 And 10

To recreate the resistance-vs-pressure graph while removing cycles 9 and 10:

```powershell
python resistance_pressure_exclude_cycles.py "C:\path\to\run_folder"
```

It writes:

```text
resistance_vs_pressure_mmhg_without_cycles_9_10.svg
```

You can remove different cycles by changing the comma-separated list:

```powershell
python resistance_pressure_exclude_cycles.py "C:\path\to\run_folder" --exclude 2,7
```
