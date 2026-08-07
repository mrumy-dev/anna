"""Auswahl des passenden Sensor-Backends.

Standard ist der Simulator. Auf dem Raspberry Pi setzt man die Umgebungs-
variable ANNA_BACKEND=gpio (siehe README), dann werden die echten GPIO-Pins
aus der Layout-Konfiguration verwendet.
"""

from __future__ import annotations

from ..models import ParkingSystem
from .base import SensorBackend
from .simulated import SimulatedSensorBackend


def wiring_specs(system: ParkingSystem) -> list[dict]:
    """Uebersetzt das Domaenenmodell in die Beschaltungsangaben je Parkfeld."""
    return [
        {
            "id": s.id,
            "pin": s.gpio_pin,
            "configured_pin": s.configured_pin,
            "invert": s.invert,
            "pull_up": s.pull_up,
            "active_state": s.active_state,
        }
        for a in system.areas
        for s in a.spaces
    ]


def create_backend(name: str, system: ParkingSystem,
                   bounce_time: float = 0.05) -> SensorBackend:
    name = (name or "simulated").lower()

    if name == "gpio":
        from .gpio import GpioSensorBackend

        return GpioSensorBackend(wiring_specs(system), bounce_time=bounce_time)

    # Default / Entwicklung
    return SimulatedSensorBackend(system.space_ids)


__all__ = [
    "SensorBackend",
    "SimulatedSensorBackend",
    "create_backend",
    "wiring_specs",
]
