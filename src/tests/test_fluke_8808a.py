from queue import Queue

from app.messages import CommandType, DeviceCommand, DeviceSource, MessageType
from devices.fluke_8808a import Fluke8808AThread


def drain(queue: Queue) -> list:
    messages = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    return messages


def test_fluke_worker_simulation_connect_and_sample() -> None:
    outbound = Queue()
    worker = Fluke8808AThread(sample_interval_s=0.1, outbound=outbound)

    worker.handle_command(
        DeviceCommand(
            target=DeviceSource.FLUKE,
            command_type=CommandType.CONNECT,
            payload={"port": "SIM", "baud_rate": 9600, "simulation": True},
        )
    )
    worker.handle_command(DeviceCommand(target=DeviceSource.FLUKE, command_type=CommandType.START))
    worker.sample_once()

    messages = drain(outbound)
    assert worker.connected is True
    assert worker.acquiring is True
    data_messages = [message for message in messages if message.message_type == MessageType.DATA]
    assert data_messages
    assert "resistance_ohms" in data_messages[-1].payload


def test_fluke_worker_set_parameter_updates_poll_interval_and_query() -> None:
    outbound = Queue()
    worker = Fluke8808AThread(sample_interval_s=0.5, outbound=outbound)

    worker.handle_command(
        DeviceCommand(
            target=DeviceSource.FLUKE,
            command_type=CommandType.SET_PARAMETER,
            payload={"poll_interval_s": 1.25, "query_command": "VAL1?"},
        )
    )

    assert worker.sample_interval_s == 1.25
    assert worker.query_command == "VAL1?"


class FakeSerial:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = list(chunks)
        self.reset_count = 0

    def reset_input_buffer(self) -> None:
        self.reset_count += 1

    def write(self, data: bytes) -> None:
        self.written = data

    def flush(self) -> None:
        pass

    def readline(self) -> bytes:
        if self.chunks:
            return self.chunks.pop(0)
        return b""


def test_fluke_serial_poll_reads_multiline_fresh_response() -> None:
    outbound = Queue()
    worker = Fluke8808AThread(sample_interval_s=0.1, outbound=outbound)
    fake_serial = FakeSerial([b"=>\r\n", b"VAL1?\r\n", b"351.234\r\n"])
    worker.connected = True
    worker._simulation_mode = False
    worker._serial = fake_serial

    worker.sample_once()

    messages = drain(outbound)
    assert fake_serial.reset_count == 1
    data_messages = [message for message in messages if message.message_type == MessageType.DATA]
    assert data_messages[-1].payload["resistance_ohms"] == 351.234
    assert "351.234" in data_messages[-1].payload["raw_response"]
