"""Base worker implementation for simulated and serial-backed devices."""

from __future__ import annotations

import threading
import time
from queue import Empty, Queue
from typing import Any

from app.messages import CommandType, DeviceCommand, DeviceMessage, DeviceSource, MessageStatus, MessageType, utc_now


class BaseDeviceThread(threading.Thread):
    """Dedicated nonblocking worker with command and outbound queues."""

    def __init__(self, source: DeviceSource, sample_interval_s: float, outbound: Queue[DeviceMessage]) -> None:
        super().__init__(name=f"{source.value}-worker", daemon=True)
        self.source = source
        self.sample_interval_s = sample_interval_s
        self.outbound = outbound
        self.commands: Queue[DeviceCommand] = Queue()
        self.connected = False
        self.acquiring = False
        self.running = True
        self.port = "SIM"
        self.baud_rate = 0
        self._last_sample_monotonic = 0.0

    def run(self) -> None:
        while self.running:
            self._process_commands()
            if self.connected and self.acquiring:
                now = time.monotonic()
                if now - self._last_sample_monotonic >= self.sample_interval_s:
                    self._last_sample_monotonic = now
                    self.sample_once()
            time.sleep(0.01)
        self.close()

    def _process_commands(self) -> None:
        while True:
            try:
                command = self.commands.get_nowait()
            except Empty:
                break
            self.handle_command(command)

    def handle_command(self, command: DeviceCommand) -> None:
        try:
            if command.command_type == CommandType.CONNECT:
                self.port = str(command.payload.get("port", "SIM"))
                self.baud_rate = int(command.payload.get("baud_rate", 0))
                self.connected = True
                self.emit_status(f"{self.source.value} connected on {self.port}.", command.request_id)
            elif command.command_type == CommandType.DISCONNECT:
                self.acquiring = False
                self.connected = False
                self.emit_status(f"{self.source.value} disconnected.", command.request_id)
            elif command.command_type == CommandType.START:
                if not self.connected:
                    raise RuntimeError(f"{self.source.value} is not connected.")
                self.acquiring = True
                self.emit_status(f"{self.source.value} acquisition started.", command.request_id)
            elif command.command_type == CommandType.STOP:
                self.acquiring = False
                self.emit_status(f"{self.source.value} acquisition stopped.", command.request_id)
            elif command.command_type == CommandType.TEST_CONNECTION:
                self.emit_status(f"{self.source.value} simulation connection test passed.", command.request_id)
            elif command.command_type == CommandType.SHUTDOWN:
                self.running = False
            else:
                self.handle_device_command(command)
        except Exception as exc:
            self.emit_error(str(exc), command.request_id)

    def handle_device_command(self, command: DeviceCommand) -> None:
        self.emit_status(f"{self.source.value} ignored {command.command_type.value}.", command.request_id)

    def sample_once(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        self.acquiring = False
        self.connected = False

    def emit_data(self, payload: dict[str, Any]) -> None:
        self.outbound.put(DeviceMessage(source=self.source, message_type=MessageType.DATA, timestamp=utc_now(), payload=payload))

    def emit_status(self, text: str, request_id: str | None = None) -> None:
        self.outbound.put(
            DeviceMessage(
                source=self.source,
                message_type=MessageType.STATUS,
                timestamp=utc_now(),
                payload={"text": text},
                request_id=request_id,
            )
        )

    def emit_error(self, error: str, request_id: str | None = None) -> None:
        self.outbound.put(
            DeviceMessage(
                source=self.source,
                message_type=MessageType.ERROR,
                timestamp=utc_now(),
                request_id=request_id,
                status=MessageStatus.ERROR,
                error=error,
            )
        )

    def emit_warning(self, text: str, request_id: str | None = None) -> None:
        self.outbound.put(
            DeviceMessage(
                source=self.source,
                message_type=MessageType.WARNING,
                timestamp=utc_now(),
                payload={"text": text},
                request_id=request_id,
                status=MessageStatus.WARNING,
            )
        )
