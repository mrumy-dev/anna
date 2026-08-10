"""Tests fuer die Status-LEDs (app/actuators/).

Regel: frei = gruen, belegt = rot (0 = gruen, 1 = rot). Liefert ein Sensor gar
nichts, bleiben beide LEDs dunkel - eine dunkle Stelle ist ehrlicher als ein
gruenes Licht, das faelschlich "frei" verspricht.

Laeuft ohne Raspberry Pi ueber den gpiozero-Nachbau aus conftest.py.
"""

from __future__ import annotations

import json

import pytest

from app.actuators import (
    NullLedBackend,
    SimulatedLedBackend,
    colors_for,
    create_led_backend,
)
from app.config import load_layout
from app.main import create_app


# --- Farblogik (reine Rechnung) -------------------------------------------
def test_free_is_green():
    assert colors_for(False) == (True, False)


def test_occupied_is_red():
    assert colors_for(True) == (False, True)


def test_unknown_is_dark():
    """Sensor liefert nichts -> keine Aussage -> beide LEDs aus."""
    assert colors_for(None) == (False, False)


# --- Simulierte Ausgabe ----------------------------------------------------
def test_simulated_backend_tracks_states():
    leds = SimulatedLedBackend(["B1", "B2"])
    leds.apply({"B1": False, "B2": True})
    states = leds.states()
    assert states["B1"] == {"green": True, "red": False}
    assert states["B2"] == {"green": False, "red": True}


def test_simulated_backend_all_off():
    leds = SimulatedLedBackend(["B1"])
    leds.apply({"B1": True})
    leds.all_off()
    assert leds.states()["B1"] == {"green": False, "red": False}


# --- Auswahl des Backends --------------------------------------------------
def test_disabled_by_default():
    """LEDs sind Ausgaenge - ohne ausdrueckliche Freigabe wird nichts getrieben."""
    system, settings = load_layout()
    leds = create_led_backend(system, {}, sensor_mode="gpio")
    assert isinstance(leds, NullLedBackend)
    assert leds.name == "none"


def test_simulator_uses_in_memory_backend():
    system, _ = load_layout()
    leds = create_led_backend(system, {"leds_enabled": True},
                              sensor_mode="simulated")
    assert isinstance(leds, SimulatedLedBackend)


def test_enabled_without_pins_falls_back_to_null(tmp_path):
    layout = {
        "settings": {"leds_enabled": True},
        "areas": [{"id": "a", "name": "A", "spaces": [
            {"id": "A1", "type": "normal", "gpio_pin": 17},
        ]}],
    }
    path = tmp_path / "layout.json"
    path.write_text(json.dumps(layout), encoding="utf-8")
    system, settings = load_layout(path)
    assert isinstance(create_led_backend(system, settings), NullLedBackend)


# --- Echte GPIO-Ausgabe ----------------------------------------------------
def _gpio_leds(fake_gpio, specs, active_high=True):
    fake_gpio()
    from app.actuators.gpio import GpioLedBackend
    return GpioLedBackend(specs, active_high=active_high)


def test_gpio_leds_switch_colours(fake_gpio):
    gpio = fake_gpio()
    from app.actuators.gpio import GpioLedBackend

    leds = GpioLedBackend([{"id": "A1", "green_pin": 6, "red_pin": 12}])

    leds.apply({"A1": False})            # frei
    assert gpio.outputs[6] is True       # gruen an
    assert gpio.outputs[12] is False     # rot aus

    leds.apply({"A1": True})             # belegt
    assert gpio.outputs[6] is False
    assert gpio.outputs[12] is True

    leds.apply({"A1": None})             # Sensor liefert nichts
    assert gpio.outputs[6] is False
    assert gpio.outputs[12] is False


def test_gpio_leds_start_dark(fake_gpio):
    gpio = fake_gpio()
    from app.actuators.gpio import GpioLedBackend

    GpioLedBackend([{"id": "A1", "green_pin": 6, "red_pin": 12}])
    assert gpio.outputs[6] is False and gpio.outputs[12] is False


