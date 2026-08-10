"""Aktoren: Status-LEDs je Parkfeld.

Symmetrisch zum Paket `sensors`: Die Hardware steckt ausschliesslich hinter
`LedBackend`, die Farblogik ist davon unabhaengig und ohne Pi testbar.
"""

from __future__ import annotations

import logging

from ..models import ParkingSystem
from .base import LedBackend, NullLedBackend, SimulatedLedBackend, colors_for

log = logging.getLogger("anna.leds")


def led_specs(system: ParkingSystem) -> list[dict]:
    """Uebersetzt das Domaenenmodell in die LED-Beschaltung je Parkfeld."""
    return [
        {"id": s.id, "green_pin": s.led_green_pin, "red_pin": s.led_red_pin}
        for a in system.areas
        for s in a.spaces
    ]


def create_led_backend(system: ParkingSystem, settings: dict,
                       sensor_mode: str = "gpio") -> LedBackend:
    """Waehlt die passende LED-Ausgabe.

    - `leds_enabled` nicht gesetzt -> gar keine Ansteuerung (Standard).
      LEDs sind AUSGAENGE; ein falsch zugeordneter Pin kann Hardware
      beschaedigen. Deshalb muss die Ausgabe bewusst eingeschaltet werden,
      sobald die Verdrahtung bestaetigt ist.
    - Echtbetrieb -> echte GPIO-Ausgabe.
    - Simulator -> LED-Zustand nur im Speicher, damit die Logik am Laptop
      entwickelt und auf /diag angezeigt werden kann.
    """
    if not settings.get("leds_enabled", False):
        return NullLedBackend()

    specs = led_specs(system)
    if not any(s["green_pin"] is not None or s["red_pin"] is not None
               for s in specs):
        log.warning("leds_enabled ist gesetzt, aber kein Feld hat LED-Pins.")
        return NullLedBackend()

    if sensor_mode != "gpio":
        return SimulatedLedBackend([s["id"] for s in specs])

    from .gpio import GpioLedBackend

    return GpioLedBackend(
        specs, active_high=bool(settings.get("led_active_high", True))
    )


__all__ = [
    "LedBackend",
    "NullLedBackend",
    "SimulatedLedBackend",
    "colors_for",
    "create_led_backend",
    "led_specs",
]
