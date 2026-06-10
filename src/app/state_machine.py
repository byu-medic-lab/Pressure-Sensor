"""Operational mode state machine and safety checks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AppState(str, Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    RECORDING = "recording"
    CALIBRATING_MANOMETER = "calibrating_manometer"
    CALIBRATING_SYRINGE = "calibrating_syringe"
    CLOSED_LOOP_RUNNING = "closed_loop_running"
    STOPPING = "stopping"
    ERROR = "error"


class AppMode(str, Enum):
    RAW_RECORDING = "raw_recording"
    MANOMETER_CALIBRATION = "manometer_calibration"
    SYRINGE_CALIBRATION = "syringe_calibration"
    CLOSED_LOOP_TEST = "closed_loop_test"


@dataclass(slots=True)
class SafetyContext:
    pressure_connected: bool = False
    fluke_connected: bool = False
    pump_connected: bool = False
    logging_path_selected: bool = False
    pressure_calibration_available: bool = False
    syringe_calibration_available: bool = False


class StateMachine:
    """Small explicit state machine for calibration and test workflows."""

    def __init__(self) -> None:
        self.state = AppState.IDLE
        self.last_error: str | None = None

    def transition(self, next_state: AppState) -> None:
        valid = {
            AppState.IDLE: {
                AppState.CONNECTING,
                AppState.RECORDING,
                AppState.CALIBRATING_MANOMETER,
                AppState.CALIBRATING_SYRINGE,
                AppState.CLOSED_LOOP_RUNNING,
                AppState.ERROR,
            },
            AppState.CONNECTING: {AppState.IDLE, AppState.ERROR},
            AppState.RECORDING: {AppState.STOPPING, AppState.IDLE, AppState.ERROR},
            AppState.CALIBRATING_MANOMETER: {AppState.STOPPING, AppState.IDLE, AppState.ERROR},
            AppState.CALIBRATING_SYRINGE: {AppState.STOPPING, AppState.IDLE, AppState.ERROR},
            AppState.CLOSED_LOOP_RUNNING: {AppState.STOPPING, AppState.IDLE, AppState.ERROR},
            AppState.STOPPING: {AppState.IDLE, AppState.ERROR},
            AppState.ERROR: {AppState.IDLE},
        }
        if next_state not in valid[self.state]:
            raise ValueError(f"Invalid transition from {self.state.value} to {next_state.value}")
        self.state = next_state
        if next_state != AppState.ERROR:
            self.last_error = None

    def set_error(self, error: str) -> None:
        self.state = AppState.ERROR
        self.last_error = error

    def validate_start(self, mode: AppMode, context: SafetyContext) -> list[str]:
        """Return warnings/errors that block a requested mode start."""
        errors: list[str] = []
        if mode in {AppMode.RAW_RECORDING, AppMode.MANOMETER_CALIBRATION, AppMode.SYRINGE_CALIBRATION, AppMode.CLOSED_LOOP_TEST}:
            if not context.pressure_connected:
                errors.append("Pressure sensor must be connected before data acquisition.")
            if not context.logging_path_selected:
                errors.append("Select an output folder before recording.")
        if mode in {AppMode.RAW_RECORDING, AppMode.CLOSED_LOOP_TEST} and not context.fluke_connected:
            errors.append("Fluke must be connected before resistance acquisition.")
        if mode == AppMode.SYRINGE_CALIBRATION and not context.pressure_calibration_available:
            errors.append("Pressure calibration is required before syringe calibration.")
        if mode == AppMode.CLOSED_LOOP_TEST:
            if not context.pressure_calibration_available:
                errors.append("Pressure calibration is required before closed-loop testing.")
            if not context.syringe_calibration_available:
                errors.append("Syringe calibration is required before closed-loop testing.")
            if not context.pump_connected:
                errors.append("Pump must be connected before closed-loop testing.")
        return errors

