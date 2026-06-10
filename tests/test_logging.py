import csv
from datetime import datetime, timezone
from pathlib import Path

from app.logging_csv import CsvRunLogger, write_metadata


OUTPUT_DIR = Path(__file__).parent / "_output"


def test_csv_logger_writes_headers_and_rows() -> None:
    path = OUTPUT_DIR / "run.csv"
    with CsvRunLogger(path, ["timestamp", "raw"]) as logger:
        logger.write_row({"timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc), "raw": 123})

    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert rows == [{"timestamp": "2026-01-01T00:00:00+00:00", "raw": "123"}]


def test_metadata_writer() -> None:
    path = OUTPUT_DIR / "metadata.csv"
    write_metadata(path, {"experiment_id": "demo"})
    assert "experiment_id,demo" in path.read_text(encoding="utf-8")
