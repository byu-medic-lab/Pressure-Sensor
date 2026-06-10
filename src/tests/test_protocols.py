import pytest

from protocols.fluke_protocol import compact_response, format_query, is_prompt_only_response, parse_resistance
from protocols.ne500_protocol import decode_response, diameter, direction, format_command, rate, run, stop, volume
from protocols.pressure_protocol import parse_pressure_integer


def test_pressure_integer_parsing() -> None:
    assert parse_pressure_integer(b"12345\r\n") == 12345
    assert parse_pressure_integer(" 42 ") == 42


def test_pressure_integer_rejects_negative_values() -> None:
    with pytest.raises(ValueError):
        parse_pressure_integer("-1")


def test_fluke_response_parsing() -> None:
    assert parse_resistance(" 350.123 OHM") == 350.123
    assert parse_resistance(b"+1.2345E+03\r\n") == 1234.5
    assert parse_resistance("VAL1?\r\n350.123\r\n=>\r\n") == 350.123


def test_fluke_query_formatting() -> None:
    assert format_query("VAL1?") == b"VAL1?\r"


def test_fluke_prompt_only_response_detection() -> None:
    assert is_prompt_only_response("=>\r\n") is True
    assert is_prompt_only_response(b">\r\n") is True
    assert is_prompt_only_response("350.12\r\n") is False


def test_fluke_compact_response_escapes_newlines() -> None:
    assert compact_response("350.12\r\n=>\r\n") == "350.12\\r\\n=>\\r\\n"


def test_ne500_command_formatting() -> None:
    assert format_command(" RUN ") == b"RUN\r"
    assert run() == b"RUN\r"
    assert stop() == b"STP\r"
    assert rate(5, "ML/MIN") == b"RAT 5 ML/MIN\r"
    assert direction("inf") == b"DIR INF\r"
    assert volume(0) == b"VOL 0\r"
    assert diameter(14.5) == b"DIA 14.5\r"


def test_ne500_response_decoding() -> None:
    assert decode_response(b"00S\r\n") == "00S"