def test_gpio_leds_survive_broken_pin(fake_gpio):
    """Eine defekte LED darf den Start nicht verhindern."""
    gpio = fake_gpio(fail_pins=(12,))
    from app.actuators.gpio import GpioLedBackend

    leds = GpioLedBackend([{"id": "A1", "green_pin": 6, "red_pin": 12}])
    leds.apply({"A1": False})
    assert gpio.outputs[6] is True               # gruen funktioniert weiter
    assert leds.states()["A1"]["error"]          # Fehler wird gemeldet
    assert leds.health()["failed"] == ["A1"]


def test_gpio_leds_active_low(fake_gpio):
    """LED gegen 3V3 bzw. invertierender Treiber: active_high=false."""
    gpio = fake_gpio()
    from app.actuators.gpio import GpioLedBackend

    leds = GpioLedBackend([{"id": "A1", "green_pin": 6, "red_pin": 12}],
                          active_high=False)
    leds.apply({"A1": False})
    # Der Nachbau bildet gpiozero nach: on() heisst "leuchtet", unabhaengig
    # davon, welcher Pegel dafuer noetig ist.
    assert gpio.outputs[6] is True
    assert leds.states()["A1"]["green"] is True


def test_gpio_leds_close_turns_everything_off(fake_gpio):
    gpio = fake_gpio()
    from app.actuators.gpio import GpioLedBackend

    leds = GpioLedBackend([{"id": "A1", "green_pin": 6, "red_pin": 12}])
    leds.apply({"A1": True})
    assert gpio.outputs[12] is True
    leds.close()
    assert gpio.outputs[12] is False


