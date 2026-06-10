"""Small OS power-management helpers for long unattended runs."""

from __future__ import annotations

import os


ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def keep_system_awake() -> bool:
    """Ask Windows to keep the system awake until cleared.

    Returns True when the request was applied. Non-Windows platforms are a no-op.
    """
    if os.name != "nt":
        return False
    try:
        import ctypes

        result = ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    except Exception:
        return False
    return bool(result)


def clear_keep_awake() -> bool:
    """Clear the keep-awake request made by keep_system_awake."""
    if os.name != "nt":
        return False
    try:
        import ctypes

        result = ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    except Exception:
        return False
    return bool(result)
