"""Threaded pressure sensor worker with serial and simulation modes."""

from __future__ import annotations

import math
import random
import time
from queue import Empty, Queue
from typing import Any

from app.messages import CommandType, DeviceCommand, DeviceMessage, DeviceSource, MessageType, utc_now
from devices.base_device import BaseDeviceThread
from protocols.pressure_protocol import parse_pressure_integer


class PressureSensorThread(BaseDeviceThread):
    """PuTTY-style raw integer pressure sensor worker.

    The worker owns the serial port in hardware mode. Incoming serial lines are
    timestamped immediately after ``readline`` returns and before the sample is
    queued for the GUI/controller.
    """

    def __init__(self, sample_interval_s: float, outbound: Queue[DeviceMessage]) -> None:
        super().__init__(DeviceSource.PRESSURE, sample_interval_s, outbound)
        self._start = time.monotonic()
        self._ambient_raw = 10000
        self._serial: Any | None = None
        self._simulation_mode = True
        self._invalid_line_count = 0

    def run(self) -> None:
        while self.running:
            self._process_commands()
            if self.connected and self.acquiring:
                if self._simulation_mode:
                    now = time.monotonic()
                    if now - self._last_sample_monotonic >= self.sample_interval_s:
                        self._last_sample_monotonic = now
                        self.sample_once()
                else:
                    self._read_serial_once()
            time.sleep(0.002 if self.connected and self.acquiring and not self._simulation_mode else 0.01)
        self.close()

    def handle_command(self, command: DeviceCommand) -> None:
        try:
            if command.command_type == CommandType.CONNECT:
                self._connect(command)
            elif command.command_type == CommandType.DISCONNECT:
                self.close()
                self.emit_status("pressure disconnected.", command.request_id)
            elif command.command_type == CommandType.TEST_CONNECTION:
                self._test_connection(command)
            elif command.command_type == CommandType.ZERO:
                self._zero(command)
            else:
                super().handle_command(command)
        except Exception as exc:
            self.emit_error(str(exc), command.request_id)

    def _connect(self, command: DeviceCommand) -> None:
        self.close()
        self.port = str(command.payload.get("port", "SIM"))
        self.baud_rate = int(command.payload.get("baud_rate", 115200))
        self._simulation_mode = bool(command.payload.get("simulation", False)) or self.port.upper() == "SIM"
        if self._simulation_mode:
            self.connected = True
            self.emit_status("pressure connected in simulation mode.", command.request_id)
            return

        try:
            import serial
        except Exception as exc:
            raise RuntimeError("pyserial is required for pressure sensor hardware mode.") from exc

        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baud_rate,
            timeout=0.05,
            write_timeout=0.2,
        )
        self._serial.reset_input_buffer()
        self.connected = True
        self.emit_status(f"pressure connected on {self.port} at {self.baud_rate} baud.", command.request_id)

    def _test_connection(self, command: DeviceCommand) -> None:
        port = str(command.payload.get("port", "SIM"))
        simulation = bool(command.payload.get("simulation", False)) or port.upper() == "SIM"
        if simulation:
            self.emit_status("pressure simulation connection test passed.", command.request_id)
            return

        try:
            import serial
        except Exception as exc:
            raise RuntimeError("pyserial is required for pressure sensor connection tests.") from exc

        baud_rate = int(command.payload.get("baud_rate", 115200))
        last_error: Exception | None = None
        with serial.Serial(port=port, baudrate=baud_rate, timeout=0.5, write_timeout=0.2) as serial_port:
            for _ in range(20):
                line = serial_port.readline()
                timestamp = utc_now()
                if not line:
                    continue
                try:
                    raw_value = parse_pressure_integer(line)
                except ValueError as exc:
                    last_error = exc
                    continue
                break
            else:
                detail = f" Last invalid line: {last_error}" if last_error else ""
                raise RuntimeError(f"No valid pressure integer was read during connection test.{detail}")
        self.outbound.put(
            DeviceMessage(
                source=self.source,
                message_type=MessageType.DATA,
                timestamp=timestamp,
                payload=self._sample_payload(raw_value),
                request_id=command.request_id,
            )
        )
        self.emit_status(f"pressure connection test read raw value {raw_value}.", command.request_id)

    def _zero(self, command: DeviceCommand) -> None:
        if "raw_value" in command.payload:
            self._ambient_raw = int(command.payload["raw_value"])
            self.emit_status(f"pressure ambient zero set to {self._ambient_raw}.", command.request_id)
            return
        self.emit_warning("No raw value supplied for pressure zero; current ambient zero was unchanged.", command.request_id)

    def sample_once(self) -> None:
        timestamp = utc_now()
        elapsed = time.monotonic() - self._start
        signal = 2200 * (0.5 + 0.5 * math.sin(elapsed / 5.0))
        noise = random.randint(-18, 18)
        raw_value = max(0, int(self._ambient_raw + signal + noise))
        self.outbound.put(
            DeviceMessage(
                source=self.source,
                message_type=MessageType.DATA,
                timestamp=timestamp,
                payload=self._sample_payload(raw_value),
            )
        )

    def _read_serial_once(self) -> None:
        if self._serial is None:
            self.emit_error("Pressure serial port is not open.")
            self.acquiring = False
            return
        try:
            line = self._serial.readline()
        except Exception as exc:
            self.emit_error(f"Pressure serial read failed: {exc}")
            self.acquiring = False
            return
        if not line:
            return

        timestamp = utc_now()
        try:
            raw_value = parse_pressure_integer(line)
        except ValueError as exc:
            self._invalid_line_count += 1
            self.emit_warning(f"Ignored invalid pressure line #{self._invalid_line_count}: {exc}")
            return

        self.outbound.put(
            DeviceMessage(
                source=self.source,
                message_type=MessageType.DATA,
                timestamp=timestamp,
                payload=self._sample_payload(raw_value),
            )
        )

    def _sample_payload(self, raw_value: int) -> dict[str, int]:
        return {
            "raw_value": raw_value,
            "ambient_raw": self._ambient_raw,
            "zeroed_raw": max(0, raw_value - self._ambient_raw),
        }

    def close(self) -> None:
        self.acquiring = False
        self.connected = False
        if self._serial is not None:
            try:
                self._serial.close()
            finally:
                self._serial = None
