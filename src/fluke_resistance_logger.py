"""Standalone Fluke 8808A resistance-vs-time logger.

Run this file by itself when you want to record only the Fluke resistance
without opening the full pressure calibration GUI.
"""

from __future__ import annotations

import argparse
import csv
import html
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from typing import TextIO

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.messages import CommandType, DeviceCommand, DeviceMessage, DeviceSource, MessageType
from devices.fluke_8808a import Fluke8808AThread
from protocols.fluke_protocol import DEFAULT_RESISTANCE_QUERY


DEFAULT_OUTPUT_DIR = Path.cwd() / "fluke_logs"


class FlukeResistanceLogger(QMainWindow):
    """Small GUI for recording Fluke resistance samples to CSV and SVG."""

    def __init__(self, port: str, baud_rate: int, poll_interval_s: float, output_folder: Path) -> None:
        super().__init__()
        self.setWindowTitle("Fluke Resistance Logger")
        self.resize(820, 560)

        self.outbound: Queue[DeviceMessage] = Queue()
        self.worker: Fluke8808AThread | None = None
        self.csv_file: TextIO | None = None
        self.csv_writer: csv.writer | None = None
        self.csv_path: Path | None = None
        self.svg_path: Path | None = None
        self.first_timestamp: datetime | None = None
        self.points: list[tuple[float, float]] = []
        self.recording = False

        self.port_edit = QLineEdit(port)
        self.port_edit.setToolTip("Serial port for the Fluke 8808A. Use SIM for simulated data.")

        self.baud_spin = QSpinBox()
        self.baud_spin.setRange(300, 1_000_000)
        self.baud_spin.setValue(baud_rate)
        self.baud_spin.setToolTip("Fluke baud rate. The project default is 9600.")

        self.poll_spin = QDoubleSpinBox()
        self.poll_spin.setRange(0.02, 10.0)
        self.poll_spin.setDecimals(3)
        self.poll_spin.setSingleStep(0.05)
        self.poll_spin.setValue(poll_interval_s)
        self.poll_spin.setSuffix(" s")
        self.poll_spin.setToolTip("How often to request a resistance reading from the Fluke.")

        self.output_edit = QLineEdit(str(output_folder))
        self.output_edit.setToolTip("Folder where the CSV and graph will be saved.")

        browse_button = QPushButton("Browse")
        browse_button.setToolTip("Choose the output folder for this recording.")
        browse_button.clicked.connect(self._browse_output_folder)

        output_row = QHBoxLayout()
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(browse_button)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("Fluke port", self.port_edit)
        form.addRow("Baud rate", self.baud_spin)
        form.addRow("Poll interval", self.poll_spin)
        form.addRow("Output folder", output_row)

        self.live_label = QLabel("Resistance: -- Ohms")
        self.live_label.setToolTip("Most recent resistance reading received from the Fluke.")
        self.live_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.live_label.setStyleSheet("font-size: 24px; font-weight: 600; padding: 16px;")

        self.start_button = QPushButton("Start recording")
        self.start_button.setToolTip("Connect to the Fluke and begin writing resistance samples to CSV.")
        self.start_button.clicked.connect(self.start_recording)

        self.stop_button = QPushButton("Stop recording")
        self.stop_button.setToolTip("Stop reading the Fluke, close the CSV, and save the graph.")
        self.stop_button.clicked.connect(self.stop_recording)
        self.stop_button.setEnabled(False)

        button_row = QHBoxLayout()
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)

        self.status_log = QTextEdit()
        self.status_log.setReadOnly(True)
        self.status_log.setToolTip("Connection, warning, and file-save messages.")

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(self.live_label)
        layout.addLayout(button_row)
        layout.addWidget(QLabel("Status"))
        layout.addWidget(self.status_log, 1)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.queue_timer = QTimer(self)
        self.queue_timer.timeout.connect(self._drain_worker_messages)
        self.queue_timer.start(50)

    def start_recording(self) -> None:
        """Start the worker and open a new CSV file."""
        if self.recording:
            return

        output_folder = Path(self.output_edit.text()).expanduser()
        try:
            output_folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "Output folder error", f"Could not create output folder:\n{exc}")
            return

        run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_path = output_folder / f"fluke_resistance_{run_stamp}.csv"
        self.svg_path = output_folder / f"fluke_resistance_{run_stamp}.svg"

        try:
            self.csv_file = self.csv_path.open("w", newline="", encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "CSV error", f"Could not open CSV file:\n{exc}")
            return

        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(["timestamp", "time_seconds", "resistance_ohms", "raw_response"])
        self.csv_file.flush()

        self.points = []
        self.first_timestamp = None
        self.worker = Fluke8808AThread(sample_interval_s=float(self.poll_spin.value()), outbound=self.outbound)
        self.worker.start()

        port = self.port_edit.text().strip() or "COM10"
        self._send_command(
            CommandType.CONNECT,
            {
                "port": port,
                "baud_rate": int(self.baud_spin.value()),
                "simulation": port.upper() == "SIM",
                "query_command": DEFAULT_RESISTANCE_QUERY,
            },
        )
        self._send_command(CommandType.START)

        self.recording = True
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self._set_inputs_enabled(False)
        self._log(f"Recording to {self.csv_path}")

    def stop_recording(self) -> None:
        """Stop the worker, close the CSV, and write the resistance graph."""
        if not self.recording and self.worker is None:
            return

        self.recording = False
        self.stop_button.setEnabled(False)
        self._shutdown_worker()
        self._close_csv()

        if self.svg_path is not None:
            try:
                write_resistance_time_svg(self.svg_path, self.points)
                self._log(f"Saved graph to {self.svg_path}")
            except OSError as exc:
                self._log(f"Could not save graph: {exc}")

        self.start_button.setEnabled(True)
        self._set_inputs_enabled(True)
        self._log("Recording stopped.")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.stop_recording()
        event.accept()

    def _browse_output_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Choose output folder", self.output_edit.text())
        if selected:
            self.output_edit.setText(selected)

    def _set_inputs_enabled(self, enabled: bool) -> None:
        self.port_edit.setEnabled(enabled)
        self.baud_spin.setEnabled(enabled)
        self.poll_spin.setEnabled(enabled)
        self.output_edit.setEnabled(enabled)

    def _send_command(self, command_type: CommandType, payload: dict | None = None) -> None:
        if self.worker is None:
            return
        self.worker.commands.put(
            DeviceCommand(
                target=DeviceSource.FLUKE,
                command_type=command_type,
                payload=payload or {},
            )
        )

    def _shutdown_worker(self) -> None:
        if self.worker is None:
            return
        self._send_command(CommandType.STOP)
        self._send_command(CommandType.DISCONNECT)
        self._send_command(CommandType.SHUTDOWN)
        self.worker.join(timeout=2.0)
        if self.worker.is_alive():
            self._log("Warning: Fluke worker did not shut down within 2 seconds.")
        self.worker = None
        self._drain_worker_messages()

    def _close_csv(self) -> None:
        if self.csv_file is not None:
            self.csv_file.flush()
            self.csv_file.close()
            self.csv_file = None
        self.csv_writer = None
        if self.csv_path is not None:
            self._log(f"Saved CSV to {self.csv_path}")

    def _drain_worker_messages(self) -> None:
        while True:
            try:
                message = self.outbound.get_nowait()
            except Empty:
                break
            self._handle_message(message)

    def _handle_message(self, message: DeviceMessage) -> None:
        if message.message_type == MessageType.DATA and "resistance_ohms" in message.payload:
            self._record_sample(message)
            return
        if message.message_type == MessageType.ERROR:
            self._log(f"Error: {message.error}")
            return
        text = message.payload.get("text")
        if text:
            label = "Warning" if message.message_type == MessageType.WARNING else "Status"
            self._log(f"{label}: {text}")

    def _record_sample(self, message: DeviceMessage) -> None:
        resistance = float(message.payload["resistance_ohms"])
        if self.first_timestamp is None:
            self.first_timestamp = message.timestamp
        elapsed = (message.timestamp - self.first_timestamp).total_seconds()
        raw_response = str(message.payload.get("raw_response", ""))

        self.points.append((elapsed, resistance))
        self.live_label.setText(f"Resistance: {resistance:.6g} Ohms")

        if self.csv_writer is not None and self.csv_file is not None:
            self.csv_writer.writerow([message.timestamp.isoformat(), f"{elapsed:.6f}", f"{resistance:.12g}", raw_response])
            self.csv_file.flush()

    def _log(self, text: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_log.append(f"[{timestamp}] {text}")


def write_resistance_time_svg(path: Path, points: list[tuple[float, float]]) -> None:
    """Write a simple SVG line graph of resistance over time."""
    width = 1200
    height = 720
    margin_left = 95
    margin_right = 35
    margin_top = 70
    margin_bottom = 90
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom

    if not points:
        body = "<text x='600' y='360' text-anchor='middle'>No resistance samples recorded</text>"
        path.write_text(_svg_document(width, height, body), encoding="utf-8")
        return

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    if x_min == x_max:
        x_max = x_min + 1.0
    if y_min == y_max:
        padding = max(abs(y_min) * 0.02, 1.0)
        y_min -= padding
        y_max += padding
    else:
        padding = (y_max - y_min) * 0.08
        y_min -= padding
        y_max += padding

    def sx(value: float) -> float:
        return margin_left + ((value - x_min) / (x_max - x_min)) * plot_width

    def sy(value: float) -> float:
        return margin_top + plot_height - ((value - y_min) / (y_max - y_min)) * plot_height

    polyline = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in points)
    circles = "\n".join(
        f"<circle cx='{sx(x):.2f}' cy='{sy(y):.2f}' r='2.4' fill='#1f77b4' />"
        for x, y in points[:: max(1, len(points) // 300)]
    )
    x_ticks = _axis_ticks(x_min, x_max, 5)
    y_ticks = _axis_ticks(y_min, y_max, 5)

    tick_markup = []
    for tick in x_ticks:
        x = sx(tick)
        tick_markup.append(f"<line x1='{x:.2f}' y1='{margin_top + plot_height}' x2='{x:.2f}' y2='{margin_top + plot_height + 8}' stroke='#5b6775' />")
        tick_markup.append(f"<text x='{x:.2f}' y='{margin_top + plot_height + 34}' text-anchor='middle'>{tick:.1f}</text>")
    for tick in y_ticks:
        y = sy(tick)
        tick_markup.append(f"<line x1='{margin_left - 8}' y1='{y:.2f}' x2='{margin_left}' y2='{y:.2f}' stroke='#5b6775' />")
        tick_markup.append(f"<text x='{margin_left - 14}' y='{y + 5:.2f}' text-anchor='end'>{tick:.6g}</text>")

    body = f"""
    <rect x='0' y='0' width='{width}' height='{height}' fill='#f7f9fb' />
    <text x='{margin_left}' y='42' class='title'>Fluke resistance vs time</text>
    <line x1='{margin_left}' y1='{margin_top}' x2='{margin_left}' y2='{margin_top + plot_height}' stroke='#334155' stroke-width='2' />
    <line x1='{margin_left}' y1='{margin_top + plot_height}' x2='{margin_left + plot_width}' y2='{margin_top + plot_height}' stroke='#334155' stroke-width='2' />
    {''.join(tick_markup)}
    <polyline points='{html.escape(polyline)}' fill='none' stroke='#1f77b4' stroke-width='2.6' stroke-linejoin='round' stroke-linecap='round' />
    {circles}
    <text x='{margin_left + plot_width / 2:.2f}' y='{height - 28}' text-anchor='middle' class='axis-label'>Time (s)</text>
    <text x='28' y='{margin_top + plot_height / 2:.2f}' text-anchor='middle' class='axis-label' transform='rotate(-90 28 {margin_top + plot_height / 2:.2f})'>Resistance (Ohms)</text>
    """
    path.write_text(_svg_document(width, height, body), encoding="utf-8")


def _axis_ticks(min_value: float, max_value: float, count: int) -> list[float]:
    if count <= 1:
        return [min_value]
    step = (max_value - min_value) / (count - 1)
    return [min_value + step * index for index in range(count)]


def _svg_document(width: int, height: int, body: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<style>
text {{ font-family: Arial, Helvetica, sans-serif; fill: #243447; font-size: 18px; }}
.title {{ font-size: 30px; font-weight: 700; }}
.axis-label {{ font-size: 22px; }}
</style>
{body}
</svg>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record Fluke 8808A resistance vs time without the main GUI.")
    parser.add_argument("--port", default="COM10", help="Fluke serial port, or SIM for simulated data.")
    parser.add_argument("--baud", type=int, default=9600, help="Fluke baud rate.")
    parser.add_argument("--poll-interval", type=float, default=0.1, help="Seconds between Fluke readings.")
    parser.add_argument("--output-folder", default=str(DEFAULT_OUTPUT_DIR), help="Folder for CSV and SVG output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = QApplication([])
    window = FlukeResistanceLogger(
        port=args.port,
        baud_rate=args.baud,
        poll_interval_s=args.poll_interval,
        output_folder=Path(args.output_folder),
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
