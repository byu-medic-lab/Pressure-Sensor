from queue import Queue

from app.messages import CommandType, DeviceCommand, DeviceSource, MessageType
from devices.ne500_pump import NE500PumpThread


def drain(queue: Queue) -> list:
    messages = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    return messages


def test_pump_worker_simulation_run_and_abort() -> None:
    outbound = Queue()
    worker = NE500PumpThread(sample_interval_s=0.1, outbound=outbound)

    worker.handle_command(
        DeviceCommand(
            target=DeviceSource.PUMP,
            command_type=CommandType.CONNECT,
            payload={"port": "SIM", "baud_rate": 19200, "simulation": True},
        )
    )
    worker.handle_command(
        DeviceCommand(
            target=DeviceSource.PUMP,
            command_type=CommandType.RUN,
            payload={"direction": "WDR", "rate": 2.5, "mode": "incremental", "volume_ml": 5, "diameter_mm": 14.5},
        )
    )
    worker.handle_command(DeviceCommand(target=DeviceSource.PUMP, command_type=CommandType.ABORT))

    data_messages = [message for message in drain(outbound) if message.message_type == MessageType.DATA]
    assert data_messages[-2].payload["running"] is True
    assert data_messages[-2].payload["direction"] == "WDR"
    assert data_messages[-2].payload["diameter_mm"] == 14.5
    assert data_messages[-1].payload["running"] is False
