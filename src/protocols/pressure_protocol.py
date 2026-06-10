"""Protocol helpers for the raw integer pressure sensor."""

from __future__ import annotations


def parse_pressure_integer(line: bytes | str) -> int:
    """Parse a raw integer line from the pressure sensor."""
    if isinstance(line, bytes):
        text = line.decode("ascii", errors="ignore")
    else:
        text = line
    text = text.strip()
    if not text:
        raise ValueError("Empty pressure reading.")
    value = int(text)
    if value < 0:
        raise ValueError(f"Pressure reading must be positive: {value}")
    return value
