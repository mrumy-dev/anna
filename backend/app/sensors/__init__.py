"""Auswahl des passenden Sensor-Backends.

Standard ist der Simulator. Auf dem Raspberry Pi setzt man die Umgebungs-
variable ANNA_BACKEND=gpio (siehe README), dann werden die echten GPIO-Pins
aus der Layout-Konfiguration verwendet.
"""

from __future__ import annotations

from ..models import ParkingSystem
from .base import SensorBackend
from .simulated import SimulatedSensorBackend


def create_backend(name: str, system: ParkingSystem,
                   bounce_time: float = 0.05) -> SensorBackend:
    name = (name or "simulated").lower()

    if name == "gpio":
        from .gpio import GpioSensorBackend

        pin_map = {s.id: s.gpio_pin for a in system.areas for s in a.spaces}
        invert_map = {s.id: s.invert for a in system.areas for s in a.spaces}
        return GpioSensorBackend(pin_map, invert_map, bounce_time=bounce_time)

    # Default / Entwicklung
    return SimulatedSensorBackend(system.space_ids)


__all__ = ["SensorBackend", "SimulatedSensorBackend", "create_backend"]
