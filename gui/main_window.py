"""Main PyQt6 window for Stage 1 simulation mode."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean
from time import monotonic

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.analysis import ExponentialSettlingFit, fit_exponential_settling
from app.config import discover_serial_ports
from app.controller import AppController
from app.messages import CommandType, DeviceMessage, DeviceSource, MessageType
from app.power_management import clear_keep_awake, keep_system_awake
from app.state_machine import AppMode, AppState
from gui.tooltips import TOOLTIPS
from gui.widgets import IntegerInput, NumberInput


@dataclass
class DeviceControls:
    port: QComboBox
    baud: QSpinBox
    connect: QPushButton
    disconnect: QPushButton
    test: QPushButton
    status: QLabel


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.setWindowTitle("Lab Pressure and Strain Calibrator - layout v2")
        self.setMinimumSize(1280, 800)
        self.device_controls: dict[DeviceSource, DeviceControls] = {}
        self.raw_window_values: list[int] = []
        self.syringe_before_values: list[int] | None = None
        self.syringe_after_values: list[int] | None = None
        self.auto_syringe_active = False
        self.auto_syringe_cycle = 0
        self.auto_syringe_total_cycles = 0
        self.auto_syringe_total_moves = 0
        self.auto_syringe_base_direction = "INF"
        self.auto_syringe_current_direction = "INF"
        self.auto_syringe_cumulative_motion_seconds = 0.0
        self.recording_window_active = False
        self.recording_window_kind = "manometer"
        self.manometer_record_seconds: NumberInput | None = None
        self.closed_loop_preposition_active = False
        self.automated_test_active = False
        self.automated_test_logging_started = False
        self.automated_test_target_pressure: float | None = None
        self.automated_test_targets: list[float] = []
        self.automated_test_target_index = 0
        self.automated_test_staircase_mode = False
        self.automated_test_direction = 1
        self.automated_test_cycle = 0
        self.automated_test_cycle_limit: int | None = None
        self.automated_test_half_cycle_index = 0
        self.automated_test_phase = "idle"
        self.automated_test_stop_requested = False
        self.automated_test_segment_active = False
        self.automated_test_segment_target_pressure: float | None = None
        self.automated_test_segment_direction = 0
        self.automated_test_pump_motion_sign = 0
        self.automated_test_segment_cross_count = 0
        self.automated_test_segment_away_count = 0
        self.automated_test_move_id = 0
        self.automated_test_runtime_slope: float | None = None
        self.automated_test_runtime_increasing_slope: float | None = None
        self.automated_test_runtime_decreasing_slope: float | None = None
        self.automated_test_segment_start_pressure: float | None = None
        self.automated_test_segment_final_target: float | None = None
        self.automated_test_segment_start_time: float | None = None
        self.automated_test_segment_planned_seconds = 0.0
        self.automated_test_segment_requested_delta = 0.0
        self.automated_test_pressure_response_delay_seconds = 2.0
        self.automated_test_settling_active = False
        self.automated_test_settling_target: float | None = None
        self.automated_test_settling_pressure_samples: list[tuple[float, float]] = []
        self.automated_test_settling_resistance_samples: list[tuple[float, float]] = []
        self.automated_test_settling_started_at: datetime | None = None
        self.automated_test_settling_started_monotonic: float | None = None
        self.automated_test_settling_timer = QTimer(self)
        self.automated_test_settling_timer.setInterval(500)
        self.automated_test_settling_timer.timeout.connect(self._check_automated_auto_settle)
        self.automated_test_auto_settle_min_seconds = 5.0
        self.automated_test_auto_settle_max_seconds = 60.0
        self.automated_test_started_monotonic: float | None = None
        self.automated_test_estimated_total_seconds: float | None = None
        self.pressure_watchdog_last_raw: int | None = None
        self.pressure_watchdog_last_sample_time: float | None = None
        self.pressure_watchdog_last_change_time: float | None = None
        self.pressure_watchdog_halted = False
        self.estimate_timer = QTimer(self)
        self.estimate_timer.setInterval(1000)
        self.estimate_timer.timeout.connect(self._update_estimated_duration)
        self.pressure_watchdog_timer = QTimer(self)
        self.pressure_watchdog_timer.setInterval(1000)
        self.pressure_watchdog_timer.timeout.connect(self._check_pressure_watchdog)
        self._build_ui()
        self._connect_signals()
        self.refresh_ports()
        QTimer.singleShot(500, self._auto_connect_and_start_acquisition)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(self._startup_instructions())
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(self._device_panel(), 2)
        top.addWidget(self._live_readout_panel(), 2)
        layout.addLayout(top)
        middle = QHBoxLayout()
        middle.setSpacing(8)
        middle.addWidget(self._calibration_panel(), 3)
        middle.addWidget(self._logging_panel(), 2)
        layout.addLayout(middle, 6)
        layout.addWidget(self._status_panel(), 1)
        self.setCentralWidget(root)

    def _startup_instructions(self) -> QGroupBox:
        group = QGroupBox("Startup instructions")
        text = QLabel(
            "Before starting: select the correct serial port for each device, then connect and test communication. "
            "Make sure the pressure system is vented to ambient, the pressure sensor reading is stable, and the "
            "Fluke reading is stable. Remove the water column unless you are doing manometer calibration. Place the "
            "syringe pump at the known starting position and confirm the tubing/fluid path is ready before calibration "
            "or automated testing."
        )
        text.setWordWrap(True)
        layout = QVBoxLayout(group)
        layout.addWidget(text)
        return group

    def _device_panel(self) -> QGroupBox:
        group = QGroupBox("Device connections")
        layout = QGridLayout(group)
        self.refresh_button = QPushButton("Refresh ports")
        self.refresh_button.setToolTip(TOOLTIPS["refresh_ports"])
        layout.addWidget(self.refresh_button, 0, 0, 1, 6)
        rows = [
            (DeviceSource.PRESSURE, "Pressure sensor", 115200),
            (DeviceSource.FLUKE, "Fluke 8808A", 9600),
            (DeviceSource.PUMP, "NE-500/501 pump", 19200),
        ]
        for row, (source, label, baud) in enumerate(rows, start=1):
            layout.addWidget(QLabel(label), row, 0)
            port = QComboBox()
            port.setToolTip(TOOLTIPS["port"])
            baud_box = QSpinBox()
            baud_box.setRange(1200, 1000000)
            baud_box.setValue(baud)
            baud_box.setToolTip(TOOLTIPS["baud"])
            connect = QPushButton("Connect")
            connect.setToolTip(TOOLTIPS["connect"])
            disconnect = QPushButton("Disconnect")
            disconnect.setToolTip(TOOLTIPS["disconnect"])
            test = QPushButton("Test")
            test.setToolTip(TOOLTIPS["test_connection"])
            status = QLabel("Disconnected")
            status.setStyleSheet("color: #9b1c1c; font-weight: 600;")
            layout.addWidget(port, row, 1)
            layout.addWidget(baud_box, row, 2)
            layout.addWidget(connect, row, 3)
            layout.addWidget(disconnect, row, 4)
            layout.addWidget(test, row, 5)
            layout.addWidget(status, row, 6)
            self.device_controls[source] = DeviceControls(port, baud_box, connect, disconnect, test, status)
        return group

    def _live_readout_panel(self) -> QGroupBox:
        group = QGroupBox("Live readouts")
        form = QFormLayout(group)
        self.raw_value = QLabel("--")
        self.raw_average = QLabel("--")
        self.pressure_value = QLabel("Calibration unavailable")
        self.resistance_value = QLabel("--")
        self.fluke_raw_response = QLabel("--")
        self.fluke_raw_response.setWordWrap(True)
        self.pump_state = QLabel("--")
        for widget in [
            self.raw_value,
            self.raw_average,
            self.pressure_value,
            self.resistance_value,
            self.fluke_raw_response,
            self.pump_state,
        ]:
            widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Raw PuTTY integer", self.raw_value)
        form.addRow("Live recording average", self.raw_average)
        form.addRow("Converted pressure (mmHg)", self.pressure_value)
        form.addRow("Fluke resistance (ohms)", self.resistance_value)
        form.addRow("Fluke raw serial", self.fluke_raw_response)
        form.addRow("Pump state", self.pump_state)
        return group

    def _calibration_panel(self) -> QGroupBox:
        group = QGroupBox("Calibration controls")
        group.setStyleSheet(
            """
            QGroupBox {
                font-size: 12px;
            }
            QLabel {
                font-size: 11px;
            }
            QLineEdit, QComboBox {
                font-size: 11px;
                min-height: 24px;
                max-height: 28px;
                padding-left: 5px;
                padding-right: 5px;
            }
            QPushButton {
                font-size: 11px;
                min-height: 28px;
                max-height: 32px;
            }
            QTextEdit {
                font-size: 11px;
            }
            """
        )
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 12, 10, 8)
        layout.setSpacing(6)
        self.calibration_level = NumberInput(decimals=2)
        self.calibration_level.setRange(0, 500)
        self.calibration_level.setValue(10)
        self.calibration_level.setSuffix(" cm H2O")
        self.calibration_level.setToolTip(TOOLTIPS["calibration_level"])
        self.manometer_record_seconds = NumberInput(decimals=1)
        self.manometer_record_seconds.setRange(0.5, 600)
        self.manometer_record_seconds.setValue(5)
        self.manometer_record_seconds.setSuffix(" s")
        self.manometer_record_seconds.setToolTip(
            "Seconds to record pressure samples after pressing Start recording window before automatically averaging."
        )
        self.record_window_start = QPushButton("Start recording window")
        self.record_window_start.setToolTip("Collect pressure samples for the configured time, then automatically average and save.")
        self.fit_button = QPushButton("Fit/save coefficients")
        self.fit_button.setToolTip(TOOLTIPS["fit_coefficients"])
        self.syringe_motion_seconds = NumberInput(decimals=2)
        self.syringe_motion_seconds.setRange(0.1, 600)
        self.syringe_motion_seconds.setValue(5)
        self.syringe_motion_seconds.setSuffix(" s")
        self.syringe_motion_seconds.setToolTip("How long the pump runs for each calibration movement.")
        self.pump_rate = NumberInput(decimals=3)
        self.pump_rate.setRange(0.001, 1000)
        self.pump_rate.setValue(60)
        self.pump_rate.setSuffix(" mL/min")
        self.pump_rate.setToolTip("Pump rate used for calibration and later testing. Keep this exact rate for pressure prediction.")
        self.pump_direction = QComboBox()
        self.pump_direction.addItems(["INF", "WDR"])
        self.pump_direction.setToolTip("INF pushes fluid out; WDR withdraws fluid into the syringe.")
        self.syringe_record_seconds = NumberInput(decimals=1)
        self.syringe_record_seconds.setRange(0.5, 600)
        self.syringe_record_seconds.setValue(5)
        self.syringe_record_seconds.setSuffix(" s")
        self.syringe_record_seconds.setToolTip("Seconds to average pressure before and after each pump movement.")
        self.syringe_cycle_count = IntegerInput()
        self.syringe_cycle_count.setRange(1, 1000)
        self.syringe_cycle_count.setValue(5)
        self.syringe_cycle_count.setToolTip("Number of automatic syringe movement calibration cycles.")
        self.auto_syringe_button = QPushButton("Start auto syringe calibration")
        self.auto_syringe_button.setToolTip("Automatically record pressure, move the pump, record pressure again, and repeat.")
        self.fit_syringe_button = QPushButton("Fit syringe calibration")
        self.fit_syringe_button.setToolTip("Fit delta_pressure_mmhg = slope * signed_pump_motion_seconds + intercept.")
        self.calibration_table = QTextEdit()
        self.calibration_table.setReadOnly(True)
        self.calibration_table.setToolTip("Displays accepted calibration points and fitted coefficients.")

        tabs = QTabWidget()
        tabs.setMinimumHeight(210)

        manometer_tab = QWidget()
        manometer_layout = QVBoxLayout(manometer_tab)
        manometer_layout.setContentsMargins(8, 8, 8, 8)
        manometer_layout.setSpacing(8)
        manometer_form = QFormLayout()
        manometer_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        manometer_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        manometer_form.setVerticalSpacing(8)
        manometer_form.addRow("Manometer point", self.calibration_level)
        manometer_form.addRow("Recording time", self.manometer_record_seconds)
        manometer_layout.addLayout(manometer_form)
        manometer_buttons = QHBoxLayout()
        manometer_buttons.setSpacing(10)
        manometer_buttons.addWidget(self.record_window_start)
        manometer_buttons.addWidget(self.fit_button)
        manometer_layout.addLayout(manometer_buttons)
        syringe_note = QLabel(
            "Syringe calibration uses the fixed default sequence: 5 s pump moves at 60 mL/min, "
            "5 s pressure averages, INF first, 5 cycles up and 5 cycles back."
        )
        syringe_note.setWordWrap(True)
        manometer_layout.addWidget(syringe_note)
        syringe_buttons = QHBoxLayout()
        syringe_buttons.setSpacing(10)
        syringe_buttons.addWidget(self.auto_syringe_button)
        syringe_buttons.addWidget(self.fit_syringe_button)
        manometer_layout.addLayout(syringe_buttons)
        manometer_layout.addStretch(1)

        tabs.addTab(manometer_tab, "Calibration")
        tabs.addTab(self.calibration_table, "Calibration log")
        layout.addWidget(tabs)
        return group

    def _logging_panel(self) -> QGroupBox:
        group = QGroupBox("Run automated test")
        layout = QVBoxLayout(group)
        form = QFormLayout()
        self.experiment_id = QLineEdit()
        self.experiment_id.setToolTip(TOOLTIPS["experiment_id"])
        self.operator_notes = QPlainTextEdit()
        self.operator_notes.setMinimumHeight(42)
        self.operator_notes.setMaximumHeight(48)
        self.operator_notes.setToolTip(TOOLTIPS["operator_notes"])
        self.output_folder = QLineEdit()
        self.output_folder.setToolTip(TOOLTIPS["output_folder"])
        self.start_pressure = NumberInput(decimals=2)
        self.start_pressure.setRange(0, 1000)
        self.start_pressure.setSuffix(" mmHg")
        self.start_pressure.setToolTip(TOOLTIPS["start_pressure"])
        self.stop_pressure = NumberInput(decimals=2)
        self.stop_pressure.setRange(0, 190)
        self.stop_pressure.setValue(50)
        self.stop_pressure.setSuffix(" mmHg")
        self.stop_pressure.setToolTip(f"{TOOLTIPS['stop_pressure']} Maximum allowed stop pressure is 190 mmHg.")
        self.pressure_interval = NumberInput(decimals=3)
        self.pressure_interval.setRange(0, 1000)
        self.pressure_interval.setValue(5)
        self.pressure_interval.setSuffix(" mmHg")
        self.pressure_interval.setToolTip("Desired pressure interval for automated test pump timing.")
        self.automated_time_interval = NumberInput(decimals=1)
        self.automated_time_interval.setRange(0.5, 3600)
        self.automated_time_interval.setSuffix(" s")
        self.automated_time_interval.clear()
        self.automated_time_interval.setToolTip(
            "Optional seconds to wait at each stopped interval. Leave blank to fit resistance settling and continue after 3 tau."
        )
        self.automated_cycle_limit = IntegerInput()
        self.automated_cycle_limit.setRange(1, 1000000)
        self.automated_cycle_limit.clear()
        self.automated_cycle_limit.setPlaceholderText("blank = indefinite")
        self.automated_cycle_limit.setToolTip(
            "Optional number of complete increasing/decreasing cycles to run before stopping. Leave blank to run until stopped manually."
        )
        self.estimated_duration = QLabel("Estimated duration: indefinite")
        self.estimated_duration.setToolTip(
            "Estimated duration from start/stop/interval/cycles, average time, and syringe timing calibration."
        )
        self.choose_output = QPushButton("Choose output folder")
        self.choose_output.setToolTip(TOOLTIPS["output_folder"])
        self.start_logging = QPushButton("Start automated test")
        self.start_logging.setToolTip("Move to start pressure, then cycle between start and stop pressure while logging resistance.")
        self.stop_logging = QPushButton("Stop automated test")
        self.stop_logging.setToolTip("Stop the automated test, stop the pump, and save the plot files.")
        self.staircase_test = QPushButton("Staircase")
        self.staircase_test.setCheckable(True)
        self.staircase_test.setToolTip(
            "Run the conditioning sequence 3x(0-50), 3x(0-100), 3x(0-150), 3x(0-180), "
            "then 3x(0-150), 3x(0-100), 3x(0-50). Uses the pressure interval for intermediate steps."
        )
        form.addRow("Experiment ID", self.experiment_id)
        form.addRow("Operator notes", self.operator_notes)
        form.addRow("Output folder", self.output_folder)
        form.addRow("Start pressure", self.start_pressure)
        form.addRow("Stop pressure", self.stop_pressure)
        form.addRow("Pressure interval", self.pressure_interval)
        form.addRow("Time interval", self.automated_time_interval)
        form.addRow("Cycle limit", self.automated_cycle_limit)
        form.addRow("Estimated duration", self.estimated_duration)
        layout.addLayout(form)
        layout.addWidget(self.choose_output)
        controls = QHBoxLayout()
        self.start_acquisition = QPushButton("Start acquisition")
        self.start_acquisition.setToolTip(TOOLTIPS["start_acquisition"])
        self.stop_acquisition = QPushButton("Stop acquisition")
        self.stop_acquisition.setToolTip(TOOLTIPS["stop_acquisition"])
        self.safe_abort = QPushButton("Safe stop / abort")
        self.safe_abort.setToolTip(TOOLTIPS["safe_abort"])
        self.safe_abort.setStyleSheet("background: #9b1c1c; color: white; font-weight: 700;")
        controls.addWidget(self.start_logging)
        controls.addWidget(self.stop_logging)
        controls.addWidget(self.staircase_test)
        controls.addWidget(self.start_acquisition)
        controls.addWidget(self.stop_acquisition)
        controls.addWidget(self.safe_abort)
        layout.addLayout(controls)
        return group

    def _status_panel(self) -> QGroupBox:
        group = QGroupBox("Status and errors")
        layout = QVBoxLayout(group)
        self.status_log = QTextEdit()
        self.status_log.setReadOnly(True)
        self.status_log.setMinimumHeight(90)
        self.status_log.setToolTip("Warnings, invalid data, timeout errors, and device faults appear here.")
        layout.addWidget(self.status_log)
        return group

    def _connect_signals(self) -> None:
        self.refresh_button.clicked.connect(self.refresh_ports)
        for source, controls in self.device_controls.items():
            controls.connect.clicked.connect(lambda _=False, s=source: self._connect_device(s))
            controls.disconnect.clicked.connect(lambda _=False, s=source: self.controller.disconnect_device(s))
            controls.test.clicked.connect(lambda _=False, s=source: self._test_device(s))
        self.start_acquisition.clicked.connect(self._start_acquisition)
        self.stop_acquisition.clicked.connect(self.controller.stop_all_acquisition)
        self.safe_abort.clicked.connect(self._safe_abort)
        self.choose_output.clicked.connect(self._choose_output)
        self.start_logging.clicked.connect(self._start_automated_test)
        self.stop_logging.clicked.connect(self._stop_automated_test)
        self.record_window_start.clicked.connect(lambda: self._start_recording_window("manometer"))
        self.fit_button.clicked.connect(self._fit_pressure)
        self.auto_syringe_button.clicked.connect(self._start_auto_syringe_calibration)
        self.fit_syringe_button.clicked.connect(self._fit_syringe)
        for field in [
            self.start_pressure,
            self.stop_pressure,
            self.pressure_interval,
            self.automated_time_interval,
            self.automated_cycle_limit,
        ]:
            field.textChanged.connect(self._update_estimated_duration)
        self.staircase_test.toggled.connect(lambda _checked=False: self._update_estimated_duration())
        self.controller.message_received.connect(self._handle_message)
        self.controller.status_changed.connect(self._append_status)

    def refresh_ports(self) -> None:
        ports = discover_serial_ports(include_simulated=True)
        preferred = {
            DeviceSource.PRESSURE: self.controller.config.devices.pressure.port,
            DeviceSource.FLUKE: self.controller.config.devices.fluke.port,
            DeviceSource.PUMP: self.controller.config.devices.pump.port,
        }
        for source, controls in self.device_controls.items():
            current = controls.port.currentData() or ""
            controls.port.clear()
            controls.port.addItem("", "")
            preferred_port = preferred[source]
            for port in ports:
                controls.port.addItem(port.label, port.device)
            target = current or preferred_port
            index = controls.port.findData(target)
            if index >= 0:
                controls.port.setCurrentIndex(index)

    def _connect_device(self, source: DeviceSource) -> None:
        controls = self.device_controls[source]
        port = controls.port.currentData()
        if not port:
            self._append_status(f"Select a serial port before connecting {source.value}.")
            return
        self.controller.connect_device(source, port, controls.baud.value())

    def _auto_connect_and_start_acquisition(self) -> None:
        """Try default startup connections and begin pressure/Fluke acquisition."""
        connected_any = False
        for source in [DeviceSource.PRESSURE, DeviceSource.FLUKE, DeviceSource.PUMP]:
            controls = self.device_controls[source]
            port = controls.port.currentData()
            if port:
                self.controller.connect_device(source, port, controls.baud.value())
                connected_any = True
        if connected_any:
            self._append_status("Startup auto-connect requested for selected devices.")
            QTimer.singleShot(1200, self._auto_start_acquisition_after_connect)
        else:
            self._append_status("Startup auto-connect skipped because no serial ports are selected.")

    def _auto_start_acquisition_after_connect(self) -> None:
        self.controller.start_all_acquisition()
        self._append_status("Startup pressure and Fluke acquisition requested.")

    def _test_device(self, source: DeviceSource) -> None:
        controls = self.device_controls[source]
        port = controls.port.currentData()
        if not port:
            self._append_status(f"Select a serial port before testing {source.value}.")
            return
        self.controller.test_connection(source, port, controls.baud.value())

    def _start_acquisition(self) -> None:
        warnings = self.controller.validate_mode_start(AppMode.RAW_RECORDING)
        non_logging_warnings = [warning for warning in warnings if "output folder" not in warning.lower()]
        if non_logging_warnings:
            for warning in non_logging_warnings:
                self._append_status(warning)
            return
        self.controller.start_all_acquisition()

    def _safe_abort(self) -> None:
        self._stop_automated_test(abort=True)
        self.controller.pump_abort()
        self.controller.stop_all_acquisition()
        self._append_status("Safe stop requested.")

    def _choose_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if folder:
            self.output_folder.setText(folder)
            self.controller.output_folder = Path(folder)

    def _start_logging(self) -> None:
        if not self.output_folder.text().strip():
            self._append_status("Choose an output folder before starting logging.")
            return
        self.controller.output_folder = Path(self.output_folder.text().strip())
        mode = "automated_test"
        try:
            path = self.controller.start_logging(
                experiment_id=self.experiment_id.text(),
                operator_notes=self.operator_notes.toPlainText(),
                mode=mode,
            )
        except Exception as exc:
            self._append_status(str(exc))
            return
        self._append_status(f"Logging to {path}")

    def _start_automated_test(self) -> None:
        if self.automated_test_active:
            self._append_status("Automated test is already running.")
            return
        if not self.output_folder.text().strip():
            self._append_status("Choose an output folder before starting the automated test.")
            return
        self.controller.output_folder = Path(self.output_folder.text().strip())
        warnings = self.controller.validate_mode_start(AppMode.CLOSED_LOOP_TEST)
        if warnings:
            for warning in warnings:
                self._append_status(warning)
            return
        staircase_mode = self.staircase_test.isChecked()
        start_pressure = 0.0 if staircase_mode else self.start_pressure.value()
        stop_pressure = self.stop_pressure.value()
        interval = self.pressure_interval.value()
        if interval <= 0:
            self._append_status("Pressure interval must be greater than 0.")
            return
        if not staircase_mode and abs(stop_pressure - start_pressure) < 0.001:
            self._append_status("Start pressure and stop pressure must be different.")
            return
        targets = self._build_staircase_targets(interval) if staircase_mode else self._build_automated_targets(start_pressure, stop_pressure, interval)
        if len(targets) < 2:
            self._append_status("Automated target list needs at least two pressures.")
            return
        cycle_limit = None if staircase_mode else self._automated_cycle_limit_value()
        if cycle_limit == 0:
            self._append_status("Cycle limit must be blank or a positive whole number.")
            return
        self.automated_test_active = True
        self.automated_test_logging_started = False
        self.automated_test_targets = targets
        self.automated_test_target_index = 0
        self.automated_test_target_pressure = start_pressure
        self.automated_test_staircase_mode = staircase_mode
        self.automated_test_direction = 1 if stop_pressure > start_pressure else -1
        self.automated_test_cycle = 0
        self.automated_test_cycle_limit = cycle_limit
        self.automated_test_half_cycle_index = 0
        self.automated_test_phase = "preposition_to_start"
        self.automated_test_stop_requested = False
        self.automated_test_segment_active = False
        self.automated_test_segment_target_pressure = None
        self.automated_test_segment_direction = 0
        increasing_fit = self.controller.calibration.syringe_increasing_fit or self.controller.calibration.syringe_fit
        decreasing_fit = self.controller.calibration.syringe_decreasing_fit or self.controller.calibration.syringe_fit
        self.automated_test_runtime_increasing_slope = increasing_fit.slope if increasing_fit is not None else None
        self.automated_test_runtime_decreasing_slope = decreasing_fit.slope if decreasing_fit is not None else None
        self.automated_test_runtime_slope = self.automated_test_runtime_increasing_slope
        self.automated_test_started_monotonic = monotonic()
        self.automated_test_estimated_total_seconds = self._estimated_total_seconds()
        self._reset_pressure_watchdog()
        self.estimate_timer.start()
        self.pressure_watchdog_timer.start()
        self.start_logging.setEnabled(False)
        if keep_system_awake():
            self._append_status("Windows sleep prevention is active for this automated test.")
        self.controller.state_machine.transition(AppState.CLOSED_LOOP_RUNNING)
        self.controller.start_all_acquisition()
        self._append_status(
            f"Automated test started. First moving to start pressure {start_pressure:.3f} mmHg; "
            "logging begins after start pressure is reached."
        )
        if self.automated_test_staircase_mode:
            self._append_status(
                "Staircase conditioning enabled: 3 cycles each at 50, 100, 150, 180, 150, 100, and 50 mmHg."
            )
        elif self.automated_test_cycle_limit is None:
            self._append_status("Cycle limit is blank; automated test will run until stopped manually.")
        else:
            self._append_status(f"Cycle limit set to {self.automated_test_cycle_limit} complete cycles.")
        estimate = self._estimated_duration_text()
        if estimate:
            self._append_status(estimate)
        if self.automated_test_runtime_increasing_slope is not None or self.automated_test_runtime_decreasing_slope is not None:
            self._append_status(
                "Syringe timing conversion: "
                f"increasing {self.automated_test_runtime_increasing_slope or 0.0:.6f}, "
                f"decreasing {self.automated_test_runtime_decreasing_slope or 0.0:.6f} "
                "mmHg per second of signed pump motion."
            )
        QTimer.singleShot(500, self._automated_test_step)

    def _stop_automated_test(self, abort: bool = False) -> None:
        if not abort and self.automated_test_active:
            self._request_automated_test_stop()
            return
        self._finish_automated_test(abort=abort)

    def _automated_cycle_limit_value(self) -> int | None:
        text = self.automated_cycle_limit.text().strip()
        if not text:
            return None
        try:
            value = int(text)
        except ValueError:
            return 0
        return value if value > 0 else 0

    def _build_automated_targets(self, start_pressure: float, stop_pressure: float, interval: float) -> list[float]:
        if interval <= 0 or abs(stop_pressure - start_pressure) < 0.001:
            return []
        direction = 1 if stop_pressure > start_pressure else -1
        targets = [start_pressure]
        current = start_pressure
        while True:
            next_target = current + direction * interval
            if (direction > 0 and next_target >= stop_pressure) or (direction < 0 and next_target <= stop_pressure):
                if abs(targets[-1] - stop_pressure) > 0.001:
                    targets.append(stop_pressure)
                break
            targets.append(next_target)
            current = next_target
        return targets

    def _build_staircase_targets(self, interval: float) -> list[float]:
        if interval <= 0:
            return []
        targets = [0.0]
        for peak in [50.0, 100.0, 150.0, 180.0, 150.0, 100.0, 50.0]:
            for _ in range(3):
                segment_up = self._build_automated_targets(0.0, peak, interval)
                segment_down = self._build_automated_targets(peak, 0.0, interval)
                for target in segment_up[1:] + segment_down[1:]:
                    if abs(targets[-1] - target) > 0.001:
                        targets.append(target)
        return targets

    def _estimated_total_seconds(self) -> float | None:
        cycle_limit = self._automated_cycle_limit_value()
        staircase_mode = self.staircase_test.isChecked()
        if cycle_limit is None and not staircase_mode:
            return None
        if cycle_limit == 0 and not staircase_mode:
            return None
        start_pressure = self.start_pressure.value()
        stop_pressure = self.stop_pressure.value()
        interval = self.pressure_interval.value()
        targets = self._build_staircase_targets(interval) if staircase_mode else self._build_automated_targets(start_pressure, stop_pressure, interval)
        if len(targets) < 2:
            return None
        average_windows = len(targets) if staircase_mode else 1 + cycle_limit * 2 * (len(targets) - 1)
        interval_seconds = self._manual_automated_time_interval_seconds()
        average_seconds = average_windows * (interval_seconds or self.automated_test_auto_settle_min_seconds)
        move_seconds = 0.0
        if self.controller.calibration.syringe_fit is not None:
            target_pairs = list(zip(targets, targets[1:]))
            if not staircase_mode:
                reversed_targets = list(reversed(targets))
                target_pairs += list(zip(reversed_targets, reversed_targets[1:]))
            for first, second in target_pairs:
                try:
                    move_seconds += abs(self.controller.calibration.motion_seconds_for_pressure_delta(second - first) or 0.0)
                except Exception:
                    break
            if not staircase_mode:
                move_seconds *= cycle_limit
        overhead_seconds = average_windows * 0.75
        return average_seconds + move_seconds + overhead_seconds

    def _estimated_duration_text(self) -> str:
        cycle_limit = self._automated_cycle_limit_value()
        if self.staircase_test.isChecked():
            total_seconds = self.automated_test_estimated_total_seconds if self.automated_test_active else self._estimated_total_seconds()
            if total_seconds is None:
                return "Estimated duration: enter valid staircase interval and calibration values"
            if self.automated_test_active and self.automated_test_started_monotonic is not None:
                remaining_seconds = max(0.0, total_seconds - (monotonic() - self.automated_test_started_monotonic))
                return f"Time remaining: {remaining_seconds / 60.0:.1f} minutes"
            return f"Estimated duration: {total_seconds / 60.0:.1f} minutes"
        if cycle_limit is None:
            if self.automated_test_active and self.automated_test_started_monotonic is not None:
                elapsed_minutes = (monotonic() - self.automated_test_started_monotonic) / 60.0
                return f"Time remaining: indefinite; elapsed {elapsed_minutes:.1f} minutes"
            return "Estimated duration: indefinite"
        if cycle_limit == 0:
            return "Estimated duration: enter a positive cycle limit or leave it blank"
        total_seconds = self.automated_test_estimated_total_seconds if self.automated_test_active else self._estimated_total_seconds()
        if total_seconds is None:
            return "Estimated duration: enter valid start, stop, interval, and cycle values"
        if self.automated_test_active and self.automated_test_started_monotonic is not None:
            remaining_seconds = max(0.0, total_seconds - (monotonic() - self.automated_test_started_monotonic))
            return f"Time remaining: {remaining_seconds / 60.0:.1f} minutes"
        return f"Estimated duration: {total_seconds / 60.0:.1f} minutes"

    def _update_estimated_duration(self) -> None:
        self.estimated_duration.setText(self._estimated_duration_text())

    def _manual_automated_time_interval_seconds(self) -> float | None:
        text = self.automated_time_interval.text().strip()
        if not text:
            return None
        try:
            value = float(text)
        except ValueError:
            return None
        return value if value > 0 else None

    def _reset_pressure_watchdog(self) -> None:
        now = monotonic()
        self.pressure_watchdog_last_raw = None
        self.pressure_watchdog_last_sample_time = now
        self.pressure_watchdog_last_change_time = now
        self.pressure_watchdog_halted = False

    def _note_pressure_watchdog_sample(self, raw_value: int) -> None:
        now = monotonic()
        self.pressure_watchdog_last_sample_time = now
        if self.pressure_watchdog_last_raw != raw_value:
            self.pressure_watchdog_last_raw = raw_value
            self.pressure_watchdog_last_change_time = now
        elif self.pressure_watchdog_last_change_time is None:
            self.pressure_watchdog_last_change_time = now

    def _check_pressure_watchdog(self) -> None:
        if not self.automated_test_active or self.pressure_watchdog_halted:
            return
        now = monotonic()
        if self.pressure_watchdog_last_sample_time is None:
            self._halt_automated_test_for_pressure_watchdog("No pressure samples have arrived for 10 seconds.")
            return
        if now - self.pressure_watchdog_last_sample_time > 10.0:
            self._halt_automated_test_for_pressure_watchdog(
                "Pressure sensor data stopped arriving for more than 10 seconds."
            )
            return
        if self.pressure_watchdog_last_change_time is not None and now - self.pressure_watchdog_last_change_time > 10.0:
            self._halt_automated_test_for_pressure_watchdog(
                f"Raw PuTTY integer has not changed for more than 10 seconds "
                f"(stuck at {self.pressure_watchdog_last_raw})."
            )

    def _halt_automated_test_for_pressure_watchdog(self, reason: str) -> None:
        if self.pressure_watchdog_halted:
            return
        self.pressure_watchdog_halted = True
        self._append_status(f"Pressure watchdog halt: {reason} Stopping pump and ending the automated test.")
        self.controller.pump_abort()
        self._stop_automated_test(abort=True)

    def _request_automated_test_stop(self) -> None:
        self.automated_test_stop_requested = True
        start_pressure = self.start_pressure.value()
        if self.automated_test_staircase_mode:
            start_pressure = 0.0
        if self.automated_test_phase == "preposition_to_start":
            self._append_status("Stop requested during pre-positioning. Stopping immediately because the test has not started logging yet.")
            self._finish_automated_test(abort=True)
            return
        self.automated_test_direction = -1 if self.stop_pressure.value() > start_pressure else 1
        self.automated_test_phase = "moving_to_start"
        if self.automated_test_targets:
            self.automated_test_target_index = 0
        self.automated_test_target_pressure = start_pressure
        self._append_status(
            f"Stop requested. Finishing the current cycle by returning to start pressure {start_pressure:.3f} mmHg."
        )

    def _finish_automated_test(self, abort: bool = False) -> None:
        if self.automated_test_active or self.automated_test_logging_started:
            self._append_status("Stopping automated test.")
        self.automated_test_active = False
        self.automated_test_logging_started = False
        self.automated_test_target_pressure = None
        self.automated_test_targets = []
        self.automated_test_target_index = 0
        self.automated_test_cycle_limit = None
        self.automated_test_staircase_mode = False
        self.automated_test_phase = "idle"
        self.automated_test_stop_requested = False
        self.automated_test_segment_active = False
        self.automated_test_segment_target_pressure = None
        self.automated_test_segment_direction = 0
        self.automated_test_segment_cross_count = 0
        self.automated_test_segment_away_count = 0
        self.automated_test_segment_start_pressure = None
        self.automated_test_segment_final_target = None
        self.automated_test_segment_start_time = None
        self.automated_test_segment_planned_seconds = 0.0
        self.automated_test_segment_requested_delta = 0.0
        self.automated_test_pump_motion_sign = 0
        self.automated_test_runtime_slope = None
        self.automated_test_runtime_increasing_slope = None
        self.automated_test_runtime_decreasing_slope = None
        self.automated_test_settling_active = False
        self.automated_test_settling_target = None
        self.automated_test_settling_pressure_samples = []
        self.automated_test_settling_resistance_samples = []
        self.automated_test_settling_started_at = None
        self.automated_test_settling_started_monotonic = None
        self.automated_test_settling_timer.stop()
        self.automated_test_started_monotonic = None
        self.automated_test_estimated_total_seconds = None
        self.estimate_timer.stop()
        self.pressure_watchdog_timer.stop()
        self._reset_pressure_watchdog()
        self.closed_loop_preposition_active = False
        self.start_logging.setEnabled(True)
        clear_keep_awake()
        self.controller.pump_abort()
        self.controller.stop_logging()
        try:
            if self.controller.state_machine.state == AppState.CLOSED_LOOP_RUNNING:
                self.controller.state_machine.transition(AppState.IDLE)
        except ValueError as exc:
            self._append_status(str(exc))
        if abort:
            self.controller.stop_all_acquisition()

    def _start_automated_logging(self) -> bool:
        if self.automated_test_logging_started:
            return True
        try:
            path = self.controller.start_logging(
                experiment_id=self.experiment_id.text(),
                operator_notes=self.operator_notes.toPlainText(),
                mode="automated_test",
            )
        except Exception as exc:
            self._append_status(str(exc))
            self._stop_automated_test(abort=True)
            return False
        self.automated_test_logging_started = True
        self._append_status(f"Automated test logging to {path}")
        return True

    def _automated_test_step(self) -> None:
        if not self.automated_test_active:
            return
        if self.automated_test_settling_active:
            return
        current = self.controller.latest_pressure_mmhg
        if current is None:
            self._append_status("Waiting for calibrated pressure reading before automated pump movement.")
            QTimer.singleShot(500, self._automated_test_step)
            return
        target = self.automated_test_target_pressure
        if target is None:
            self.automated_test_target_pressure = self.start_pressure.value()
            target = self.automated_test_target_pressure
        tolerance = min(0.5, max(0.05, self.pressure_interval.value() * 0.1))
        if abs(current - target) <= tolerance:
            self._handle_automated_target_reached(current, target)
            return
        self._move_automated_pump_to_target(current, target)

    def _handle_automated_target_reached(self, current: float, target: float) -> None:
        if self.automated_test_phase == "preposition_to_start":
            self.controller.pump_abort()
            self._append_status(f"Reached start pressure at {current:.3f} mmHg. Starting resistance logging and stopped-window average.")
            if not self._start_automated_logging():
                return
            self._start_automated_settled_average(target)
            return
        self._start_automated_settled_average(target)

    def _start_automated_settled_average(self, target: float) -> None:
        if self.automated_test_settling_active:
            return
        self.automated_test_settling_active = True
        self.automated_test_settling_target = target
        self.automated_test_settling_pressure_samples = []
        self.automated_test_settling_resistance_samples = []
        self.automated_test_settling_started_at = datetime.now(timezone.utc)
        self.automated_test_settling_started_monotonic = monotonic()
        manual_seconds = self._manual_automated_time_interval_seconds()
        if manual_seconds is not None:
            self._append_status(
                f"Pump stopped. Averaging pressure and resistance for {manual_seconds:.1f}s at target {target:.3f} mmHg."
            )
            QTimer.singleShot(int(manual_seconds * 1000), lambda: self._finish_automated_settled_average())
            return
        self._append_status(
            f"Pump stopped. Fitting resistance settling at target {target:.3f} mmHg; "
            "will continue after 3 tau or at the 60.0s safety timeout."
        )
        self.automated_test_settling_timer.start()

    def _check_automated_auto_settle(self) -> None:
        if not self.automated_test_settling_active or self.automated_test_settling_started_monotonic is None:
            return
        elapsed = monotonic() - self.automated_test_settling_started_monotonic
        if elapsed < self.automated_test_auto_settle_min_seconds:
            return
        fit = fit_exponential_settling(self.automated_test_settling_resistance_samples)
        if fit is not None and elapsed >= fit.three_tau_seconds:
            self._append_status(
                f"Resistance settling fit reached 3 tau ({fit.three_tau_seconds:.1f}s); "
                f"predicted final resistance {fit.final_value:.5f} ohms."
            )
            self._finish_automated_settled_average(fit)
            return
        if elapsed >= self.automated_test_auto_settle_max_seconds:
            self._append_status(
                "Resistance auto-settle reached the 60.0s safety timeout; using the best available fit or sample average."
            )
            self._finish_automated_settled_average(fit)

    def _finish_automated_settled_average(self, resistance_fit: ExponentialSettlingFit | None = None) -> None:
        if not self.automated_test_settling_active:
            return
        self.automated_test_settling_timer.stop()
        target = self.automated_test_settling_target
        pressure_samples = list(self.automated_test_settling_pressure_samples)
        resistance_samples = list(self.automated_test_settling_resistance_samples)
        started_at = self.automated_test_settling_started_at
        self.automated_test_settling_active = False
        self.automated_test_settling_target = None
        self.automated_test_settling_pressure_samples = []
        self.automated_test_settling_resistance_samples = []
        self.automated_test_settling_started_at = None
        self.automated_test_settling_started_monotonic = None
        if target is None:
            return
        pressure_values = [value for _, value in pressure_samples]
        resistance_values = [value for _, value in resistance_samples]
        average_pressure = fmean(pressure_values) if pressure_values else self.controller.latest_pressure_mmhg
        average_resistance = (
            resistance_fit.final_value
            if resistance_fit is not None
            else fmean(resistance_values)
            if resistance_values
            else self.controller.latest_resistance_ohms
        )
        if average_pressure is None:
            self._append_status("No pressure samples were captured during the stopped average window.")
        if average_resistance is None:
            self._append_status("No Fluke resistance samples were captured during the stopped average window.")
        self.controller.record_closed_loop_settled_point(
            {
                "timestamp": datetime.now(timezone.utc),
                "window_started_at": started_at,
                "target_pressure_mmhg": target,
                "average_pressure_mmhg": average_pressure,
                "average_resistance_ohms": average_resistance,
                "pressure_sample_count": len(pressure_samples),
                "resistance_sample_count": len(resistance_samples),
                "resistance_settle_method": "exponential_3tau" if resistance_fit is not None else "fixed_average",
                "resistance_tau_seconds": resistance_fit.tau_seconds if resistance_fit is not None else None,
                "resistance_fit_rmse": resistance_fit.rmse if resistance_fit is not None else None,
                "cycle": self.automated_test_cycle,
                "half_cycle_index": self.automated_test_half_cycle_index,
                "sweep_direction": self._automated_sweep_direction_name(),
                "phase": self.automated_test_phase,
            }
        )
        pressure_text = "--" if average_pressure is None else f"{average_pressure:.3f}"
        resistance_text = "--" if average_resistance is None else f"{average_resistance:.5f}"
        self._append_status(
            f"Stopped average saved: target {target:.3f} mmHg, pressure {pressure_text} mmHg "
            f"from {len(pressure_samples)} samples, resistance {resistance_text} ohms "
            f"from {len(resistance_samples)} samples."
        )
        self._advance_automated_target_after_average(target)

    def _advance_automated_target_after_average(self, target: float) -> None:
        if self.automated_test_staircase_mode:
            self._advance_staircase_target_after_average(target)
            return
        at_stop = abs(target - self.stop_pressure.value()) <= 0.001
        at_start = abs(target - self.start_pressure.value()) <= 0.001
        self._append_status(
            f"Completed stopped average at target {target:.3f} mmHg "
            f"(cycle {self.automated_test_cycle})."
        )
        if self.automated_test_phase == "preposition_to_start":
            self.automated_test_phase = "moving_to_stop"
            self.automated_test_direction = 1 if self.stop_pressure.value() > self.start_pressure.value() else -1
            self.automated_test_target_pressure = self._next_cycle_target(target)
            self._append_status(
                f"Pre-position average complete. First cycling target is "
                f"{self.automated_test_target_pressure:.3f} mmHg."
            )
            QTimer.singleShot(250, self._automated_test_step)
            return
        if at_stop:
            self.automated_test_half_cycle_index += 1
            self.automated_test_direction = -1 if self.stop_pressure.value() > self.start_pressure.value() else 1
            self.automated_test_phase = "moving_to_start"
        elif at_start:
            self.automated_test_cycle += 1
            if self.automated_test_stop_requested:
                self._append_status("Returned to start pressure. Automated test stopped after completing the cycle.")
                self._finish_automated_test()
                return
            if self.automated_test_cycle_limit is not None and self.automated_test_cycle >= self.automated_test_cycle_limit:
                self._append_status(
                    f"Cycle limit reached ({self.automated_test_cycle}/{self.automated_test_cycle_limit}). "
                    "Automated test stopped at the start pressure."
                )
                self._finish_automated_test()
                return
            self.automated_test_half_cycle_index += 1
            self.automated_test_direction = 1 if self.stop_pressure.value() > self.start_pressure.value() else -1
            self.automated_test_phase = "moving_to_stop"
        self.automated_test_target_pressure = self._next_cycle_target(target)
        QTimer.singleShot(250, self._automated_test_step)

    def _advance_staircase_target_after_average(self, target: float) -> None:
        self._append_status(
            f"Completed staircase stopped average at nominal target {target:.3f} mmHg "
            f"({self.automated_test_target_index + 1}/{len(self.automated_test_targets)})."
        )
        if self.automated_test_stop_requested:
            if abs(target) <= 0.001:
                self._append_status("Returned to 0 mmHg. Staircase test stopped.")
                self._finish_automated_test()
                return
            next_zero = self._next_staircase_zero_index()
            if next_zero is not None:
                self.automated_test_target_index = next_zero - 1
                self.automated_test_target_pressure = self.automated_test_targets[next_zero]
                self.automated_test_direction = -1 if self.automated_test_target_pressure < target else 1
                self.automated_test_phase = "moving_to_start"
                QTimer.singleShot(250, self._automated_test_step)
                return
        if self.automated_test_target_index >= len(self.automated_test_targets) - 1:
            self._append_status("Staircase conditioning sequence complete.")
            self._finish_automated_test()
            return
        previous_target = target
        self.automated_test_target_index += 1
        self.automated_test_target_pressure = self.automated_test_targets[self.automated_test_target_index]
        self.automated_test_direction = 1 if self.automated_test_target_pressure > previous_target else -1
        if abs(self.automated_test_target_pressure) <= 0.001:
            self.automated_test_phase = "moving_to_start"
            self.automated_test_cycle += 1
        else:
            self.automated_test_phase = "moving_to_stop" if self.automated_test_direction > 0 else "moving_to_start"
        QTimer.singleShot(250, self._automated_test_step)

    def _next_staircase_zero_index(self) -> int | None:
        for index in range(self.automated_test_target_index + 1, len(self.automated_test_targets)):
            if abs(self.automated_test_targets[index]) <= 0.001:
                return index
        return None

    def _automated_sweep_direction_name(self) -> str:
        if self.automated_test_direction > 0:
            return "increasing"
        if self.automated_test_direction < 0:
            return "decreasing"
        return "unknown"

    def _next_cycle_target(self, current_target: float) -> float:
        if not self.automated_test_targets:
            return current_target
        self.automated_test_target_index += self.automated_test_direction
        self.automated_test_target_index = max(
            0,
            min(len(self.automated_test_targets) - 1, self.automated_test_target_index),
        )
        return self.automated_test_targets[self.automated_test_target_index]

    def _move_automated_pump_to_target(self, current: float, target: float) -> None:
        remaining_delta = target - current
        bounded_delta = self._bounded_automated_pressure_delta(remaining_delta)
        try:
            signed_motion_seconds = self._motion_seconds_for_automated_delta(bounded_delta)
        except Exception as exc:
            self._append_status(str(exc))
            self._stop_automated_test(abort=True)
            return
        if signed_motion_seconds is None:
            self._append_status("Syringe calibration is unavailable; cannot compute pump motion time.")
            self._stop_automated_test(abort=True)
            return
        direction = "INF" if signed_motion_seconds >= 0 else "WDR"
        duration = abs(signed_motion_seconds)
        if duration < 0.05:
            QTimer.singleShot(100, self._automated_test_step)
            return
        max_segment_seconds = 30.0
        segment_duration = min(duration, max_segment_seconds)
        segment_target_pressure = current + bounded_delta
        self.automated_test_move_id += 1
        move_id = self.automated_test_move_id
        self.automated_test_segment_active = True
        self.automated_test_segment_target_pressure = segment_target_pressure
        self.automated_test_segment_direction = 1 if bounded_delta > 0 else -1
        self.automated_test_pump_motion_sign = 1 if direction == "INF" else -1
        self.automated_test_segment_cross_count = 0
        self.automated_test_segment_away_count = 0
        self.automated_test_segment_start_pressure = current
        self.automated_test_segment_final_target = target
        self.automated_test_segment_start_time = monotonic()
        self.automated_test_segment_planned_seconds = segment_duration
        self.automated_test_segment_requested_delta = bounded_delta
        self.controller.pump_run(
            {
                "direction": direction,
                "rate": self.pump_rate.value(),
                "rate_units": "ML/MIN",
                "mode": "continuous",
                "volume_ml": 0,
                "motion_seconds": segment_duration,
            }
        )
        self._append_status(
            f"Pump {direction} for {segment_duration:.2f}s: requested pressure step "
            f"{bounded_delta:+.3f} mmHg toward segment target {segment_target_pressure:.3f} "
            f"(final target {target:.3f}) from {current:.3f}."
        )
        QTimer.singleShot(int(segment_duration * 1000), lambda move_id=move_id: self._finish_automated_pump_segment(move_id, "timed move complete"))

    def _motion_seconds_for_automated_delta(self, delta_mmhg: float) -> float | None:
        slope = self._runtime_slope_for_delta(delta_mmhg)
        if slope is None:
            motion_seconds = self.controller.calibration.motion_seconds_for_pressure_delta(delta_mmhg)
            fit = self.controller.calibration.fit_for_pressure_delta(delta_mmhg)
            self.automated_test_runtime_slope = fit.slope if fit is not None else None
            return motion_seconds
        self.automated_test_runtime_slope = slope
        if slope == 0:
            raise ValueError("Syringe calibration slope is zero; cannot compute pump motion time.")
        return delta_mmhg / slope

    def _runtime_slope_for_delta(self, delta_mmhg: float) -> float | None:
        if delta_mmhg > 0 and self.automated_test_runtime_increasing_slope is not None:
            return self.automated_test_runtime_increasing_slope
        if delta_mmhg < 0 and self.automated_test_runtime_decreasing_slope is not None:
            return self.automated_test_runtime_decreasing_slope
        fit = self.controller.calibration.fit_for_pressure_delta(delta_mmhg)
        if fit is not None:
            return fit.slope
        if self.automated_test_runtime_slope is not None:
            return self.automated_test_runtime_slope
        if self.controller.calibration.syringe_fit is not None:
            return self.controller.calibration.syringe_fit.slope
        return None

    def _set_runtime_slope_for_delta(self, delta_mmhg: float, slope: float) -> None:
        if delta_mmhg >= 0:
            self.automated_test_runtime_increasing_slope = slope
        else:
            self.automated_test_runtime_decreasing_slope = slope
        self.automated_test_runtime_slope = slope

    def _runtime_slope_label_for_delta(self, delta_mmhg: float) -> str:
        return "increasing" if delta_mmhg >= 0 else "decreasing"

    def _bounded_automated_pressure_delta(self, remaining_delta: float) -> float:
        interval = max(0.05, self.pressure_interval.value())
        max_step = max(interval * 2.0, interval + 1.0)
        if abs(remaining_delta) <= max_step:
            return remaining_delta
        self._append_status(
            f"Large pressure correction limited from {remaining_delta:+.3f} mmHg to "
            f"{max_step if remaining_delta > 0 else -max_step:+.3f} mmHg."
        )
        return max_step if remaining_delta > 0 else -max_step

    def _finish_automated_pump_segment(self, move_id: int, reason: str) -> None:
        if move_id != self.automated_test_move_id or not self.automated_test_segment_active:
            return
        self.automated_test_segment_active = False
        self.automated_test_segment_target_pressure = None
        self.automated_test_segment_direction = 0
        self.automated_test_segment_cross_count = 0
        self.automated_test_segment_away_count = 0
        self.controller.pump_abort()
        self._append_status(
            f"Pump segment stopped: {reason}. Waiting "
            f"{self.automated_test_pressure_response_delay_seconds:.1f}s for pressure response before rechecking."
        )
        QTimer.singleShot(
            int(self.automated_test_pressure_response_delay_seconds * 1000),
            lambda move_id=move_id, reason=reason: self._finish_automated_segment_recheck(move_id, reason),
        )

    def _finish_automated_segment_recheck(self, move_id: int, reason: str) -> None:
        if move_id != self.automated_test_move_id:
            return
        target = self.automated_test_segment_final_target
        self._record_automated_pump_observation(reason)
        self.automated_test_segment_start_pressure = None
        self.automated_test_segment_final_target = None
        self.automated_test_segment_start_time = None
        self.automated_test_segment_planned_seconds = 0.0
        self.automated_test_segment_requested_delta = 0.0
        self.automated_test_pump_motion_sign = 0
        self._append_status("Pressure response delay complete. Rechecking pressure.")
        QTimer.singleShot(500, self._automated_test_step)

    def _record_automated_pump_observation(self, reason: str) -> None:
        start_pressure = self.automated_test_segment_start_pressure
        end_pressure = self.controller.latest_pressure_mmhg
        start_time = self.automated_test_segment_start_time
        if start_pressure is None or end_pressure is None or start_time is None:
            return
        elapsed = min(max(monotonic() - start_time, 0.0), self.automated_test_segment_planned_seconds)
        signed_seconds = elapsed * self.automated_test_pump_motion_sign
        actual_delta = end_pressure - start_pressure
        observation = {
            "timestamp": datetime.now(timezone.utc),
            "reason": reason,
            "start_pressure_mmhg": start_pressure,
            "end_pressure_mmhg": end_pressure,
            "requested_delta_mmhg": self.automated_test_segment_requested_delta,
            "actual_delta_mmhg": actual_delta,
            "signed_motion_seconds": signed_seconds,
            "runtime_slope_before": self._runtime_slope_for_delta(self.automated_test_segment_requested_delta),
        }
        self.controller.record_closed_loop_observation(observation)
        self._update_automated_runtime_slope(signed_seconds, actual_delta, self.automated_test_segment_requested_delta)

    def _update_automated_runtime_slope(self, signed_seconds: float, actual_delta: float, requested_delta: float) -> None:
        if abs(signed_seconds) < 0.05 or abs(actual_delta) < 0.02:
            return
        observed_slope = actual_delta / signed_seconds
        current_slope = self._runtime_slope_for_delta(requested_delta)
        slope_label = self._runtime_slope_label_for_delta(requested_delta)
        if current_slope is None:
            self._set_runtime_slope_for_delta(requested_delta, observed_slope)
            return
        if observed_slope * current_slope <= 0:
            self._append_status(
                f"Warning: observed pump response had the opposite sign from the {slope_label} runtime equation. "
                "Ignoring this observation and trying the target again after recheck."
            )
            return
        updated_slope = 0.8 * current_slope + 0.2 * observed_slope
        self._set_runtime_slope_for_delta(requested_delta, updated_slope)
        self._append_status(
            f"{slope_label.title()} runtime syringe timing updated: observed {observed_slope:.6f}, "
            f"using {updated_slope:.6f} mmHg/s."
        )

    def _start_recording_window(self, kind: str = "manometer") -> None:
        if not self.controller.workers[DeviceSource.PRESSURE].connected:
            self._append_status("Connect the pressure sensor before starting a recording window.")
            return
        if self.recording_window_active:
            self._append_status("A recording window is already active.")
            return
        self.raw_window_values.clear()
        self.recording_window_active = True
        self.recording_window_kind = kind
        self.raw_average.setText("--")
        self.controller.send_command(DeviceSource.PRESSURE, CommandType.START)
        self._append_status(f"{kind.replace('_', ' ').title()} recording window started.")
        if kind == "manometer" and self.manometer_record_seconds is not None:
            self.record_window_start.setEnabled(False)
            QTimer.singleShot(int(self.manometer_record_seconds.value() * 1000), self._stop_recording_window)

    def _stop_recording_window(self) -> None:
        if not self.raw_window_values:
            self.recording_window_active = False
            self.record_window_start.setEnabled(True)
            self._append_status("No pressure samples captured in the recording window.")
            return
        self.recording_window_active = False
        point = self.controller.calibration.add_manometer_window(
            timestamp=datetime.now(timezone.utc),
            reference_cm_h2o=self.calibration_level.value(),
            raw_values=self.raw_window_values,
        )
        self.calibration_table.append(
            f"{point.timestamp.isoformat()} | {point.reference_cm_h2o:.3f} cm H2O | "
            f"{point.reference_mmhg:.3f} mmHg | avg raw {point.average_raw:.2f}"
        )
        self.record_window_start.setEnabled(True)
        self.calibration_level.setValue(self.calibration_level.value() + 10)
        self._append_status("Recording window saved.")

    def _save_syringe_before_window(self) -> None:
        if not self.raw_window_values:
            self.recording_window_active = False
            self._append_status("No pressure samples captured before the pump movement.")
            return
        self.recording_window_active = False
        self.syringe_before_values = list(self.raw_window_values)
        average_raw = sum(self.syringe_before_values) / len(self.syringe_before_values)
        pressure = self.controller.calibration.convert_raw_pressure(average_raw)
        pressure_text = "calibration unavailable" if pressure is None else f"{pressure:.3f} mmHg"
        self.calibration_table.append(f"Syringe before move | avg raw {average_raw:.2f} | {pressure_text}")
        self._append_status("Syringe before-move pressure saved.")

    def _move_syringe_calibration_step(self) -> float | None:
        motion_seconds = self.syringe_motion_seconds.value()
        direction = self._auto_syringe_direction_for_current_move()
        self.auto_syringe_current_direction = direction
        self.controller.pump_run(
            {
                "direction": direction,
                "rate": self.pump_rate.value(),
                "rate_units": "ML/MIN",
                "mode": "continuous",
                "volume_ml": 0,
                "motion_seconds": motion_seconds,
            }
        )
        signed_motion = motion_seconds if direction == "INF" else -motion_seconds
        self.auto_syringe_cumulative_motion_seconds += signed_motion
        self._append_status(
            f"Pump timed movement requested: {direction} for {motion_seconds:.2f}s; "
            f"cumulative signed motion {self.auto_syringe_cumulative_motion_seconds:.2f}s."
        )
        QTimer.singleShot(int(motion_seconds * 1000), self.controller.pump_abort)
        return motion_seconds

    def _save_syringe_after_window(self) -> None:
        if self.syringe_before_values is None:
            self.recording_window_active = False
            self._append_status("Record and save the before-move pressure first.")
            return
        if not self.raw_window_values:
            self.recording_window_active = False
            self._append_status("No pressure samples captured after the pump movement.")
            return
        self.recording_window_active = False
        self.syringe_after_values = list(self.raw_window_values)
        try:
            point = self.controller.calibration.add_syringe_movement_point(
                timestamp=datetime.now(timezone.utc),
                movement_seconds=self.syringe_motion_seconds.value(),
                direction=self.auto_syringe_current_direction,
                rate_setting=self.pump_rate.value(),
                before_raw_values=self.syringe_before_values,
                after_raw_values=self.syringe_after_values,
                cycle_index=self.auto_syringe_cycle,
                cumulative_motion_seconds=self.auto_syringe_cumulative_motion_seconds,
            )
        except Exception as exc:
            self._append_status(str(exc))
            return
        self.calibration_table.append(
            f"{point.timestamp.isoformat()} | pump {point.direction} {point.movement_seconds:.2f}s | "
            f"pressure {point.before_pressure_mmhg:.3f} -> "
            f"{point.after_pressure_mmhg:.3f} mmHg | delta {point.delta_pressure_mmhg:.3f} mmHg | "
            f"cumulative {point.cumulative_motion_seconds:.2f}s"
        )
        self.syringe_before_values = None
        self.syringe_after_values = None
        self._append_status("Syringe movement calibration point saved.")

    def _start_auto_syringe_calibration(self) -> None:
        if self.auto_syringe_active:
            self._append_status("Auto syringe calibration is already running.")
            return
        if not self.controller.workers[DeviceSource.PRESSURE].connected:
            self._append_status("Connect the pressure sensor before auto syringe calibration.")
            return
        if not self.controller.workers[DeviceSource.PUMP].connected:
            self._append_status("Connect the syringe pump before auto syringe calibration.")
            return
        if self.controller.calibration.pressure_fit is None:
            self._append_status("Fit pressure calibration before syringe movement calibration.")
            return
        self.auto_syringe_active = True
        self.auto_syringe_cycle = 0
        self.auto_syringe_total_cycles = self.syringe_cycle_count.value()
        self.auto_syringe_total_moves = self.auto_syringe_total_cycles * 2
        self.auto_syringe_base_direction = self.pump_direction.currentText()
        self.auto_syringe_current_direction = self.auto_syringe_base_direction
        self.auto_syringe_cumulative_motion_seconds = 0.0
        self.auto_syringe_button.setEnabled(False)
        self.controller.send_command(DeviceSource.PRESSURE, CommandType.START)
        self._append_status(
            f"Auto syringe calibration started: {self.auto_syringe_total_cycles} increasing moves, "
            f"then {self.auto_syringe_total_cycles} decreasing moves, "
            f"{self.syringe_record_seconds.value():.1f}s before/after average."
        )
        self._start_next_auto_syringe_cycle()

    def _start_next_auto_syringe_cycle(self) -> None:
        if not self.auto_syringe_active:
            return
        if self.auto_syringe_cycle >= self.auto_syringe_total_moves:
            self.auto_syringe_active = False
            self.auto_syringe_button.setEnabled(True)
            self._append_status("Auto syringe calibration complete. Fit syringe calibration when ready.")
            return
        self.auto_syringe_cycle += 1
        self.auto_syringe_current_direction = self._auto_syringe_direction_for_current_move()
        self._start_recording_window("syringe_before")
        self._append_status(
            f"Move {self.auto_syringe_cycle}/{self.auto_syringe_total_moves} "
            f"({self.auto_syringe_current_direction}): recording before-move pressure."
        )
        QTimer.singleShot(int(self.syringe_record_seconds.value() * 1000), self._auto_finish_before_window)

    def _auto_syringe_direction_for_current_move(self) -> str:
        if not self.auto_syringe_active:
            return self.pump_direction.currentText()
        if self.auto_syringe_cycle <= self.auto_syringe_total_cycles:
            return self.auto_syringe_base_direction
        return "WDR" if self.auto_syringe_base_direction == "INF" else "INF"

    def _auto_finish_before_window(self) -> None:
        if not self.auto_syringe_active:
            return
        self._save_syringe_before_window()
        step_distance = self._move_syringe_calibration_step()
        if step_distance is None:
            self.auto_syringe_active = False
            self.auto_syringe_button.setEnabled(True)
            return
        QTimer.singleShot(int((self.syringe_motion_seconds.value() + 0.5) * 1000), self._auto_start_after_window)

    def _auto_start_after_window(self) -> None:
        if not self.auto_syringe_active:
            return
        self._start_recording_window("syringe_after")
        self._append_status(
            f"Move {self.auto_syringe_cycle}/{self.auto_syringe_total_moves}: recording after-move pressure."
        )
        QTimer.singleShot(int(self.syringe_record_seconds.value() * 1000), self._auto_finish_after_window)

    def _auto_finish_after_window(self) -> None:
        if not self.auto_syringe_active:
            return
        self._save_syringe_after_window()
        QTimer.singleShot(250, self._start_next_auto_syringe_cycle)

    def _fit_pressure(self) -> None:
        try:
            fit = self.controller.calibration.fit_pressure()
        except Exception as exc:
            self._append_status(str(exc))
            return
        self.calibration_table.append(f"Fit: pressure_mmhg = {fit.slope:.8f} * raw + {fit.intercept:.8f}")
        self._append_status("Pressure calibration fit updated.")

    def _fit_syringe(self) -> None:
        try:
            fit = self.controller.calibration.fit_syringe()
        except Exception as exc:
            self._append_status(str(exc))
            return
        desired = self.pressure_interval.value()
        try:
            signed_motion = self.controller.calibration.motion_seconds_for_pressure_delta(desired)
        except Exception as exc:
            self._append_status(str(exc))
            return
        direction = "INF" if signed_motion is not None and signed_motion >= 0 else "WDR"
        self.calibration_table.append(
            f"Syringe fit: pressure_mmhg = {fit.slope:.8f} * cumulative_motion_seconds + {fit.intercept:.8f}"
        )
        if self.controller.calibration.syringe_increasing_fit is not None:
            increasing = self.controller.calibration.syringe_increasing_fit
            self.calibration_table.append(
                "Increasing fit: "
                f"pressure_mmhg = {increasing.slope:.8f} * cumulative_motion_seconds + {increasing.intercept:.8f}"
            )
        if self.controller.calibration.syringe_decreasing_fit is not None:
            decreasing = self.controller.calibration.syringe_decreasing_fit
            self.calibration_table.append(
                "Decreasing fit: "
                f"pressure_mmhg = {decreasing.slope:.8f} * cumulative_motion_seconds + {decreasing.intercept:.8f}"
            )
        if signed_motion is not None:
            self.calibration_table.append(
                f"For {desired:.3f} mmHg interval at this rate: run pump {direction} for {abs(signed_motion):.2f}s"
            )
        self._append_status("Syringe movement calibration fit updated.")
        self._update_estimated_duration()

    def _start_closed_loop_preposition(self) -> None:
        self.controller.start_all_acquisition()
        current = self.controller.latest_pressure_mmhg
        target = self.start_pressure.value()
        if current is None:
            self._append_status("Closed-loop start requested. Waiting for calibrated pressure before pre-positioning to start pressure.")
            self.closed_loop_preposition_active = True
            return
        self._move_pump_toward_start_pressure(current, target)

    def _move_pump_toward_start_pressure(self, current_pressure: float, target_pressure: float) -> None:
        direction = "WDR" if current_pressure > target_pressure else "INF"
        self.closed_loop_preposition_active = True
        self.controller.pump_run(
            {
                "direction": direction,
                "rate": self.pump_rate.value(),
                "rate_units": "ML/MIN",
                "mode": "continuous",
                "volume_ml": 0,
                "motion_seconds": 0,
            }
        )
        self._append_status(
            f"Pre-positioning to start pressure before recording: current {current_pressure:.3f} mmHg, "
            f"target {target_pressure:.3f} mmHg, pump {direction}."
        )

    def _handle_message(self, message: DeviceMessage) -> None:
        if message.message_type in {MessageType.STATUS, MessageType.ERROR, MessageType.WARNING}:
            self._update_device_status(message.source)
            return
        if message.message_type != MessageType.DATA:
            return
        if message.source == DeviceSource.PRESSURE:
            raw = int(message.payload["raw_value"])
            self.raw_value.setText(str(raw))
            if self.automated_test_active:
                self._note_pressure_watchdog_sample(raw)
            if self.recording_window_active:
                self.raw_window_values.append(raw)
                avg = sum(self.raw_window_values) / len(self.raw_window_values)
                self.raw_average.setText(f"{avg:.2f}")
            pressure = self.controller.calibration.convert_raw_pressure(raw)
            self.pressure_value.setText("Calibration unavailable" if pressure is None else f"{pressure:.3f}")
            if self.automated_test_settling_active and pressure is not None:
                self.automated_test_settling_pressure_samples.append((monotonic(), pressure))
            if self.automated_test_segment_active and pressure is not None:
                segment_target = self.automated_test_segment_target_pressure
                start_pressure = self.automated_test_segment_start_pressure
                final_target = self.automated_test_segment_final_target
                moved_away_from_target = (
                    start_pressure is not None
                    and final_target is not None
                    and abs(pressure - final_target) > abs(start_pressure - final_target) + 0.5
                )
                crossed_up = (
                    segment_target is not None
                    and self.automated_test_segment_direction > 0
                    and pressure >= segment_target
                )
                crossed_down = (
                    segment_target is not None
                    and self.automated_test_segment_direction < 0
                    and pressure <= segment_target
                )
                if crossed_up or crossed_down:
                    self.automated_test_segment_cross_count += 1
                else:
                    self.automated_test_segment_cross_count = 0
                elapsed = (
                    monotonic() - self.automated_test_segment_start_time
                    if self.automated_test_segment_start_time is not None
                    else 0.0
                )
                if moved_away_from_target and elapsed >= 1.0:
                    self.automated_test_segment_away_count += 1
                else:
                    self.automated_test_segment_away_count = 0
                if self.automated_test_segment_cross_count >= 2:
                    self._finish_automated_pump_segment(
                        self.automated_test_move_id,
                        f"live pressure reached {pressure:.3f} mmHg for segment target {segment_target:.3f} mmHg "
                        f"on {self.automated_test_segment_cross_count} consecutive samples",
                    )
                elif self.automated_test_segment_away_count >= 3:
                    self._finish_automated_pump_segment(
                        self.automated_test_move_id,
                        f"pressure moved away from target {final_target:.3f} mmHg; measured {pressure:.3f} mmHg "
                        f"on {self.automated_test_segment_away_count} consecutive samples",
                    )
            if self.closed_loop_preposition_active and pressure is not None:
                target = self.start_pressure.value()
                if abs(pressure - target) <= 0.5:
                    self.closed_loop_preposition_active = False
                    self.controller.pump_abort()
                    self._append_status("Reached start pressure. Start logging now, then run the closed-loop test sequence.")
                elif self.controller.latest_pressure_mmhg is not None:
                    desired_direction = "WDR" if pressure > target else "INF"
                    if desired_direction != self.pump_direction.currentText():
                        self.pump_direction.setCurrentText(desired_direction)
        elif message.source == DeviceSource.FLUKE:
            resistance = float(message.payload["resistance_ohms"])
            self.resistance_value.setText(f"{resistance:.5f}")
            raw_response = str(message.payload.get("raw_response", ""))
            if raw_response:
                self.fluke_raw_response.setText(raw_response)
            if self.automated_test_settling_active:
                self.automated_test_settling_resistance_samples.append((monotonic(), resistance))
        elif message.source == DeviceSource.PUMP:
            running = "running" if message.payload["running"] else "stopped"
            self.pump_state.setText(
                f"{running}, {message.payload['direction']}, {message.payload['rate']} {message.payload['rate_units']}, "
                f"{message.payload['mode']}"
            )
        self._update_device_status(message.source)

    def _update_device_status(self, source: DeviceSource) -> None:
        controls = self.device_controls[source]
        connected = self.controller.workers[source].connected
        controls.status.setText("Connected" if connected else "Disconnected")
        controls.status.setStyleSheet(f"color: {'#167a3d' if connected else '#9b1c1c'}; font-weight: 600;")

    def _append_status(self, text: str) -> None:
        self.status_log.append(text)
