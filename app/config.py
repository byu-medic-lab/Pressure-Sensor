"""Configuration models and serial-port discovery helpers."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SerialSettings:
    port: str = "SIM"
    baud_rate: int = 9600
    timeout_s: float = 0.2


@dataclass(slots=True)
class DeviceConfig:
    pressure: SerialSettings = field(default_factory=lambda: SerialSettings(port="", baud_rate=115200))
    fluke: SerialSettings = field(default_factory=lambda: SerialSettings(port="", baud_rate=9600))
    pump: SerialSettings = field(default_factory=lambda: SerialSettings(port="", baud_rate=19200))


@dataclass(slots=True)
class AppConfig:
    simulation_mode: bool = True
    devices: DeviceConfig = field(default_factory=DeviceConfig)
    fluke_poll_interval_s: float = 0.1
    pressure_poll_interval_s: float = 0.1
    pump_update_interval_s: float = 0.2


@dataclass(frozen=True, slots=True)
class SerialPortInfo:
    device: str
    description: str = ""
    manufacturer: str = ""

    @property
    def label(self) -> str:
        parts = [self.device]
        if self.description:
            parts.append(self.description)
        if self.manufacturer:
            parts.append(self.manufacturer)
        return " - ".join(parts)


def discover_serial_ports(include_simulated: bool = True) -> list[SerialPortInfo]:
    """Discover available serial ports, gracefully handling missing pyserial."""
    ports: list[SerialPortInfo] = []
    if include_simulated:
        ports.append(SerialPortInfo(device="SIM", description="Simulation device", manufacturer="Software"))
    try:
        from serial.tools import list_ports
    except Exception:
        return ports

    for port in list_ports.comports():
        ports.append(
            SerialPortInfo(
                device=port.device,
                description=port.description or "",
                manufacturer=port.manufacturer or "",
            )
        )
    return ports
