"""NE-500/NE-501 pump worker with serial and simulation modes."""

from __future__ import annotations

from queue import Queue
from typing import Any

from app.messages import CommandType, DeviceCommand, DeviceMessage, DeviceSource, MessageType, utc_now
from devices.base_device import BaseDeviceThread
from protocols import ne500_protocol


class NE500PumpThread(BaseDeviceThread):
    """Pump command worker with one-command-at-a-time serial semantics."""

    def __init__(self, sample_interval_s: float, outbound: Queue[DeviceMessage]) -> None:
        super().__init__(DeviceSource.PUMP, sample_interval_s, outbound)
        self.running_pump = False
        self.direction = "INF"
        self.rate = 1.0
        self.rate_units = "ML/MIN"
        self.volume_ml: float | None = 0.0
        self.mode = "incremental"
        self.diameter_mm: float | None = None
        self.distance_mm: float | None = None
        self.rate_mm_min: float | None = None
        self.motion_seconds: float | None = None
        self._serial: Any | None = None
        self._simulation_mode = True

    def handle_command(self, command: DeviceCommand) -> None:
        try:
            if command.command_type == CommandType.CONNECT:
                self._connect(command)
            elif command.command_type == CommandType.DISCONNECT:
                self.close()
                self.emit_status("pump disconnected.", command.request_id)
            elif command.command_type == CommandType.TEST_CONNECTION:
                self._test_connection(command)
            elif command.command_type in {CommandType.STOP, CommandType.ABORT}:
                self._stop_pump(command)
            else:
                super().handle_command(command)
        except Exception as exc:
            self.emit_error(str(exc), command.request_id)

    def _connect(self, command: DeviceCommand) -> None:
        self.close()
        self.port = str(command.payload.get("port", "SIM"))
        self.baud_rate = int(command.payload.get("baud_rate", 19200))
        self._simulation_mode = bool(command.payload.get("simulation", False)) or self.port.upper() == "SIM"
        if self._simulation_mode:
            self.connected = True
            self.emit_status("pump connected in simulation mode.", command.request_id)
            return

        try:
            import serial
        except Exception as exc:
            raise RuntimeError("pyserial is required for pump hardware mode.") from exc

        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baud_rate,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=1.0,
            write_timeout=1.0,
        )
        self._serial.reset_input_buffer()
        self.connected = True
        self.emit_status(f"pump connected on {self.port} at {self.baud_rate} baud.", command.request_id)

    def _test_connection(self, command: DeviceCommand) -> None:
        port = str(command.payload.get("port", "SIM"))
        simulation = bool(command.payload.get("simulation", False)) or port.upper() == "SIM"
        if simulation:
            self.emit_status("pump simulation connection test passed.", command.request_id)
            return
        try:
            import serial
        except Exception as exc:
            raise RuntimeError("pyserial is required for pump connection tests.") from exc
        baud_rate = int(command.payload.get("baud_rate", 19200))
        with serial.Serial(port=port, baudrate=baud_rate, bytesize=8, parity="N", stopbits=1, timeout=1.0, write_timeout=1.0) as serial_port:
            serial_port.write(ne500_protocol.stop())
            serial_port.flush()
            response = serial_port.readline()
        self.emit_status(f"pump connection test sent STP; response: {ne500_protocol.decode_response(response) or '<none>'}", command.request_id)

    def handle_device_command(self, command: DeviceCommand) -> None:
        if command.command_type == CommandType.RUN:
            if not self.connected:
                raise RuntimeError("Pump is not connected.")
            self.direction = str(command.payload.get("direction", self.direction))
            self.rate = float(command.payload.get("rate", self.rate))
            self.rate_units = str(command.payload.get("rate_units", self.rate_units))
            self.volume_ml = float(command.payload.get("volume_ml", self.volume_ml or 0.0))
            self.mode = str(command.payload.get("mode", self.mode))
            self.diameter_mm = float(command.payload["diameter_mm"]) if command.payload.get("diameter_mm") else self.diameter_mm
            self.distance_mm = float(command.payload["distance_mm"]) if command.payload.get("distance_mm") else self.distance_mm
            self.rate_mm_min = float(command.payload["rate_mm_min"]) if command.payload.get("rate_mm_min") else self.rate_mm_min
            self.motion_seconds = float(command.payload["motion_seconds"]) if command.payload.get("motion_seconds") else self.motion_seconds
            if not self._simulation_mode:
                self._run_hardware_sequence()
            self.running_pump = True
            self.emit_status("Pump running.", command.request_id)
            self.sample_once()
        elif command.command_type in {CommandType.ABORT, CommandType.STOP}:
            self._stop_pump(command)
        else:
            super().handle_device_command(command)

    def sample_once(self) -> None:
        self.outbound.put(
            DeviceMessage(
                source=self.source,
                message_type=MessageType.DATA,
                timestamp=utc_now(),
                payload={
                    "running": self.running_pump,
                    "direction": self.direction,
                    "rate": self.rate,
                    "rate_units": self.rate_units,
                    "volume_ml": self.volume_ml,
                    "mode": self.mode,
                    "diameter_mm": self.diameter_mm,
                    "distance_mm": self.distance_mm,
                    "rate_mm_min": self.rate_mm_min,
                    "motion_seconds": self.motion_seconds,
                },
            )
        )

    def _run_hardware_sequence(self) -> None:
        if self._serial is None:
            raise RuntimeError("Pump serial port is not open.")
        if self.diameter_mm is not None and self.diameter_mm > 0:
            self._send_and_wait(ne500_protocol.diameter(self.diameter_mm))
        self._send_and_wait(ne500_protocol.rate(self.rate, self.rate_units))
        self._send_and_wait(ne500_protocol.direction(self.direction))
        requested_volume = 0.0 if self.mode == "continuous" else float(self.volume_ml or 0.0)
        self._send_and_wait(ne500_protocol.volume(requested_volume))
        self._send_and_wait(ne500_protocol.run())

    def _send_and_wait(self, command: bytes) -> str:
        if self._serial is None:
            raise RuntimeError("Pump serial port is not open.")
        self._serial.write(command)
        self._serial.flush()
        response = self._serial.readline()
        return ne500_protocol.decode_response(response)

    def _stop_pump(self, command: DeviceCommand) -> None:
        if self.connected and not self._simulation_mode:
            self._send_and_wait(ne500_protocol.stop())
        self.running_pump = False
        self.acquiring = False
        self.emit_status("Pump stopped.", command.request_id)
        self.sample_once()

    def close(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            finally:
                self._serial = None
        self.running_pump = False
        self.acquiring = False
        self.connected = False
