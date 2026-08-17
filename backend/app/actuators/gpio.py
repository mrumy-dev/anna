"""Status-LEDs am Raspberry Pi ansteuern.

Je Parkfeld eine gruene und eine rote LED. Uebliche Beschaltung:

    GPIO-Pin --- Vorwiderstand (z. B. 330 Ohm) --- LED --- GND

Dabei leuchtet die LED, wenn der Pin HIGH ist ("active_high", Standard).
Haengt die LED stattdessen zwischen 3V3 und dem Pin (oder wird ueber einen
invertierenden Treiber geschaltet), leuchtet sie bei LOW - dann in der
Konfiguration `led_active_high: false` setzen.

`gpiozero` wird bewusst erst hier (lazy) importiert, damit das uebrige Projekt
ohne die Bibliothek lauffaehig bleibt.

Sicherheitshinweis: LEDs sind AUSGAENGE. Ein falsch zugeordneter Ausgangspin
kann Hardware beschaedigen, wenn er gegen einen geschlossenen Schalter oder
eine andere Quelle treibt. Deshalb wird die Ansteuerung nur aktiv, wenn in der
Konfiguration `leds_enabled: true` gesetzt ist.
"""

from __future__ import annotations

import logging

from .. import pins as pinmap
from .base import LedBackend

log = logging.getLogger("anna.leds")


class GpioLedBackend(LedBackend):
    name = "gpio"

    def __init__(self, specs: list[dict], active_high: bool = True):
        """specs: je Parkfeld {id, green_pin, red_pin}."""
        from gpiozero import LED  # noqa: WPS433 (bewusst lokal)

        super().__init__()
        self._leds: dict[str, dict] = {}
        self._specs: dict[str, dict] = {}
        self._errors: dict[str, str] = {}
        self._last: dict[str, tuple[bool, bool]] = {}
        self._active_high = active_high

        for spec in specs:
            space_id = spec["id"]
            self._specs[space_id] = spec
            pair: dict = {}
            for colour, key in (("green", "green_pin"), ("red", "red_pin")):
                pin = spec.get(key)
                if pin is None:
                    continue
                try:
                    pair[colour] = LED(pin, active_high=active_high,
                                       initial_value=False)
                    log.info("LED %s/%s -> %s", space_id, colour,
                             pinmap.describe_pin(pin))
                except Exception as exc:  # noqa: BLE001 - eine LED darf den Start nicht killen
                    self._errors[space_id] = f"{colour}: {exc}"
                    log.warning("LED-Pin GPIO%s (%s/%s) nicht nutzbar: %s",
                                pin, space_id, colour, exc)
            if pair:
                self._leds[space_id] = pair

        configured = sum(len(p) for p in self._leds.values())
        if configured:
            log.info("LED-Ausgabe bereit: %d LED(s) an %d Feld(ern), "
                     "active_high=%s.", configured, len(self._leds), active_high)
        else:
            log.warning("LED-Ausgabe eingeschaltet, aber keine einzige LED "
                        "konnte initialisiert werden.")

    # --- Ausgabe ----------------------------------------------------------
    def _write(self, states: dict[str, tuple[bool, bool]]) -> None:
        for space_id, pair in self._leds.items():
            target = states.get(space_id)
            if target is None:
                continue
            if self._last.get(space_id) == target:
                continue  # unveraendert - kein Schreibzugriff noetig
            green_on, red_on = target
            for colour, on in (("green", green_on), ("red", red_on)):
                led = pair.get(colour)
                if led is None:
                    continue
                try:
                    led.on() if on else led.off()
                except Exception as exc:  # noqa: BLE001
                    log.warning("LED %s/%s liess sich nicht schalten: %s",
                                space_id, colour, exc)
            self._last[space_id] = target

    def states(self) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for space_id, spec in self._specs.items():
            green, red = self._last.get(space_id, (False, False))
            result[space_id] = {
                "green": green,
                "red": red,
                "green_pin": spec.get("green_pin"),
                "red_pin": spec.get("red_pin"),
                "error": self._errors.get(space_id),
            }
        return result

    def health(self) -> dict:
        expected = [
            s["id"] for s in self._specs.values()
            if s.get("green_pin") is not None or s.get("red_pin") is not None
        ]
        failed = sorted(self._errors)
        return {
            "ok": len([sid for sid in expected if sid not in self._errors]),
            "total": len(expected),
            "failed": failed,
        }

    def all_off(self) -> None:
        for space_id, pair in self._leds.items():
            for led in pair.values():
                try:
                    led.off()
                except Exception:  # noqa: BLE001
                    pass
            self._last[space_id] = (False, False)

    def close(self) -> None:
        self.all_off()
        for pair in self._leds.values():
            for led in pair.values():
                try:
                    led.close()
                except Exception:  # noqa: BLE001
                    pass
        self._leds.clear()