# --- Layout-Pruefung -------------------------------------------------------
def test_layout_rejects_led_pin_on_sensor_pin(tmp_path):
    """Ein Ausgang auf einem Sensorpin ist elektrisch gefaehrlich."""
    layout = {
        "settings": {},
        "areas": [{"id": "a", "name": "A", "spaces": [
            {"id": "A1", "type": "normal", "gpio_pin": 17, "led_green_pin": 17},
        ]}],
    }
    path = tmp_path / "layout.json"
    path.write_text(json.dumps(layout), encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        load_layout(path)
    assert "GPIO17" in str(exc.value)


def test_layout_rejects_two_leds_on_same_pin(tmp_path):
    layout = {
        "settings": {},
        "areas": [{"id": "a", "name": "A", "spaces": [
            {"id": "A1", "type": "normal", "led_green_pin": 6, "led_red_pin": 6},
        ]}],
    }
    path = tmp_path / "layout.json"
    path.write_text(json.dumps(layout), encoding="utf-8")
    with pytest.raises(ValueError):
        load_layout(path)


def test_layout_resolves_led_pins_with_board_numbering(tmp_path):
    """Die Nummerierung gilt auch fuer LED-Pins."""
    layout = {
        "settings": {"numbering": "board"},
        "areas": [{"id": "a", "name": "A", "spaces": [
            {"id": "A1", "type": "normal", "led_green_pin": 31},  # Header 31 = GPIO6
        ]}],
    }
    path = tmp_path / "layout.json"
    path.write_text(json.dumps(layout), encoding="utf-8")
    system, _ = load_layout(path)
    assert system.space("A1").led_green_pin == 6


def test_real_layout_has_no_pin_conflicts():
    """Die ausgelieferte Konfiguration muss in sich stimmig sein."""
    system, _ = load_layout()
    used: dict[int, str] = {}
    for area in system.areas:
        for space in area.spaces:
            for pin, role in ((space.gpio_pin, "Sensor"),
                              (space.led_green_pin, "LED gruen"),
                              (space.led_red_pin, "LED rot")):
                if pin is None:
                    continue
                assert pin not in used, (
                    f"GPIO{pin} doppelt: {used.get(pin)} und {space.id} ({role})")
                used[pin] = f"{space.id} ({role})"


# --- Zusammenspiel mit der App --------------------------------------------
@pytest.fixture
def led_layout(tmp_path, monkeypatch):
    """Kopie der echten Konfiguration, aber mit eingeschalteten LEDs.

    Bewusst ueber eine echte Datei statt ueber ein veraendertes settings-Dict:
    So laeuft derselbe Weg wie im Betrieb, inklusive Neuladen.
    """
    from app.config import layout_path

    data = json.loads(layout_path().read_text(encoding="utf-8"))
    data["settings"]["leds_enabled"] = True
    path = tmp_path / "layout.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("ANNA_LAYOUT", str(path))
    return path


def test_app_drives_leds_from_sensor_state(fake_gpio, all_free, led_layout):
    """Ein belegtes Feld muss die rote LED schalten."""
    gpio = fake_gpio(all_free)

    def factory(system, settings):
        from app.sensors import wiring_specs
        from app.sensors.gpio import GpioSensorBackend
        return GpioSensorBackend(wiring_specs(system))

    system, _ = load_layout()
    b1 = system.space("B1")

    app = create_app(backend_factory=factory)
    app.testing = True
    client = app.test_client()

    client.get("/api/state")
    assert gpio.outputs[b1.led_green_pin] is True     # frei -> gruen
    assert gpio.outputs[b1.led_red_pin] is False

    gpio.set_level(b1.gpio_pin, 0)                    # Auto auf B1
    for _ in range(3):                                # Entprellung abwarten
        client.get("/api/state")
    assert gpio.outputs[b1.led_green_pin] is False    # belegt -> rot
    assert gpio.outputs[b1.led_red_pin] is True


def test_app_leaves_leds_dark_for_dead_sensor(fake_gpio, all_free, led_layout):
    """Sensor liefert nichts -> keine gruene Luege, beide LEDs bleiben aus."""
    system, _ = load_layout()
    b1 = system.space("B1")
    gpio = fake_gpio(all_free, fail_pins=(b1.gpio_pin,))

    def factory(sys_, settings):
        from app.sensors import wiring_specs
        from app.sensors.gpio import GpioSensorBackend
        return GpioSensorBackend(wiring_specs(sys_))

    app = create_app(backend_factory=factory)
    app.testing = True
    app.test_client().get("/api/state")

    assert gpio.outputs[b1.led_green_pin] is False
    assert gpio.outputs[b1.led_red_pin] is False


def test_diagnostics_reports_led_state(led_layout):
    app = create_app()
    app.testing = True

    data = app.test_client().get("/api/diagnostics").get_json()
    assert data["leds_enabled"] is True
    assert data["leds_mode"] == "simulated"
    row = data["spaces"][0]
    assert row["led_green_pin"] is not None
    assert row["led"] is not None


def test_diagnostics_without_leds():
    app = create_app()
    app.testing = True
    data = app.test_client().get("/api/diagnostics").get_json()
    assert data["leds_enabled"] is False
    assert data["leds_mode"] == "none"


# --- Hintergrund-Takt ------------------------------------------------------
def test_ticker_runs_without_any_browser(fake_gpio, all_free, led_layout,
                                         monkeypatch):
    """Die LEDs muessen auch stimmen, wenn niemand die Webseite offen hat.

    Ohne eigenen Takt wuerde nur ein HTTP-Aufruf messen - dann waeren die
    Status-LEDs am Modell dunkel, sobald der letzte Browser geschlossen wird.
    """
    import threading
    import time

    monkeypatch.setenv("ANNA_BACKGROUND", "1")
    monkeypatch.setenv("ANNA_BACKEND", "gpio")
    gpio = fake_gpio(all_free)
    system, _ = load_layout()
    b1 = system.space("B1")

    app = create_app()
    rt = app.config["RUNTIME"]
    try:
        assert any(t.name == "anna-leds" for t in threading.enumerate())

        # Kein einziger HTTP-Aufruf - trotzdem muss die LED folgen.
        gpio.set_level(b1.gpio_pin, 0)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if gpio.outputs.get(b1.led_red_pin):
                break
            time.sleep(0.05)

        assert gpio.outputs[b1.led_red_pin] is True
        assert gpio.outputs[b1.led_green_pin] is False
    finally:
        rt._stop_ticker()


def test_no_ticker_without_leds(monkeypatch):
    """Ohne LEDs braucht es keinen Hintergrund-Takt."""
    import threading

    monkeypatch.setenv("ANNA_BACKGROUND", "1")
    before = {t.name for t in threading.enumerate()}
    app = create_app()
    assert app.config["RUNTIME"].leds.name == "none"
    assert "anna-leds" not in ({t.name for t in threading.enumerate()} - before)
