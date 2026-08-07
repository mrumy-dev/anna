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
    """Erzeugt das Sensor-Backend. Standard ist der Echtbetrieb ("gpio")."""
    name = (name or "gpio").lower()

    if name == "simulated":
        return SimulatedSensorBackend(system.space_ids)

    if name != "gpio":
        raise ValueError(
            f"Unbekanntes ANNA_BACKEND={name!r}. Erlaubt: 'gpio' (Echtbetrieb, "
            f"Standard) oder 'simulated' (Entwicklung ohne Hardware)."
        )

    try:
        # gpiozero wird erst im Konstruktor importiert (lazy), deshalb muss
        # auch der Aufruf innerhalb des try stehen.
        from .gpio import GpioSensorBackend

        return GpioSensorBackend(wiring_specs(system), bounce_time=bounce_time)
    except ImportError as exc:
        # Klartext statt nacktem ImportError - das passiert genau dann, wenn
        # jemand den Echtbetrieb auf einem Rechner ohne GPIO startet.
        raise RuntimeError(
            "Der Echtbetrieb (ANNA_BACKEND=gpio) benoetigt die Bibliothek "
            f"gpiozero, sie ist hier nicht installiert ({exc}).\n"
            "  Auf dem Raspberry Pi:   pip install -r requirements-pi.txt\n"
            "  Ohne Hardware testen:   ANNA_BACKEND=simulated python run.py"
        ) from exc


__all__ = [
    "SensorBackend",
    "SimulatedSensorBackend",
    "create_backend",
    "wiring_specs",
]
