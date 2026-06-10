# Pressure Sensor Characterization System

This repository contains the software, setup notes, images, and 3D-print files for a lab pressure/resistance characterization system. The system is used to measure how the electrical resistance of a conductive polymer composite sensor changes under controlled pressure.

The main software is a Python desktop GUI built with PyQt6. It controls and records data from:

- A serial pressure sensor that outputs raw integer pressure readings
- A Fluke 8808A digital multimeter measuring resistance
- A New Era NE-500/NE-501 syringe pump over RS-232

The GUI supports pressure calibration, syringe pump movement calibration, automated pressure cycling, CSV logging, and SVG graph generation.

---

## Repository Layout

```text
Pressure-Sensor/
  README.md
  src/
    main.py
    pyproject.toml
    app/
    devices/
    gui/
    protocols/
    tests/
    hysteresis_tool/
    fluke_resistance_logger.py
    fluke_resistance_decay_graph.py
    pump_push_water_10s.py
    add_average_trendline_equations.py
  Instructions/
    Pressure_Resistance_Characterization_Setup.md
    Sensor_Fabrication_Protocol.md
    Sensor_Behavior.md
    Introduction.md
  images/
    Final_Sensor.png
    Fluke_Multimeter.jpg
    Manometer.jpg
    Pressure_Sensor.jpg
    Sensor_Setup.jpg
    Syringe_Pump.jpg
  STL/
    NCCF_Bottom.STL
    NCCF_Top.STL
    Silicone_Bottom.STL
    Silicone_Top.STL
```

The runnable Python project is inside the `src/` folder.

---

## Hardware Used

The software is designed for this lab setup:

- Pressure sensor connected through a serial interface
- Fluke 8808A digital multimeter
- NE-500/NE-501 syringe pump
- USB-to-serial adapters
- Water manometer
- Conductive polymer composite sensor fixture
- 3D printed sensor/test fixture components

The app can also run in simulation mode without hardware, but real data collection requires the devices above and the correct serial ports.

---

## Software Requirements

Install these before running the project:

- Python 3.11 or newer
- Git
- Windows is recommended because the GUI and serial-port workflow were developed and tested on Windows

Python packages are installed from `src/pyproject.toml`:

- PyQt6
- pyserial
- pytest, for running tests

---

## Download The Code From GitHub

Open PowerShell and run:

```powershell
cd "C:\Users\YOUR_USERNAME\Documents"
git clone https://github.com/byu-medic-lab/Pressure-Sensor.git
cd Pressure-Sensor
```

Replace `YOUR_USERNAME` with your Windows username if needed.

---

## Create The Python Environment

From the repository folder:

