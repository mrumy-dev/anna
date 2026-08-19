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
import time

from .. import pins as pinmap
from .base import LedBackend

log = logging.getLogger("anna.leds")


class GpioLedBackend(LedBackend):
    name = "gpio"

    def __init__(self, specs: list[dict], active_high: bool = True,
                 check_shorts: bool = True):
        """specs: je Parkfeld {id, green_pin, red_pin}."""
        from gpiozero import LED  # noqa: WPS433 (bewusst lokal)

        super().__init__()
        self._leds: dict[str, dict] = {}
        self._specs: dict[str, dict] = {}
        self._errors: dict[str, str] = {}
        self._last: dict[str, tuple[bool, bool]] = {}
        # Fehler beim SCHALTEN (nicht beim Oeffnen), je Feld/Farbe.
        self._write_errors: dict[str, str] = {}
        self._active_high = active_high

        kurzschluss = self._pins_gegen_masse(specs) if check_shorts else set()

        for spec in specs:
            space_id = spec["id"]
            self._specs[space_id] = spec
            pair: dict = {}
            for colour, key in (("green", "green_pin"), ("red", "red_pin")):
                pin = spec.get(key)
                if pin is None:
                    continue
                if pin in kurzschluss:
                    # Nicht treiben! Ein Pin, der auf Masse festhaengt, zieht
                    # bei 3,3 V rund 10 mA. Bei 16 solchen Pins waeren das ein
                    # Vielfaches dessen, was die GPIO-Treiber des Pi vertragen
                    # (16 mA je Pin, ca. 50 mA gesamt) - und leuchten wuerde
                    # trotzdem nichts, weil keine LED im Strompfad liegt.
                    self._errors[f"{space_id}/{colour}"] = (
                        f"GPIO{pin} haengt auf Masse fest (kein LED-Strompfad) "
                        f"- Ausgang gesperrt, sonst droht Ueberlast")
                    log.error("LED-Pin GPIO%s (%s/%s) haengt auf MASSE fest. "
                              "Ausgang wird NICHT getrieben. Verdrahtung "
                              "pruefen: Liegt die LED wirklich im Strompfad?",
                              pin, space_id, colour)
                    continue
                try:
                    pair[colour] = LED(pin, active_high=active_high,
                                       initial_value=False)
                    log.info("LED %s/%s -> %s", space_id, colour,
                             pinmap.describe_pin(pin))
                except Exception as exc:  # noqa: BLE001 - eine LED darf den Start nicht killen
                    self._errors[f"{space_id}/{colour}"] = str(exc)
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

    # --- Schutzpruefung ---------------------------------------------------
    @staticmethod
    def _pins_gegen_masse(specs: list[dict]) -> set[int]:
        """Findet LED-Pins, die von aussen auf Masse gezogen werden.

        Verfahren: Pin kurz als Eingang MIT internem Pull-up (rund 50 kOhm)
        lesen. Haengt dort eine LED mit Vorwiderstand gegen Masse, sperrt die
        LED bei den winzigen 66 uA aus dem Pull-up - der Pin liest HIGH. Liest
        er trotz Pull-up LOW, liegt ein sehr viel niederohmigerer Weg zur Masse
        an, in dem KEINE LED sitzt (z. B. Vorwiderstand direkt gegen Masse oder
        eine Bruecke).

        Solche Pins duerfen nicht getrieben werden: Sie leuchten nicht und
        ziehen dauerhaft Strom weit ueber dem, was die GPIO-Treiber des Pi
        vertragen.
        """
        try:
            from gpiozero import Device  # noqa: WPS433
        except Exception as exc:  # noqa: BLE001
            # Die Pruefung ist eine Zusatzsicherung - sie darf den Start
            # niemals verhindern. Ohne sie wird eben nichts gesperrt.
            log.debug("Kurzschlusspruefung nicht moeglich: %s", exc)
            return set()

        verdaechtig: set[int] = set()
        pins = [
            p for s in specs
            for p in (s.get("green_pin"), s.get("red_pin"))
            if p is not None
        ]
        for pin in pins:
            geraet = None
            try:
                geraet = Device.pin_factory.pin(pin)
                geraet.function = "input"
                geraet.pull = "up"
                time.sleep(0.002)          # Pegel einschwingen lassen
                if geraet.state < 0.5:
                    verdaechtig.add(pin)
            except Exception as exc:  # noqa: BLE001 - Pruefung darf nie stoeren
                log.debug("GPIO%s liess sich nicht vorpruefen: %s", pin, exc)
            finally:
                if geraet is not None:
                    try:
                        geraet.close()
                    except Exception:  # noqa: BLE001
                        pass
        if verdaechtig:
            log.error("Diese LED-Pins haengen auf Masse fest und werden NICHT "
                      "getrieben: %s", ", ".join(f"GPIO{p}" for p in sorted(verdaechtig)))
        return verdaechtig

    # --- Ausgabe ----------------------------------------------------------
    def _write(self, states: dict[str, tuple[bool, bool]]) -> None:
        for space_id, pair in self._leds.items():
            target = states.get(space_id)
            if target is None:
                continue
            if self._last.get(space_id) == target:
                continue  # unveraendert - kein Schreibzugriff noetig

            green_on, red_on = target
            ok = True
            for colour, on in (("green", green_on), ("red", red_on)):
                led = pair.get(colour)
                if led is None:
                    continue
                try:
                    led.on() if on else led.off()
                    self._write_errors.pop(f"{space_id}/{colour}", None)
                except Exception as exc:  # noqa: BLE001
                    ok = False
                    self._write_errors[f"{space_id}/{colour}"] = str(exc)
                    log.warning("LED %s/%s liess sich nicht schalten: %s",
                                space_id, colour, exc)

            if ok:
                self._last[space_id] = target
            else:
                # NICHT merken, wenn das Schreiben fehlschlug. Sonst haelt die
                # Abkuerzung oben das Feld fuer immer im falschen Zustand fest -
                # die LED bliebe dunkel, waehrend die Diagnose "alles gut"
                # meldet. Beim naechsten Takt wird es erneut versucht.
                self._last.pop(space_id, None)

    def known_ids(self) -> list[str]:
        return list(self._leds)

    def _errors_for(self, space_id: str) -> str | None:
        """Alle Fehler eines Feldes - Oeffnen UND Schalten, je Farbe."""
        teile = [
            f"{key.split('/')[-1]}: {msg}"
            for key, msg in list(self._errors.items()) + list(self._write_errors.items())
            if key.split("/")[0] == space_id
        ]
        return " | ".join(teile) if teile else None

    def states(self) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for space_id, spec in self._specs.items():
            green, red = self._last.get(space_id, (False, False))
            result[space_id] = {
                "green": green,
                "red": red,
                "green_pin": spec.get("green_pin"),
                "red_pin": spec.get("red_pin"),
                "error": self._errors_for(space_id),
            }
        return result

    def health(self) -> dict:
        """Zaehlt einzelne LEDs, nicht Felder - 16 LEDs, nicht 8 Felder."""
        erwartet = [
            f"{s['id']}/{colour}"
            for s in self._specs.values()
            for colour, key in (("green", "green_pin"), ("red", "red_pin"))
            if s.get(key) is not None
        ]
        kaputt = sorted(set(self._errors) | set(self._write_errors))
        return {
            "ok": len([k for k in erwartet if k not in kaputt]),
            "total": len(erwartet),
            "failed": [k for k in kaputt if k in erwartet],
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
