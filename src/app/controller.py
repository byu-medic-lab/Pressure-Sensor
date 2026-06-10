"""Central controller mediating GUI, workers, state, logging, and calibration."""

from __future__ import annotations

from datetime import datetime
import csv
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from app.calibration import CalibrationStore
from app.config import AppConfig
from app.logging_csv import CsvRunLogger, write_metadata
from app.messages import CommandType, DeviceCommand, DeviceMessage, DeviceSource, MessageType
from app.plot_exports import export_run_graphs
from app.state_machine import AppMode, SafetyContext, StateMachine
from devices.fluke_8808a import Fluke8808AThread
from devices.ne500_pump import NE500PumpThread
from devices.pressure_sensor import PressureSensorThread


class AppController(QObject):
    """Own workers and expose Qt-safe signals for the GUI."""

    message_received = pyqtSignal(object)
    status_changed = pyqtSignal(str)

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.outbound_queue: Queue[DeviceMessage] = Queue()
        self.state_machine = StateMachine()
        self.calibration = CalibrationStore()
        self.output_folder: Path | None = None
        self.active_run_folder: Path | None = None
        self.logger: CsvRunLogger | None = None
        self.logging_metadata_path: Path | None = None
        self.logged_rows: list[dict[str, Any]] = []
        self.closed_loop_observations: list[dict[str, Any]] = []
        self.closed_loop_settled_points: list[dict[str, Any]] = []
        self.latest_pressure_raw: int | None = None
        self.latest_pressure_mmhg: float | None = None
        self.latest_resistance_ohms: float | None = None
        self.latest_fluke_raw_response: str = ""
        self.window: Any | None = None
        self.workers = {
            DeviceSource.PRESSURE: PressureSensorThread(config.pressure_poll_interval_s, self.outbound_queue),
            DeviceSource.FLUKE: Fluke8808AThread(config.fluke_poll_interval_s, self.outbound_queue),
            DeviceSource.PUMP: NE500PumpThread(config.pump_update_interval_s, self.outbound_queue),
        }
        for worker in self.workers.values():
            worker.start()
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(50)
        self.poll_timer.timeout.connect(self._drain_worker_messages)
        self.poll_timer.start()

    def set_window(self, window: Any) -> None:
        self.window = window

    def connect_device(self, source: DeviceSource, port: str, baud_rate: int) -> None:
        self.send_command(source, CommandType.CONNECT, {"port": port, "baud_rate": baud_rate, "simulation": str(port).upper() == "SIM"})

    def disconnect_device(self, source: DeviceSource) -> None:
        self.send_command(source, CommandType.DISCONNECT)

    def test_connection(self, source: DeviceSource, port: str, baud_rate: int) -> None:
        self.send_command(source, CommandType.TEST_CONNECTION, {"port": port, "baud_rate": baud_rate, "simulation": str(port).upper() == "SIM"})

    def send_command(self, target: DeviceSource, command_type: CommandType, payload: dict[str, Any] | None = None) -> None:
        command = DeviceCommand(target=target, command_type=command_type, payload=payload or {})
        self.workers[target].commands.put(command)

    def start_all_acquisition(self) -> None:
        self.send_command(DeviceSource.PRESSURE, CommandType.START)
        self.send_command(DeviceSource.FLUKE, CommandType.START)

    def stop_all_acquisition(self) -> None:
        self.send_command(DeviceSource.PRESSURE, CommandType.STOP)
        self.send_command(DeviceSource.FLUKE, CommandType.STOP)

    def pump_run(self, payload: dict[str, Any]) -> None:
        self.send_command(DeviceSource.PUMP, CommandType.RUN, payload)

    def pump_abort(self) -> None:
        self.send_command(DeviceSource.PUMP, CommandType.ABORT)

    def start_logging(self, experiment_id: str, operator_notes: str, mode: str) -> Path:
        if self.output_folder is None:
            raise RuntimeError("Choose an output folder before starting logging.")
        if self.logger is not None:
            self.stop_logging()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_experiment_id = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in experiment_id.strip())
        name_parts = [timestamp, mode]
        if safe_experiment_id:
            name_parts.append(safe_experiment_id)
        self.active_run_folder = self.output_folder / "_".join(name_parts)
        self.active_run_folder.mkdir(parents=True, exist_ok=True)
        self.logged_rows = []
        self.closed_loop_observations = []
        self.closed_loop_settled_points = []
        data_path = self.active_run_folder / "data.csv"
        self.logger = CsvRunLogger(
            data_path,
            [
                "timestamp",
                "source",
                "raw_putty",
                "pressure_mmhg",
                "fluke_resistance_ohms",
                "fluke_raw_response",
                "pump_running",
                "pump_direction",
                "pump_rate",
                "pump_rate_units",
                "pump_mode",
                "pump_volume_ml",
                "pump_motion_seconds",
            ],
        )
        self.logging_metadata_path = self.active_run_folder / "metadata.csv"
        write_metadata(
            self.logging_metadata_path,
            {
                "created_at": datetime.now().isoformat(),
                "experiment_id": experiment_id,
                "operator_notes": operator_notes,
                "mode": mode,
                "simulation_mode": self.config.simulation_mode,
                "pressure_port": self.workers[DeviceSource.PRESSURE].port,
                "pressure_baud": self.workers[DeviceSource.PRESSURE].baud_rate,
                "fluke_port": self.workers[DeviceSource.FLUKE].port,
                "fluke_baud": self.workers[DeviceSource.FLUKE].baud_rate,
                "pump_port": self.workers[DeviceSource.PUMP].port,
                "pump_baud": self.workers[DeviceSource.PUMP].baud_rate,
                "pressure_calibration": self.calibration.pressure_fit,
                "syringe_calibration": self.calibration.syringe_fit,
                "syringe_increasing_calibration": self.calibration.syringe_increasing_fit,
                "syringe_decreasing_calibration": self.calibration.syringe_decreasing_fit,
            },
        )
        self.status_changed.emit(f"Logging started: {data_path}")
        return data_path

    def stop_logging(self) -> None:
        if self.logger is not None:
            path = self.logger.path
            self.logger.close()
            self.logger = None
            run_folder = self.active_run_folder or path.parent
            graph_paths = export_run_graphs(
                run_folder,
                self.logged_rows,
                self.calibration,
                self.closed_loop_observations,
                self.closed_loop_settled_points,
            )
            self._remove_non_plot_outputs(run_folder)
            self._write_settled_points_csv(run_folder)
            self._write_pressure_calibration_plot_points_csv(run_folder)
            graph_names = ", ".join(graph.name for graph in graph_paths)
            self.status_changed.emit(f"Logging stopped: {path}. Graphs saved: {graph_names}")

    def safety_context(self) -> SafetyContext:
        return SafetyContext(
            pressure_connected=self.workers[DeviceSource.PRESSURE].connected,
            fluke_connected=self.workers[DeviceSource.FLUKE].connected,
            pump_connected=self.workers[DeviceSource.PUMP].connected,
            logging_path_selected=self.output_folder is not None,
            pressure_calibration_available=self.calibration.pressure_fit is not None,
            syringe_calibration_available=self.calibration.syringe_fit is not None,
        )

    def validate_mode_start(self, mode: AppMode) -> list[str]:
        return self.state_machine.validate_start(mode, self.safety_context())

    def record_closed_loop_observation(self, observation: dict[str, Any]) -> None:
        """Store one observed pump move for adaptive timing and end-of-run plots."""
        self.closed_loop_observations.append(dict(observation))

    def record_closed_loop_settled_point(self, point: dict[str, Any]) -> None:
        """Store one stopped-window pressure/resistance average for end-of-run plots."""
        self.closed_loop_settled_points.append(dict(point))

    def _drain_worker_messages(self) -> None:
        while True:
            try:
                message = self.outbound_queue.get_nowait()
            except Empty:
                break
            self._record_message_for_logging(message)
            self.message_received.emit(message)
            if message.message_type in {MessageType.STATUS, MessageType.ERROR, MessageType.WARNING}:
                text = message.error or message.payload.get("text") or f"{message.source.value}: {message.message_type.value}"
                self.status_changed.emit(str(text))

    def _record_message_for_logging(self, message: DeviceMessage) -> None:
        if message.message_type != MessageType.DATA:
            return
        if message.source == DeviceSource.PRESSURE:
            self.latest_pressure_raw = int(message.payload["raw_value"])
            self.latest_pressure_mmhg = self.calibration.convert_raw_pressure(self.latest_pressure_raw)
        elif message.source == DeviceSource.FLUKE:
            self.latest_resistance_ohms = float(message.payload["resistance_ohms"])
            self.latest_fluke_raw_response = str(message.payload.get("raw_response", ""))

        if self.logger is None:
            return

        row: dict[str, Any] = {
            "timestamp": message.timestamp,
            "source": message.source.value,
            "raw_putty": self.latest_pressure_raw,
            "pressure_mmhg": self.latest_pressure_mmhg,
            "fluke_resistance_ohms": self.latest_resistance_ohms,
            "fluke_raw_response": self.latest_fluke_raw_response,
        }
        if message.source == DeviceSource.PUMP:
            row.update(
                {
                    "pump_running": message.payload.get("running"),
                    "pump_direction": message.payload.get("direction"),
                    "pump_rate": message.payload.get("rate"),
                    "pump_rate_units": message.payload.get("rate_units"),
                    "pump_mode": message.payload.get("mode"),
                    "pump_volume_ml": message.payload.get("volume_ml"),
                    "pump_motion_seconds": message.payload.get("motion_seconds"),
                }
            )
        self.logged_rows.append(dict(row))
        self.logger.write_row(row)

    def _export_calibration_points(self, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        manometer_path = folder / "manometer_calibration_points.csv"
        with manometer_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["timestamp", "reference_cm_h2o", "reference_mmhg", "average_raw"])
            writer.writeheader()
            for point in self.calibration.manometer_points:
                writer.writerow(
                    {
                        "timestamp": point.timestamp.isoformat(),
                        "reference_cm_h2o": point.reference_cm_h2o,
                        "reference_mmhg": point.reference_mmhg,
                        "average_raw": point.average_raw,
                    }
                )

    def _remove_non_plot_outputs(self, folder: Path) -> None:
        for path in folder.iterdir():
            if path.is_file() and path.suffix.lower() != ".svg" and path.name != "metadata.csv":
                path.unlink()

    def _write_settled_points_csv(self, folder: Path) -> None:
        if not self.closed_loop_settled_points:
            return
        path = folder / "plotted_pressure_resistance_points.csv"
        fieldnames = [
            "average_pressure_mmhg",
            "average_resistance_ohms",
        ]
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for point in self.closed_loop_settled_points:
                writer.writerow(
                    {
                        "average_pressure_mmhg": point.get("average_pressure_mmhg"),
                        "average_resistance_ohms": point.get("average_resistance_ohms"),
                    }
                )

    def _write_pressure_calibration_plot_points_csv(self, folder: Path) -> None:
        if not self.calibration.manometer_points:
            return
        path = folder / "pressure_cm_vs_mmhg_points.csv"
        fieldnames = ["pressure_cm_h2o", "pressure_mmhg"]
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for point in self.calibration.manometer_points:
                writer.writerow(
                    {
                        "pressure_cm_h2o": point.reference_cm_h2o,
                        "pressure_mmhg": point.reference_mmhg,
                    }
                )

    def shutdown(self) -> None:
        self.stop_logging()
        self.poll_timer.stop()
        for source in list(self.workers):
            self.send_command(source, CommandType.SHUTDOWN)
        for worker in self.workers.values():
            worker.join(timeout=2.0)
