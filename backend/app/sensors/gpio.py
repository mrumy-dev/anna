"""Echtes Sensor-Backend fuer den Raspberry Pi.

Verwendet die Bibliothek `gpiozero`. Ein Reed-/Magnetschalter verhaelt sich
elektrisch wie ein Taster und wird daher mit der Klasse `Button` ausgelesen:

    Reed-Schalter  ---  GPIO-Pin
                   ---  GND

Mit dem internen Pull-up (pull_up=True) liest der Pin HIGH, solange der
Schalter offen ist (kein Auto). Schliesst der Magnet den Reed-Kontakt, wird
der Pin auf GND gezogen -> `is_pressed` == True -> Feld belegt.

`gpiozero` wird absichtlich erst hier (lazy) importiert, damit das uebrige
Projekt auch ohne installierte Bibliothek auf einem normalen Laptop laeuft.

Installation auf dem Pi (Raspberry Pi OS Bookworm oder neuer):
    pip install gpiozero lgpio
"""

from __future__ import annotations

import logging

from .base import SensorBackend

log = logging.getLogger("anna.gpio")


class GpioSensorBackend(SensorBackend):
    name = "gpio"

    def __init__(self, pin_map: dict[str, int], invert_map: dict[str, bool],
                 bounce_time: float = 0.05):
        # Lazy-Import: schlaegt nur fehl, wenn man dieses Backend wirklich
        # auf einem System ohne gpiozero/Hardware zu starten versucht.
        from gpiozero import Button  # noqa: WPS433 (bewusst lokal)

        self._buttons: dict[str, Button] = {}
        self._invert: dict[str, bool] = {}
        configured = 0
        for space_id, pin in pin_map.items():
            if pin is None:
                # Noch nicht verdrahtetes Feld: bleibt als "frei" sichtbar.
                log.info("Feld %s hat keinen GPIO-Pin, wird uebersprungen.", space_id)
                continue
            try:
                self._buttons[space_id] = Button(
                    pin, pull_up=True, bounce_time=bounce_time
                )
                self._invert[space_id] = invert_map.get(space_id, False)
                configured += 1
            except Exception as exc:  # noqa: BLE001 - ein Pin darf den Start nicht killen
                # Z. B. Pin bereits belegt oder ungueltig: warnen und weiter,
                # damit die restlichen Felder trotzdem funktionieren.
                log.warning("GPIO-Pin %s fuer Feld %s nicht nutzbar: %s",
                            pin, space_id, exc)

        if configured == 0:
            log.warning("Kein einziger GPIO-Pin konnte initialisiert werden - "
                        "es werden keine Sensordaten gelesen.")
        else:
            log.info("GPIO-Backend bereit: %d Sensor(en) aktiv.", configured)

    def read_all(self) -> dict[str, bool]:
        readings: dict[str, bool] = {}
        for space_id, button in self._buttons.items():
            try:
                occupied = button.is_pressed
            except Exception as exc:  # noqa: BLE001 - Lesefehler nicht fatal
                log.warning("Feld %s konnte nicht gelesen werden: %s", space_id, exc)
                continue
            if self._invert.get(space_id):
                occupied = not occupied
            readings[space_id] = occupied
        return readings

    def close(self) -> None:
        for button in self._buttons.values():
            try:
                button.close()
            except Exception:  # noqa: BLE001 - beim Aufraeumen nicht stoeren
                pass
        self._buttons.clear()
