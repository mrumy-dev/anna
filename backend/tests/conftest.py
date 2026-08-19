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
        # Zustand der Ausgangspins (LEDs): {bcm_pin: leuchtet}
        self.outputs: dict[int, bool] = {}
        # Pins, die von aussen auf Masse gezogen werden
        # (Verdrahtungsfehler: Widerstand ohne LED im Strompfad)
        self.grounded: set[int] = set()

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

    class FakeLED:
        """Ausgang - bildet gpiozero.LED nach (inkl. active_high)."""

        def __init__(self, pin, active_high=True, initial_value=False):
            if pin in gpio.fail_pins:
                raise RuntimeError(f"GPIO{pin} wird bereits verwendet")
            if pin in gpio.opened:
                raise RuntimeError(f"GPIO{pin} ist bereits geoeffnet")
            self._pin_number = pin
            self.active_high = active_high
            self.value = 1 if initial_value else 0
            gpio.opened[pin] = self
            gpio.outputs[pin] = bool(initial_value)

        def on(self) -> None:
            self.value = 1
            gpio.outputs[self._pin_number] = True

        def off(self) -> None:
            self.value = 0
            gpio.outputs[self._pin_number] = False

        @property
        def is_lit(self) -> bool:
            return bool(self.value)

        def close(self) -> None:
            gpio.opened.pop(self._pin_number, None)

    class FakeRawPin:
        """Roher Pin-Zugriff, wie ihn Device.pin_factory.pin() liefert.

        Damit laesst sich die Kurzschluss-Vorpruefung testen: Ein Pin, den die
        Hardware auf Masse zieht, liest trotz Pull-up LOW.
        """

        def __init__(self, number):
            self.number = number
            self.function = "input"
            self.pull = "floating"

        @property
        def state(self) -> float:
            if self.number in gpio.grounded:
                return 0.0            # haengt auf Masse, Pull-up chancenlos
            if self.pull == "up":
                return 1.0
            if self.pull == "down":
                return 0.0
            return float(gpio.level(self.number))

        def close(self) -> None:
            pass

    class FakePinFactory:
        def pin(self, number):
            return FakeRawPin(number)

    class FakeDevice:
        pin_factory = FakePinFactory()

    module.Button = FakeButton
    module.DigitalInputDevice = FakeInput
    module.LED = FakeLED
    module.Device = FakeDevice
    monkeypatch.setitem(sys.modules, "gpiozero", module)
    return gpio


@pytest.fixture
def fake_gpio(monkeypatch):
    """Fixture-Variante: fake_gpio(levels=..., fail_pins=...)."""
    def _install(levels=None, fail_pins=()):
        return install_fake_gpiozero(monkeypatch, levels, fail_pins)
    return _install


# --- Angaben aus der echten Layout-Konfiguration --------------------------
# Bewusst abgeleitet statt fest verdrahtet: Kommt ein Parkfeld dazu, muessen
# die Tests nicht angefasst werden.
def _layout():
    from app.config import load_layout
    system, _ = load_layout()
    return [s for a in system.areas for s in a.spaces]


@pytest.fixture
def space_count() -> int:
    """Anzahl Parkfelder laut config/parking_layout.json."""
    return len(_layout())


@pytest.fixture
def sensor_pins() -> tuple[int, ...]:
    """Alle konfigurierten Sensor-Pins (BCM)."""
    return tuple(s.gpio_pin for s in _layout() if s.gpio_pin is not None)


@pytest.fixture
def all_free(sensor_pins) -> dict[int, int]:
    """Pegel-Vorgabe: alle Reed-Kontakte offen = alle Felder frei."""
    return {pin: 1 for pin in sensor_pins}


@pytest.fixture(autouse=True)
def _test_backend(monkeypatch):
    """Im Test laeuft standardmaessig der Simulator.

    Im ECHTBETRIEB ist gpio der Standard (localhost = Produktion, siehe
    app/main.py:_default_backend). Fuer die Testsuite waere das unbrauchbar,
    weil auf einem Entwicklungsrechner keine GPIO-Hardware existiert. Tests, die
    den Echtbetrieb pruefen, setzen ANNA_BACKEND selbst oder schleusen ein
    Backend ueber create_app(backend_factory=...) ein.

    Dass der Produktionsstandard wirklich gpio ist, prueft
    test_diagnostics.py::test_production_default_backend_is_gpio.
    """
    monkeypatch.setenv("ANNA_BACKEND", "simulated")
    # Kein Hintergrund-Takt in Tests: die Messung soll ausschliesslich
    # durch den Testcode angestossen werden, sonst waeren Zusicherungen
    # ueber Entprellung und LED-Zustand nicht reproduzierbar.
    monkeypatch.setenv("ANNA_BACKGROUND", "0")
