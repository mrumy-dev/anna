"""Echtes Sensor-Backend fuer den Raspberry Pi.

Verwendet die Bibliothek `gpiozero`. Ein Reed-/Magnetschalter verhaelt sich
elektrisch wie ein Taster und wird daher mit der Klasse `Button` ausgelesen:

    Reed-Schalter  ---  GPIO-Pin
                   ---  GND

Mit dem internen Pull-up (pull_up=True) liest der Pin HIGH, solange der
Schalter offen ist (kein Auto). Schliesst der Magnet den Reed-Kontakt, wird
der Pin auf GND gezogen -> `is_pressed` == True -> Feld belegt.

Nicht jeder Sensor passt zu diesem Bild. Deshalb ist die Beschaltung je Feld
konfigurierbar (siehe config/parking_layout.json):

    pull_up = true   Reed-/Taster-Kontakt gegen GND         (Standard)
    pull_up = false  Sensor zieht bei Belegung aktiv auf HIGH (z. B. PNP-Sensor)
    pull_up = null   kein interner Widerstand, externe Beschaltung
                     (dann zusaetzlich active_state true/false angeben)

`gpiozero` wird absichtlich erst hier (lazy) importiert, damit das uebrige
Projekt auch ohne installierte Bibliothek auf einem normalen Laptop laeuft.

Installation auf dem Pi (Raspberry Pi OS Bookworm oder neuer):
    pip install -r requirements-pi.txt
"""

from __future__ import annotations

import logging
import time

from .. import pins as pinmap
from .base import ChangeTracker, SensorBackend

log = logging.getLogger("anna.gpio")


