"""Gemeinsame Test-Hilfen.

Kernstueck ist ein Nachbau von `gpiozero`, der die Semantik von `Button`
naturgetreu abbildet (Pull-up/Pull-down/active_state). Damit laesst sich die
gesamte Sensor-Logik inklusive der Beschaltungsvarianten ohne Raspberry Pi
testen - genau die Faelle, die bei der Inbetriebnahme Probleme machen.
"""

from __future__ import annotations

import sys
import types

import pytest


class FakePin:
    """Bildet den rohen elektrischen Pegel ab (1 = HIGH, 0 = LOW)."""

    def __init__(self, state: int = 1):
        self.state = state


class FakeGpio:
    """Steuert die simulierte Hardware im Test."""

    def __init__(self, levels: dict[int, int] | None = None,
                 fail_pins: tuple[int, ...] = ()):
        # Ruhezustand HIGH entspricht offenem Reed-Schalter mit Pull-up.
        self.levels: dict[int, int] = dict(levels or {})
        self.fail_pins = set(fail_pins)
        self.opened: dict[int, object] = {}

    def level(self, pin: int) -> int:
        return self.levels.get(pin, 1)

    def set_level(self, pin: int, state: int) -> None:
        """Simuliert ein Auto, das auf das Feld gestellt/entfernt wird."""
        self.levels[pin] = state
        device = self.opened.get(pin)
        if device is not None:
            device.pin.state = state


def install_fake_gpiozero(monkeypatch, levels: dict[int, int] | None = None,
                          fail_pins: tuple[int, ...] = ()) -> FakeGpio:
    """Haengt ein Fake-`gpiozero` in sys.modules und gibt die Steuerung zurueck."""
    gpio = FakeGpio(levels, fail_pins)
    module = types.ModuleType("gpiozero")

    class FakeInput:
        def __init__(self, pin, pull_up=True, bounce_time=None,
                     active_state=None):
            if pin in gpio.fail_pins:
                raise RuntimeError(f"GPIO{pin} wird bereits verwendet")
            if pin in gpio.opened:
                raise RuntimeError(f"GPIO{pin} ist bereits geoeffnet")
            self._pin_number = pin
            self._pull_up = pull_up
            self._active_state = active_state
            self.pin = FakePin(gpio.level(pin))
            gpio.opened[pin] = self

        # --- gpiozero-Semantik ---------------------------------------
        @property
        def value(self) -> int:
            raw = self.pin.state
            if self._pull_up is True:
                return 1 if raw == 0 else 0
            if self._pull_up is False:
                return 1 if raw == 1 else 0
            return 1 if (raw == 1) == bool(self._active_state) else 0

        @property
        def is_active(self) -> bool:
            return bool(self.value)

        def close(self) -> None:
            gpio.opened.pop(self._pin_number, None)

    class FakeButton(FakeInput):
        @property
        def is_pressed(self) -> bool:
            return self.is_active

    module.Button = FakeButton
    module.DigitalInputDevice = FakeInput
    monkeypatch.setitem(sys.modules, "gpiozero", module)
    return gpio


@pytest.fixture
def fake_gpio(monkeypatch):
    """Fixture-Variante: fake_gpio(levels=..., fail_pins=...)."""
    def _install(levels=None, fail_pins=()):
        return install_fake_gpiozero(monkeypatch, levels, fail_pins)
    return _install
