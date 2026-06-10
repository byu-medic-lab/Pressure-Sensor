"""Run the NE-500/NE-501 syringe pump in INF direction for 10 seconds.

This standalone script uses the same NE500PumpThread command-queue path as the
GUI. It does not write to serial directly.

Default command:
    python pump_push_water_10s.py

Defaults:
    port: COM8
    baud: 19200
    direction: INF
    rate: 60 mL/min
    duration: 10 seconds
"""

from __future__ import annotations

import argparse
from queue import Empty, Queue
from time import monotonic, sleep

from app.messages import CommandType, DeviceCommand, DeviceMessage, DeviceSource, MessageType
from devices.ne500_pump import NE500PumpThread


def send(worker: NE500PumpThread, command_type: CommandType, payload: dict | None = None) -> str:
    command = DeviceCommand(target=DeviceSource.PUMP, command_type=command_type, payload=payload or {})
    worker.commands.put(command)
    return command.request_id


def drain_messages(outbound: Queue[DeviceMessage]) -> list[DeviceMessage]:
    messages: list[DeviceMessage] = []
    while True:
        try:
            messages.append(outbound.get_nowait())
        except Empty:
            return messages


def print_messages(outbound: Queue[DeviceMessage]) -> None:
    for message in drain_messages(outbound):
        if message.message_type == MessageType.DATA:
            continue
        text = message.error or message.payload.get("text") or f"{message.source.value}: {message.message_type.value}"
        print(text)


def wait_for_request(outbound: Queue[DeviceMessage], request_id: str, timeout_s: float) -> None:
    deadline = monotonic() + timeout_s
    while monotonic() < deadline:
        for message in drain_messages(outbound):
            text = message.error or message.payload.get("text") or f"{message.source.value}: {message.message_type.value}"
            if message.message_type != MessageType.DATA:
                print(text)
            if message.request_id == request_id:
                if message.message_type == MessageType.ERROR:
                    raise RuntimeError(str(message.error or text))
                return
        sleep(0.05)
    raise TimeoutError(f"Timed out waiting for pump command {request_id}.")


def run_pump(port: str, baud: int, rate: float, units: str, duration: float) -> None:
    outbound: Queue[DeviceMessage] = Queue()
    worker = NE500PumpThread(sample_interval_s=0.25, outbound=outbound)
    worker.start()
    try:
        print(f"Connecting to pump on {port} at {baud} baud using the GUI pump worker path.")
        request_id = send(worker, CommandType.CONNECT, {"port": port, "baud_rate": baud, "simulation": False})
        wait_for_request(outbound, request_id, timeout_s=5.0)

        request_id = send(
            worker,
            CommandType.RUN,
            {
                "direction": "INF",
                "rate": rate,
                "rate_units": units,
                "mode": "continuous",
                "volume_ml": 0,
                "motion_seconds": duration,
            },
        )
        wait_for_request(outbound, request_id, timeout_s=8.0)
        print(f"Pushing water for {duration:g} seconds. Press Ctrl+C to stop early.")
        deadline = monotonic() + duration
        while monotonic() < deadline:
            print_messages(outbound)
            sleep(0.2)
    finally:
        print("Sending pump stop.")
        request_id = send(worker, CommandType.ABORT)
        try:
            wait_for_request(outbound, request_id, timeout_s=5.0)
        finally:
            send(worker, CommandType.SHUTDOWN)
            worker.join(timeout=2.0)
            print("Pump worker shut down.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Push water with the NE-500/NE-501 syringe pump for 10 seconds.")
    parser.add_argument("--port", default="COM8", help="Pump serial port. Default: COM8")
    parser.add_argument("--baud", type=int, default=19200, help="Pump baud rate. Default: 19200")
    parser.add_argument("--rate", type=float, default=60.0, help="Pump rate. Default: 60")
    parser.add_argument("--units", default="ML/MIN", help="Pump rate units. Default: ML/MIN")
    parser.add_argument("--duration", type=float, default=10.0, help="Run duration in seconds. Default: 10")
    args = parser.parse_args()
    run_pump(args.port, args.baud, args.rate, args.units.upper(), args.duration)


if __name__ == "__main__":
    main()