class GpioSensorBackend(SensorBackend):
    name = "gpio"

    def __init__(self, specs: list[dict], bounce_time: float = 0.05):
        """specs: je Parkfeld {id, pin, invert, pull_up, active_state}."""
        # Lazy-Import: schlaegt nur fehl, wenn man dieses Backend wirklich
        # auf einem System ohne gpiozero/Hardware zu starten versucht.
        from gpiozero import Button  # noqa: WPS433 (bewusst lokal)

        self._buttons: dict[str, Button] = {}
        self._specs: dict[str, dict] = {}
        self._errors: dict[str, str] = {}
        self._tracker = ChangeTracker()
        self._bounce_time = bounce_time

        for spec in specs:
            space_id = spec["id"]
            self._specs[space_id] = spec
            pin = spec.get("pin")

            if pin is None:
                self._errors[space_id] = "Kein GPIO-Pin konfiguriert."
                log.info("Feld %s hat keinen GPIO-Pin, wird uebersprungen.",
                         space_id)
                continue

            try:
                self._buttons[space_id] = self._make_button(Button, spec)
                log.info("Feld %s -> %s (pull_up=%s, invert=%s)", space_id,
                         pinmap.describe_pin(pin), spec.get("pull_up"),
                         spec.get("invert"))
            except Exception as exc:  # noqa: BLE001 - ein Pin darf den Start nicht killen
                # Z. B. Pin bereits belegt oder ungueltig: warnen und weiter,
                # damit die restlichen Felder trotzdem funktionieren.
                self._errors[space_id] = str(exc)
                log.warning("GPIO%s fuer Feld %s nicht nutzbar: %s",
                            pin, space_id, exc)

        if not self._buttons:
            log.warning("Kein einziger GPIO-Pin konnte initialisiert werden - "
                        "es werden keine Sensordaten gelesen.")
        else:
            log.info("GPIO-Backend bereit: %d Sensor(en) aktiv.",
                     len(self._buttons))

    def _make_button(self, button_cls, spec: dict):
        pull_up = spec.get("pull_up", True)
        kwargs = {"bounce_time": self._bounce_time}
        if pull_up is None:
            # Ohne internen Widerstand verlangt gpiozero eine explizite Angabe,
            # welcher Pegel als "aktiv" gilt.
            active = spec.get("active_state")
            kwargs["active_state"] = True if active is None else bool(active)
        return button_cls(spec["pin"], pull_up=pull_up, **kwargs)

    # --- Auslesen ---------------------------------------------------------
    def _raw_level(self, space_id: str) -> int | None:
        """Roher elektrischer Pegel (1 = HIGH, 0 = LOW), unabhaengig von der
        Interpretation belegt/frei."""
        button = self._buttons.get(space_id)
        if button is None:
            return None
        try:
            return int(round(float(button.pin.state)))
        except Exception:  # noqa: BLE001
            # Fallback: aus dem interpretierten Wert zurueckrechnen. Welcher
            # Pegel "aktiv" ist, wissen wir aus unserer eigenen Konfiguration.
            try:
                spec = self._specs.get(space_id, {})
                pull_up = spec.get("pull_up", True)
                active_high = (not pull_up) if pull_up is not None \
                    else bool(spec.get("active_state", True))
                value = int(button.value)
                return value if active_high else 1 - value
            except Exception:  # noqa: BLE001
                return None

    def read_all(self) -> dict[str, bool]:
        readings: dict[str, bool] = {}
        for space_id, button in self._buttons.items():
            try:
                occupied = button.is_pressed
            except Exception as exc:  # noqa: BLE001 - Lesefehler nicht fatal
                log.warning("Feld %s konnte nicht gelesen werden: %s",
                            space_id, exc)
                self._errors[space_id] = str(exc)
                continue
            self._tracker.record(space_id, self._raw_level(space_id))
            if self._specs.get(space_id, {}).get("invert"):
                occupied = not occupied
            readings[space_id] = bool(occupied)
        return readings

    # --- Diagnose ---------------------------------------------------------
    def diagnostics(self) -> list[dict]:
        readings = self.read_all()
        rows: list[dict] = []
        for space_id, spec in self._specs.items():
            pin = spec.get("pin")
            rows.append({
                "space_id": space_id,
                "pin": pin,
                "configured_pin": spec.get("configured_pin"),
                "pin_label": pinmap.describe_pin(pin) if pin is not None else None,
                "board_pin": pinmap.BCM_TO_BOARD.get(pin) if pin is not None else None,
                "hint": pinmap.board_confusion_hint(spec["configured_pin"])
                        if spec.get("configured_pin") is not None else None,
                "raw": self._raw_level(space_id),
                "occupied": readings.get(space_id),
                "invert": bool(spec.get("invert")),
                "pull_up": spec.get("pull_up", True),
                "ok": space_id in self._buttons,
                "error": self._errors.get(space_id),
                "changes": self._tracker.changes(space_id),
                "last_change_s": self._tracker.seconds_since_change(space_id),
            })
        return rows

    def used_pins(self) -> set[int]:
        return {
            spec["pin"] for spec in self._specs.values()
            if spec.get("pin") is not None
        }

    def scan(self, duration_s: float = 6.0, interval_s: float = 0.05) -> list[dict]:
        """Beobachtet alle brauchbaren GPIO-Pins und meldet, welche sich aendern.

        Damit findet man die tatsaechliche Verdrahtung: Waehrend des Scans ein
        Auto auf ein Feld stellen oder wegnehmen - der Pin, dessen Pegel
        wechselt, ist der Pin dieses Feldes.

        Bereits konfigurierte Pins werden ueber die vorhandenen Button-Objekte
        beobachtet (ein Pin kann nicht zweimal geoeffnet werden), alle uebrigen
        Pins werden fuer die Dauer des Scans zusaetzlich geoeffnet.
        """
        from gpiozero import DigitalInputDevice  # noqa: WPS433

        used = self.used_pins()
        by_space = {
            spec["pin"]: space_id
            for space_id, spec in self._specs.items()
            if spec.get("pin") is not None
        }

        extra: dict[int, object] = {}
        for pin in pinmap.SAFE_BCM_PINS:
            if pin in used:
                continue
            try:
                extra[pin] = DigitalInputDevice(pin, pull_up=True)
            except Exception as exc:  # noqa: BLE001 - belegte Pins ueberspringen
                log.debug("Pin GPIO%s nicht scanbar: %s", pin, exc)

        def sample() -> dict[int, int]:
            levels: dict[int, int] = {}
            for space_id, spec in self._specs.items():
                pin = spec.get("pin")
                if pin is None:
                    continue
                level = self._raw_level(space_id)
                if level is not None:
                    levels[pin] = level
            for pin, device in extra.items():
                try:
                    levels[pin] = int(round(float(device.pin.state)))
                except Exception:  # noqa: BLE001
                    pass
            return levels

        try:
            first = sample()
            counts: dict[int, int] = {pin: 0 for pin in first}
            last = dict(first)
            deadline = time.monotonic() + max(0.2, duration_s)
            while time.monotonic() < deadline:
                time.sleep(interval_s)
                for pin, level in sample().items():
                    if pin in last and last[pin] != level:
                        counts[pin] = counts.get(pin, 0) + 1
                    last[pin] = level
        finally:
            for device in extra.values():
                try:
                    device.close()
                except Exception:  # noqa: BLE001
                    pass

        rows = [
            {
                "pin": pin,
                "pin_label": pinmap.describe_pin(pin),
                "board_pin": pinmap.BCM_TO_BOARD.get(pin),
                "start": first.get(pin),
                "end": last.get(pin),
                "changes": counts.get(pin, 0),
                "assigned_to": by_space.get(pin),
            }
            for pin in sorted(counts)
        ]
        rows.sort(key=lambda r: (-r["changes"], r["pin"]))
        return rows

    def close(self) -> None:
        for button in self._buttons.values():
            try:
                button.close()
            except Exception:  # noqa: BLE001 - beim Aufraeumen nicht stoeren
                pass
        self._buttons.clear()
