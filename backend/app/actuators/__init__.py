"""Aktoren: Status-LEDs je Parkfeld.

Symmetrisch zum Paket `sensors`: Die Hardware steckt ausschliesslich hinter
`LedBackend`, die Farblogik ist davon unabhaengig und ohne Pi testbar.
"""

from __future__ import annotations

import logging

from ..models import ParkingSystem
from .base import (LedBackend, NullLedBackend, SimulatedLedBackend,
                   colors_for, test_pattern)

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
    specs = led_specs(system)
    verdrahtet = [s["id"] for s in specs
                  if s["green_pin"] is not None or s["red_pin"] is not None]

    if not settings.get("leds_enabled", False):
        # Deutlich sagen, dass hier NICHTS angesteuert wird. Ohne diese Meldung
        # sieht ein abgeschalteter Ausgang exakt wie ein Hardwarefehler aus -
        # man verdrahtet, wartet und sucht den Fehler an der falschen Stelle.
        if verdrahtet:
            log.warning(
                "LED-Ansteuerung ist ABGESCHALTET (settings.leds_enabled = false), "
                "obwohl %d Feld(er) LED-Pins konfiguriert haben. Es wird KEINE "
                "LED geschaltet. Zum Einschalten in %s setzen: "
                '"leds_enabled": true', len(verdrahtet), "parking_layout.json")
        else:
            log.info("Keine Status-LEDs konfiguriert.")
        return NullLedBackend(
            "LED-Ansteuerung ist abgeschaltet "
            "(settings.leds_enabled = false).")

    if not verdrahtet:
        log.warning("leds_enabled ist gesetzt, aber kein Feld hat LED-Pins.")
        return NullLedBackend("Kein Parkfeld hat LED-Pins konfiguriert.")

    if sensor_mode != "gpio":
        return SimulatedLedBackend([s["id"] for s in specs])

    try:
        from .gpio import GpioLedBackend

        return GpioLedBackend(
            specs, active_high=bool(settings.get("led_active_high", True))
        )
    except ImportError as exc:
        # Bewusst KEIN Abbruch: Die Parkplatzanzeige ist wichtiger als die
        # LEDs. Aber laut und mit Grund, damit es nicht wieder still bleibt.
        grund = (f"LED-Ausgabe nicht moeglich - gpiozero fehlt ({exc}). "
                 "Auf dem Pi: pip install -r requirements-pi.txt")
        log.error("%s", grund)
        return NullLedBackend(grund)
    except Exception as exc:  # noqa: BLE001
        grund = f"LED-Ausgabe konnte nicht gestartet werden: {exc}"
        log.error("%s", grund)
        return NullLedBackend(grund)


__all__ = [
    "LedBackend",
    "NullLedBackend",
    "SimulatedLedBackend",
    "colors_for",
    "test_pattern",
    "create_led_backend",
    "led_specs",
]
