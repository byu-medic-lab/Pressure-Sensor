from queue import Queue

from app.messages import CommandType, DeviceCommand, DeviceSource, MessageType
from devices.pressure_sensor import PressureSensorThread


def drain(queue: Queue) -> list:
    messages = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    return messages


def test_pressure_worker_simulation_connect_and_sample() -> None:
    outbound = Queue()
    worker = PressureSensorThread(sample_interval_s=0.1, outbound=outbound)

    worker.handle_command(
        DeviceCommand(
            target=DeviceSource.PRESSURE,
            command_type=CommandType.CONNECT,
            payload={"port": "SIM", "baud_rate": 115200, "simulation": True},
        )
    )
    worker.handle_command(DeviceCommand(target=DeviceSource.PRESSURE, command_type=CommandType.START))
    worker.sample_once()

    messages = drain(outbound)
    assert worker.connected is True
    assert worker.acquiring is True
    data_messages = [message for message in messages if message.message_type == MessageType.DATA]
    assert data_messages
    assert {"raw_value", "ambient_raw", "zeroed_raw"} <= set(data_messages[-1].payload)


def test_pressure_worker_zero_uses_supplied_raw_value() -> None:
    outbound = Queue()
    worker = PressureSensorThread(sample_interval_s=0.1, outbound=outbound)

    worker.handle_command(
        DeviceCommand(
            target=DeviceSource.PRESSURE,
            command_type=CommandType.ZERO,
            payload={"raw_value": 1234},
        )
    )

    worker.sample_once()
    data_messages = [message for message in drain(outbound) if message.message_type == MessageType.DATA]
    assert data_messages[-1].payload["ambient_raw"] == 1234
