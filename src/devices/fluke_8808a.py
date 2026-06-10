"""Threaded Fluke 8808A worker with serial and simulation modes."""

from __future__ import annotations

import math
import random
import time
from queue import Queue
from typing import Any

from app.messages import CommandType, DeviceCommand, DeviceMessage, DeviceSource, MessageType, utc_now
from devices.base_device import BaseDeviceThread
from protocols.fluke_protocol import DEFAULT_RESISTANCE_QUERY, compact_response, format_query, is_prompt_only_response, parse_resistance


class Fluke8808AThread(BaseDeviceThread):
    """Poll a Fluke 8808A for resistance without blocking the GUI."""

    def __init__(self, sample_interval_s: float, outbound: Queue[DeviceMessage]) -> None:
        super().__init__(DeviceSource.FLUKE, sample_interval_s, outbound)
        self._start = time.monotonic()
        self._serial: Any | None = None
        self._simulation_mode = True
        self.query_command = DEFAULT_RESISTANCE_QUERY
        self._invalid_response_count = 0

    def handle_command(self, command: DeviceCommand) -> None:
        try:
            if command.command_type == CommandType.CONNECT:
                self._connect(command)
            elif command.command_type == CommandType.DISCONNECT:
                self.close()
                self.emit_status("fluke disconnected.", command.request_id)
            elif command.command_type == CommandType.TEST_CONNECTION:
                self._test_connection(command)
            elif command.command_type == CommandType.SET_PARAMETER:
                self._set_parameter(command)
            else:
                super().handle_command(command)
        except Exception as exc:
            self.emit_error(str(exc), command.request_id)

    def _connect(self, command: DeviceCommand) -> None:
        self.close()
        self.port = str(command.payload.get("port", "SIM"))
        self.baud_rate = int(command.payload.get("baud_rate", 9600))
        self._simulation_mode = bool(command.payload.get("simulation", False)) or self.port.upper() == "SIM"
        self.query_command = str(command.payload.get("query_command", self.query_command))
        if self._simulation_mode:
            self.connected = True
            self.emit_status("fluke connected in simulation mode.", command.request_id)
            return

        try:
            import serial
        except Exception as exc:
            raise RuntimeError("pyserial is required for Fluke hardware mode.") from exc

        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baud_rate,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=0.1,
            write_timeout=0.2,
        )
        self._serial.reset_input_buffer()
        self.connected = True
        self.emit_status(f"fluke connected on {self.port} at {self.baud_rate} baud.", command.request_id)

    def _test_connection(self, command: DeviceCommand) -> None:
        port = str(command.payload.get("port", "SIM"))
        simulation = bool(command.payload.get("simulation", False)) or port.upper() == "SIM"
        if simulation:
            self.emit_status("fluke simulation connection test passed.", command.request_id)
            return

        try:
            import serial
        except Exception as exc:
            raise RuntimeError("pyserial is required for Fluke connection tests.") from exc

        baud_rate = int(command.payload.get("baud_rate", 9600))
        query_command = str(command.payload.get("query_command", self.query_command))
        with serial.Serial(port=port, baudrate=baud_rate, bytesize=8, parity="N", stopbits=1, timeout=1.0, write_timeout=0.5) as serial_port:
            serial_port.reset_input_buffer()
            serial_port.write(format_query(query_command))
            serial_port.flush()
            response = serial_port.readline()
        timestamp = utc_now()
        resistance = parse_resistance(response)
        self.outbound.put(
            DeviceMessage(
                source=self.source,
                message_type=MessageType.DATA,
                timestamp=timestamp,
                payload={"resistance_ohms": resistance, "query_command": query_command},
                request_id=command.request_id,
            )
        )
        self.emit_status(f"fluke connection test read {resistance:.6g} ohms.", command.request_id)

    def _set_parameter(self, command: DeviceCommand) -> None:
        if "poll_interval_s" in command.payload:
            self.sample_interval_s = float(command.payload["poll_interval_s"])
        if "query_command" in command.payload:
            self.query_command = str(command.payload["query_command"])
        self.emit_status("fluke parameters updated.", command.request_id)

    def sample_once(self) -> None:
        if not self._simulation_mode:
            self._poll_serial_once()
            return
        timestamp = utc_now()
        elapsed = time.monotonic() - self._start
        resistance = 350.0 + 0.8 * math.sin(elapsed / 4.0) + random.uniform(-0.03, 0.03)
        self.outbound.put(
            DeviceMessage(
                source=self.source,
                message_type=MessageType.DATA,
                timestamp=timestamp,
                payload={"resistance_ohms": round(resistance, 5)},
            )
        )

    def _poll_serial_once(self) -> None:
        if self._serial is None:
            self.emit_error("Fluke serial port is not open.")
            self.acquiring = False
            return
        try:
            self._serial.reset_input_buffer()
            self._serial.write(format_query(self.query_command))
            self._serial.flush()
            response = self._read_fresh_response()
        except Exception as exc:
            self.emit_error(f"Fluke serial poll failed: {exc}")
            self.acquiring = False
            return
        timestamp = utc_now()
        if not response:
            self.emit_warning("Fluke poll timed out without a response.")
            return
        raw_response = compact_response(response)
        if is_prompt_only_response(response):
            self._invalid_response_count += 1
            if self._invalid_response_count <= 3 or self._invalid_response_count % 50 == 0:
                self.emit_warning(f"Fluke prompt-only response #{self._invalid_response_count}: {raw_response!r}")
            return
        try:
            resistance = parse_resistance(response)
        except ValueError as exc:
            self._invalid_response_count += 1
            if self._invalid_response_count <= 3 or self._invalid_response_count % 50 == 0:
                self.emit_warning(f"Ignored invalid Fluke response #{self._invalid_response_count}: {exc}")
            return
        self.outbound.put(
            DeviceMessage(
                source=self.source,
                message_type=MessageType.DATA,
                timestamp=timestamp,
                payload={
                    "resistance_ohms": resistance,
                    "query_command": self.query_command,
                    "raw_response": raw_response,
                },
            )
        )

    def _read_fresh_response(self) -> bytes:
        """Collect the response to the current query, including prompt/value multi-line replies."""
        if self._serial is None:
            return b""
        deadline = time.monotonic() + 0.4
        chunks: list[bytes] = []
        while time.monotonic() < deadline:
            chunk = self._serial.readline()
            if not chunk:
                continue
            chunks.append(chunk)
            combined = b"".join(chunks)
            if not is_prompt_only_response(combined):
                try:
                    parse_resistance(combined)
                except ValueError:
                    continue
                return combined
        return b"".join(chunks)

    def close(self) -> None:
        self.acquiring = False
        self.connected = False
        if self._serial is not None:
            try:
                self._serial.close()
            finally:
                self._serial = None
