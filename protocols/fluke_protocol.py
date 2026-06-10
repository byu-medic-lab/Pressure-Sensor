"""Protocol helpers for Fluke 8808A responses."""

from __future__ import annotations

import re


_NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[Ee][-+]?\d+)?")
DEFAULT_RESISTANCE_QUERY = "VAL1?"


def response_text(response: bytes | str) -> str:
    """Decode a Fluke serial response into text."""
    if isinstance(response, bytes):
        return response.decode("ascii", errors="ignore")
    return response


def compact_response(response: bytes | str, max_length: int = 120) -> str:
    """Return a single-line raw response preview for diagnostics."""
    text = response_text(response).replace("\r", "\\r").replace("\n", "\\n")
    if len(text) <= max_length:
        return text
    return f"{text[:max_length - 3]}..."


def is_prompt_only_response(response: bytes | str) -> bool:
    """Return True when the meter only echoed a command prompt, not a reading."""
    text = response_text(response).strip()
    return text in {">", "=>"}


def parse_resistance(response: bytes | str) -> float:
    """Parse the first numeric resistance value from a Fluke response.

    TODO: Confirm exact Fluke 8808A response shape in hardware testing.
    """
    text = response_text(response)
    measurement_lines = [
        line
        for line in text.splitlines()
        if "?" not in line and not is_prompt_only_response(line)
    ]
    lines = text.splitlines()
    searchable_text = "\n".join(measurement_lines) if lines else text
    matches = _NUMBER_RE.findall(searchable_text)
    if not matches:
        raise ValueError(f"No numeric resistance in response: {text!r}")
    return float(matches[-1])


def format_query(command: str = DEFAULT_RESISTANCE_QUERY) -> bytes:
    """Format a Fluke query command.

    TODO: Confirm the exact 8808A resistance query command in hardware testing.
    ``VAL1?`` is the default query used for the primary display reading.
    """
    clean = command.strip()
    if not clean:
        raise ValueError("Fluke query command cannot be empty.")
    return f"{clean}\r".encode("ascii")