```powershell
cd src
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

This creates a local virtual environment and installs all required packages.

---

## Run The Tests

From the `src/` folder with the virtual environment activated:

```powershell
python -m pytest
```

All tests should pass before using the GUI for data collection.

---

## Run The Main GUI

From the `src/` folder with the virtual environment activated:

```powershell
python main.py
```

The GUI will open as a desktop application.

---

## Basic GUI Workflow

### 1. Prepare The System

Before starting:

- Select the correct serial port for each device
- Connect and test device communication
- Make sure the pressure system is vented to ambient
- Make sure the pressure sensor reading is stable
- Make sure the Fluke reading is stable
- Remove the water column unless doing manometer calibration
- Place the syringe pump at the known starting position
- Confirm the tubing and fluid path are ready before calibration or automated testing

### 2. Connect Devices

In the **Device connections** section:

- Select the pressure sensor serial port
- Select the Fluke serial port
- Select the syringe pump serial port
- Click **Connect** for each device
- Use **Test** to verify communication

Serial ports are not hardcoded. They must be selected from the dropdowns.

### 3. Calibrate Pressure With The Manometer

In the **Calibration** tab:

1. Enter the manometer pressure point in `cm H2O`
2. Set the recording time
3. Click **Start recording window**
4. The app records pressure samples for the selected time
5. The app averages the window and stores the point
6. The manometer point automatically increases by 10 cm H2O
7. Repeat for all calibration points
8. Click **Fit/save coefficients**

The pressure conversion used by the app is:

```text
mmHg = cmH2O * 0.735559
```

The fitted pressure model is:

```text
pressure_mmhg = slope * raw_pressure_integer + intercept
```

### 4. Calibrate Syringe Pump Movement

In the same **Calibration** tab:

1. Click **Start auto syringe calibration**
2. The app records pressure before movement
3. The pump moves using the fixed calibration sequence
4. The app records pressure after movement
5. The process repeats automatically
6. Click **Fit syringe calibration** when complete

The current fixed syringe calibration sequence uses:

```text
Pump motion time: 5 s
Movement rate: 60 mL/min
Direction: INF first
Average time: 5 s
Cycles: 5 up and 5 back
```

The app fits separate increasing and decreasing pump-response behavior.

### 5. Run Automated Test

In **Run automated test**:

1. Enter an experiment ID
2. Add operator notes
3. Choose an output folder
4. Enter start pressure, stop pressure, pressure interval, and optional cycle count
5. Leave time interval blank to use the automatic 3-tau settling behavior
6. Click **Start automated test**

The app moves to the start pressure before logging begins. During the test it records pressure and resistance at stopped pressure intervals.

---

## Output Files

Each automated run creates a timestamped output folder. The final folder normally contains:

```text
metadata.csv
resistance_vs_pressure_mmhg.svg
resistance_vs_pressure_fits.svg
plotted_pressure_resistance_points.csv
pressure_cm_vs_mmhg_points.csv
```

`metadata.csv` contains run information such as experiment ID, operator notes, serial settings, and calibration coefficients.

`plotted_pressure_resistance_points.csv` contains only:

```text
average_pressure_mmhg
average_resistance_ohms
```

The SVG graphs include equation text for average increasing and decreasing pressure sweeps.

---

## Standalone Scripts

The `src/` folder includes several standalone helper scripts.

### Fluke Resistance Logger

Records Fluke resistance vs time without opening the main GUI:

```powershell
python fluke_resistance_logger.py
```

This creates CSV and SVG files in:

```text
src/fluke_logs/
```

Only one program can use the Fluke COM port at a time. Close or disconnect the main GUI before running this logger.

### Fluke Exponential Decay Graph

Creates a resistance-vs-time graph with an exponential fit and 3-tau marker:

```powershell
python fluke_resistance_decay_graph.py
```

By default it uses the newest CSV in `fluke_logs/`.

### Pump Test Script

Runs the syringe pump for a short timed movement:

```powershell
python pump_push_water_10s.py
```

Only run this when the pump is physically safe to move.

### Add Average Trendline Equations To Existing Graphs

Walks a folder of saved runs and adds increasing/decreasing equation text to existing resistance-vs-pressure SVGs:

```powershell
python add_average_trendline_equations.py
```

### Hysteresis Tools

Additional post-processing tools are in:

```text
src/hysteresis_tool/
```

See:

```text
src/hysteresis_tool/README.md
```

---

## Important Notes

- Do not open PuTTY separately while the GUI is reading the pressure sensor. Only one program should own a serial port at a time.
- Do not run the standalone Fluke logger while the main GUI is connected to the Fluke.
- Do not run pump scripts unless the fluid path is safe and the pump is correctly connected.
- The app timestamps device data as it arrives and correlates pressure/resistance later by timestamp.
- Raw and averaged data are logged to CSV files.
- The GUI is designed so serial I/O runs in worker threads and does not block the interface.

---

## Troubleshooting

### PyQt6 Import Error

If Python cannot import PyQt6, reinstall the project dependencies:

```powershell
cd src
.venv\Scripts\activate
python -m pip install -e ".[test]"
```

### Serial Port Access Denied

This usually means another program is already using the port. Close:

- PuTTY
- The main GUI
- Any standalone logger script
- Any other serial monitor

Then unplug and reconnect the USB-to-serial adapter if needed.

### Fluke Reads Prompt-Only Responses

The software uses `VAL1?` for the Fluke primary display reading. If responses look wrong:

- Confirm the correct COM port
- Confirm the Fluke is set up for remote serial communication
- Confirm the baud rate is 9600
- Confirm the Fluke is in the desired resistance mode

### Pump Does Not Move

Check:

- Correct pump COM port
- Pump power and RS-232 cable
- Baud rate 19200
- Pump address/settings
- Physical syringe setup
- Tubing is not blocked

---

## Development Notes

The code is organized by responsibility:

- `app/` contains controller, calibration, logging, state machine, and analysis logic
- `devices/` contains threaded device workers
- `protocols/` contains serial command/response formatting
- `gui/` contains PyQt6 window and widgets
- `tests/` contains protocol, calibration, logging, and state-machine tests

Run tests after code changes:

```powershell
cd src
.venv\Scripts\activate
python -m pytest
```

---
