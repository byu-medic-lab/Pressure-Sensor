"""Structured command and message types shared by GUI, controller, and workers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class DeviceSource(str, Enum):
    PRESSURE = "pressure"
    FLUKE = "fluke"
    PUMP = "pump"
    CONTROLLER = "controller"


class CommandType(str, Enum):
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    START = "start"
    STOP = "stop"
    SET_PARAMETER = "set_parameter"
    ZERO = "zero"
    RUN = "run"
    ABORT = "abort"
    SHUTDOWN = "shutdown"
    TEST_CONNECTION = "test_connection"


class MessageType(str, Enum):
    STATUS = "status"
    DATA = "data"
    ERROR = "error"
    ACK = "ack"
    WARNING = "warning"


class MessageStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    WARNING = "warning"
    PENDING = "pending"


@dataclass(slots=True)
class DeviceCommand:
    """Command sent from the GUI/controller to a worker thread."""

    target: DeviceSource
    command_type: CommandType
    payload: dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class DeviceMessage:
    """Message sent from a worker to the controller/GUI."""

    source: DeviceSource
    message_type: MessageType
    timestamp: datetime
    payload: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    status: MessageStatus = MessageStatus.OK
    error: str | None = None


@dataclass(slots=True)
class PressureSample:
    timestamp: datetime
    raw_value: int
    pressure_mmhg: float | None = None


@dataclass(slots=True)
class ResistanceSample:
    timestamp: datetime
    resistance_ohms: float


@dataclass(slots=True)
class PumpState:
    timestamp: datetime
    running: bool
    direction: str
    rate: float
    rate_units: str
    volume_ml: float | None = None
    mode: str = "incremental"

