"""Protocol helpers for NE-500/NE-501 syringe pump commands."""

from __future__ import annotations


COMMAND_TERMINATOR = "\r"


def format_command(command: str) -> bytes:
    """Format an NE-500 command with the required carriage return."""
    clean = " ".join(command.strip().split())
    if not clean:
        raise ValueError("Pump command cannot be empty.")
    return f"{clean}{COMMAND_TERMINATOR}".encode("ascii")


def run() -> bytes:
    return format_command("RUN")


def stop() -> bytes:
    return format_command("STP")


def rate(value: float, units: str) -> bytes:
    return format_command(f"RAT {value:g} {units}")


def direction(value: str) -> bytes:
    value = value.upper()
    if value not in {"INF", "WDR"}:
        raise ValueError("Pump direction must be INF or WDR.")
    return format_command(f"DIR {value}")


def volume(value_ml: float) -> bytes:
    return format_command(f"VOL {value_ml:g}")


def diameter(diameter_mm: float) -> bytes:
    return format_command(f"DIA {diameter_mm:g}")


def decode_response(response: bytes | str) -> str:
    """Decode a pump response for status logging.

    TODO: Confirm exact alarm/status response fields during hardware testing.
    """
    if isinstance(response, bytes):
        return response.decode("ascii", errors="replace").strip()
    return response.strip()
