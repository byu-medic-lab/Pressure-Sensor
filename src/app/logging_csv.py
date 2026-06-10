"""CSV logging helpers for raw data, metadata, and calibration outputs."""

from __future__ import annotations

import csv
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


class CsvRunLogger:
    """Append rows to a CSV file with stable headers."""

    def __init__(self, path: Path, headers: Iterable[str]) -> None:
        self.path = Path(path)
        self.headers = list(headers)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=self.headers, extrasaction="ignore")
        self._writer.writeheader()

    def write_row(self, row: dict[str, Any]) -> None:
        normalized = {
            key: value.isoformat() if isinstance(value, datetime) else value
            for key, value in row.items()
        }
        self._writer.writerow(normalized)
        self._file.flush()

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> "CsvRunLogger":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def write_metadata(path: Path, metadata: dict[str, Any]) -> None:
    """Write run metadata as simple key/value CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["key", "value"])
        for key, value in metadata.items():
            if is_dataclass(value):
                value = asdict(value)
            writer.writerow([key, value])

