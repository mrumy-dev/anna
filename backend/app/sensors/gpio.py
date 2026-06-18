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

from .base import SensorBackend


class GpioSensorBackend(SensorBackend):
    name = "gpio"

    def __init__(self, pin_map: dict[str, int], invert_map: dict[str, bool],
                 bounce_time: float = 0.05):
        # Lazy-Import: schlaegt nur fehl, wenn man dieses Backend wirklich
        # auf einem System ohne gpiozero/Hardware zu starten versucht.
        from gpiozero import Button  # noqa: WPS433 (bewusst lokal)

        self._buttons: dict[str, Button] = {}
        self._invert: dict[str, bool] = {}
        for space_id, pin in pin_map.items():
            if pin is None:
                continue
            self._buttons[space_id] = Button(
                pin, pull_up=True, bounce_time=bounce_time
            )
            self._invert[space_id] = invert_map.get(space_id, False)

    def read_all(self) -> dict[str, bool]:
        readings: dict[str, bool] = {}
        for space_id, button in self._buttons.items():
            occupied = button.is_pressed
            if self._invert.get(space_id):
                occupied = not occupied
            readings[space_id] = occupied
        return readings

    def close(self) -> None:
        for button in self._buttons.values():
            button.close()
        self._buttons.clear()
