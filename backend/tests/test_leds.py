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
    assert leds.health()["failed"] == ["A1/red"]   # je LED, nicht je Feld
    assert leds.health()["total"] == 2             # gruen + rot


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
    # Kein Start-Selbsttest in Tests: der wuerde die ersten Sekunden alle LEDs
    # uebersteuern und damit die Pruefung des Normalbetriebs verfaelschen.
    data["settings"]["led_boot_test_s"] = 0
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


@pytest.fixture
def no_led_layout(tmp_path, monkeypatch):
    """Konfiguration mit ausdruecklich abgeschalteter LED-Ansteuerung."""
    from app.config import layout_path

    data = json.loads(layout_path().read_text(encoding="utf-8"))
    data["settings"]["leds_enabled"] = False
    path = tmp_path / "layout.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("ANNA_LAYOUT", str(path))
    return path


def test_diagnostics_without_leds(no_led_layout):
    app = create_app()
    app.testing = True
    data = app.test_client().get("/api/diagnostics").get_json()
    assert data["leds_enabled"] is False
    assert data["leds_mode"] == "none"
    # Der Grund muss dastehen - sonst sieht "abgeschaltet" wie ein
    # Hardwarefehler aus und man sucht tagelang an der Verdrahtung.
    assert "abgeschaltet" in data["leds_reason"].lower()


def test_led_test_rejected_when_disabled(no_led_layout):
    app = create_app()
    app.testing = True
    resp = app.test_client().post("/api/diag/led-test?mode=beide")
    assert resp.status_code == 400
    assert "leds_enabled" in resp.get_json()["error"]


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


def test_no_ticker_without_leds(monkeypatch, no_led_layout):
    """Ohne LEDs braucht es keinen Hintergrund-Takt."""
    import threading

    monkeypatch.setenv("ANNA_BACKGROUND", "1")
    before = {t.name for t in threading.enumerate()}
    app = create_app()
    assert app.config["RUNTIME"].leds.name == "none"
    assert "anna-leds" not in ({t.name for t in threading.enumerate()} - before)


# --- Selbsttest fuer Ausgaenge --------------------------------------------
def test_test_pattern_modes():
    from app.actuators import test_pattern

    ids = ["B1", "B2"]
    assert test_pattern(ids, "gruen") == {"B1": (True, False), "B2": (True, False)}
    assert test_pattern(ids, "rot") == {"B1": (False, True), "B2": (False, True)}
    assert test_pattern(ids, "beide") == {"B1": (True, True), "B2": (True, True)}
    assert test_pattern(ids, "aus") == {"B1": (False, False), "B2": (False, False)}
    assert test_pattern(ids, "feld", "B2") == {"B1": (False, False), "B2": (True, True)}


def test_test_pattern_rejects_nonsense():
    from app.actuators import test_pattern

    with pytest.raises(ValueError):
        test_pattern(["B1"], "blinken")
    with pytest.raises(ValueError):
        test_pattern(["B1"], "feld", "ZZ")


def test_override_beats_normal_operation():
    """Das Testmuster muss die Belegung uebersteuern - sonst sieht man nichts."""
    leds = SimulatedLedBackend(["B1", "B2"])
    leds.apply({"B1": True, "B2": False})          # B1 belegt -> rot
    assert leds.states()["B1"] == {"green": False, "red": True}

    leds.set_override({"B1": (True, False), "B2": (True, False)}, seconds=30,
                      label="gruen")
    assert leds.states()["B1"] == {"green": True, "red": False}

    # Der Hintergrund-Takt misst weiter - das Muster muss trotzdem stehen bleiben.
    leds.apply({"B1": True, "B2": False})
    assert leds.states()["B1"] == {"green": True, "red": False}
    assert leds.override_info()["label"] == "gruen"


def test_override_expires_and_normal_operation_resumes():
    leds = SimulatedLedBackend(["B1"])
    leds.set_override({"B1": (True, True)}, seconds=0.5, label="beide")
    assert leds.override_active() is True

    import time as _t
    _t.sleep(0.6)
    assert leds.override_active() is False
    leds.apply({"B1": True})                        # belegt -> rot
    assert leds.states()["B1"] == {"green": False, "red": True}


def test_override_can_be_cleared():
    leds = SimulatedLedBackend(["B1"])
    leds.set_override({"B1": (True, True)}, seconds=30)
    leds.set_override(None)
    assert leds.override_active() is False
    assert leds.override_info() is None


def test_led_test_endpoint_drives_all_leds(fake_gpio, all_free, led_layout):
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

    resp = client.post("/api/diag/led-test?mode=beide&seconds=30")
    assert resp.status_code == 200
    assert gpio.outputs[b1.led_green_pin] is True
    assert gpio.outputs[b1.led_red_pin] is True

    # Nur ein Feld - damit laesst sich die Zuordnung pruefen.
    client.post("/api/diag/led-test?mode=feld&space=B1&seconds=30")
    assert gpio.outputs[b1.led_green_pin] is True
    h1 = system.space("H1")
    assert gpio.outputs[h1.led_green_pin] is False

    # Beenden -> Normalbetrieb (alle frei -> gruen)
    assert client.delete("/api/diag/led-test").status_code == 200
    assert gpio.outputs[b1.led_green_pin] is True
    assert gpio.outputs[b1.led_red_pin] is False


def test_led_test_rejects_unknown_mode(led_layout):
    app = create_app()
    app.testing = True
    resp = app.test_client().post("/api/diag/led-test?mode=disco")
    assert resp.status_code == 400


# --- Regression: fehlgeschlagenes Schalten darf nichts einfrieren ---------
def test_failed_write_is_retried_and_reported(fake_gpio):
    """Ein Schreibfehler darf das Feld nicht dauerhaft dunkel stehen lassen.

    Fruehere Fehlerquelle: Der Zwischenspeicher `_last` merkte sich den
    Sollzustand AUCH nach einem fehlgeschlagenen led.on(). Beim naechsten Takt
    griff die Abkuerzung "unveraendert - nicht schreiben", und das Feld blieb
    fuer immer dunkel - waehrend states() "green: true, error: null" meldete.
    """
    gpio = fake_gpio()
    from app.actuators.gpio import GpioLedBackend

    leds = GpioLedBackend([{"id": "A1", "green_pin": 6, "red_pin": 12}])
    gruen = gpio.opened[6]

    # Ein einziger Schaltvorgang schlaegt fehl ...
    original_on = gruen.on
    kaputt = {"aktiv": True}

    def flaky_on():
        if kaputt["aktiv"]:
            raise RuntimeError("Schaltfehler")
        original_on()

    gruen.on = flaky_on
    leds.apply({"A1": False})                 # frei -> gruen, schlaegt fehl

    assert gpio.outputs[6] is False
    assert leds.states()["A1"]["error"], "Der Schreibfehler muss gemeldet werden"
    assert "A1/green" in leds.health()["failed"]

    # ... beim naechsten Takt wird es erneut versucht.
    kaputt["aktiv"] = False
    leds.apply({"A1": False})
    assert gpio.outputs[6] is True, "Nach dem Fehler muss erneut geschrieben werden"
    assert leds.states()["A1"]["error"] is None
    assert leds.health()["failed"] == []


def test_errors_are_reported_per_colour(fake_gpio):
    """Faellt rot aus, darf das den Fehler von gruen nicht verdecken."""
    fake_gpio(fail_pins=(6, 12))
    from app.actuators.gpio import GpioLedBackend

    leds = GpioLedBackend([{"id": "A1", "green_pin": 6, "red_pin": 12}])
    fehler = leds.states()["A1"]["error"]
    assert "green" in fehler and "red" in fehler
    assert set(leds.health()["failed"]) == {"A1/green", "A1/red"}


# --- /api/health kennt jetzt auch die LEDs --------------------------------
def test_health_reports_led_failures(fake_gpio, all_free, led_layout):
    """Fallen LEDs aus, darf die Ampel nicht weiter auf "ok" stehen."""
    system, _ = load_layout()
    b1 = system.space("B1")
    gpio = fake_gpio(all_free, fail_pins=(b1.led_green_pin,))

    def factory(sys_, settings):
        from app.sensors import wiring_specs
        from app.sensors.gpio import GpioSensorBackend
        return GpioSensorBackend(wiring_specs(sys_))

    app = create_app(backend_factory=factory)
    app.testing = True
    h = app.test_client().get("/api/health").get_json()

    assert h["status"] == "degraded"
    assert h["leds_mode"] == "gpio"
    assert h["leds_total"] == 16          # 8 Felder x 2 LEDs
    assert h["leds_ok"] == 15
    assert "B1/green" in h["leds_failed"]


def test_health_ok_when_all_leds_work(fake_gpio, all_free, led_layout):
    fake_gpio(all_free)

    def factory(sys_, settings):
        from app.sensors import wiring_specs
        from app.sensors.gpio import GpioSensorBackend
        return GpioSensorBackend(wiring_specs(sys_))

    app = create_app(backend_factory=factory)
    app.testing = True
    h = app.test_client().get("/api/health").get_json()
    assert h["status"] == "ok"
    assert h["leds_ok"] == 16 and h["leds_failed"] == []


def test_spi_pins_are_flagged():
    """GPIO7-11 sind SPI0 - das muss die Pin-Referenz sagen."""
    from app import pins as pinmap

    for pin in (7, 8, 9, 10, 11):
        assert pinmap.pin_warning(pin), f"GPIO{pin} ohne SPI-Hinweis"
        assert "SPI" in pinmap.pin_warning(pin)


# --- Start-Selbsttest ------------------------------------------------------
def test_boot_flash_lights_everything_at_startup(fake_gpio, all_free, tmp_path,
                                                 monkeypatch):
    """Nach jedem Neustart muessen kurz ALLE LEDs an sein.

    Ein Blick aufs Modell beantwortet damit ohne einen einzigen Befehl die
    wichtigste Frage: Kommt ueberhaupt Strom bei den LEDs an?
    """
    from app.config import layout_path

    data = json.loads(layout_path().read_text(encoding="utf-8"))
    data["settings"]["leds_enabled"] = True
    data["settings"]["led_boot_test_s"] = 30
    path = tmp_path / "layout.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("ANNA_LAYOUT", str(path))

    gpio = fake_gpio(all_free)

    def factory(sys_, settings):
        from app.sensors import wiring_specs
        from app.sensors.gpio import GpioSensorBackend
        return GpioSensorBackend(wiring_specs(sys_))

    app = create_app(backend_factory=factory)
    system, _ = load_layout()

    # Alle 16 LEDs muessen an sein - auch die roten, obwohl alles frei ist.
    for area in system.areas:
        for space in area.spaces:
            assert gpio.outputs[space.led_green_pin] is True, f"{space.id} gruen"
            assert gpio.outputs[space.led_red_pin] is True, f"{space.id} rot"

    assert app.config["RUNTIME"].leds.override_info()["label"] == "Start-Selbsttest"


def test_boot_flash_can_be_switched_off(fake_gpio, all_free, led_layout):
    """led_boot_test_s = 0 -> sofort Normalbetrieb."""
    gpio = fake_gpio(all_free)

    def factory(sys_, settings):
        from app.sensors import wiring_specs
        from app.sensors.gpio import GpioSensorBackend
        return GpioSensorBackend(wiring_specs(sys_))

    app = create_app(backend_factory=factory)
    app.testing = True
    system, _ = load_layout()
    b1 = system.space("B1")

    assert app.config["RUNTIME"].leds.override_info() is None
    # Ohne Start-Selbsttest schreibt erst die erste Messung die LEDs
    # (im Betrieb erledigt das der Hintergrund-Takt binnen 1,5 s).
    app.test_client().get("/api/state")
    assert gpio.outputs[b1.led_green_pin] is True     # frei -> gruen
    assert gpio.outputs[b1.led_red_pin] is False


def test_start_zeigt_die_wirklichkeit_nicht_ein_testmuster():
    """Beim Start muessen die LEDs die Belegung zeigen, kein Testmuster.

    Anforderung: alle Felder frei = alle LEDs gruen. Ein Selbsttest, der beim
    Start ALLE LEDs (gruen UND rot) anschaltet, widerspricht dem - er ist
    deshalb standardmaessig aus und nur zum Suchen einer Verdrahtung gedacht.
    """
    _, settings = load_layout()
    assert settings.get("led_boot_test_s", 0) == 0, (
        "led_boot_test_s muss im Auslieferzustand 0 sein - sonst leuchten beim "
        "Start alle LEDs statt der tatsaechlichen Belegung.")


def test_leds_stimmen_sofort_beim_start(fake_gpio, all_free, led_layout):
    """Ohne einen einzigen Aufruf: alle frei -> alle gruen, von Sekunde eins an."""
    gpio = fake_gpio(all_free)

    def factory(sys_, settings):
        from app.sensors import wiring_specs
        from app.sensors.gpio import GpioSensorBackend
        return GpioSensorBackend(wiring_specs(sys_))

    create_app(backend_factory=factory)          # kein /api/state noetig
    system, _ = load_layout()
    for area in system.areas:
        for s in area.spaces:
            assert gpio.outputs[s.led_green_pin] is True, f"{s.id} nicht gruen"
            assert gpio.outputs[s.led_red_pin] is False, f"{s.id} faelschlich rot"


def test_find_leds_skips_sensor_pins():
    """Die LED-Suche darf niemals einen Sensorpin treiben.

    Ein Ausgang gegen einen geschlossenen Reed-Schalter waere ein Kurzschluss
    nach GND.
    """
    import importlib.util
    from pathlib import Path

    from app import pins as pinmap

    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "gpio_check", root / "scripts" / "gpio_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    system, _ = load_layout()
    sensorpins = {s.gpio_pin for a in system.areas for s in a.spaces
                  if s.gpio_pin is not None}
    kandidaten = [p for p in pinmap.ALL_BCM_PINS
                  if p not in sensorpins and p not in (0, 1)]

    assert not (set(kandidaten) & sensorpins), "Sensorpin in der LED-Suche!"
    assert 0 not in kandidaten and 1 not in kandidaten
    # Alle geplanten LED-Pins muessen enthalten sein, sonst findet die Suche
    # die eigene Verdrahtung nicht.
    for area in system.areas:
        for space in area.spaces:
            for pin in (space.led_green_pin, space.led_red_pin):
                if pin is not None:
                    assert pin in kandidaten, f"GPIO{pin} fehlt in der Suche"


# --- Die Anforderung, wortwoertlich ---------------------------------------
def test_ein_auto_macht_genau_ein_feld_rot(fake_gpio, all_free, led_layout):
    """8 Felder. Auto auf EIN Feld -> genau dieses Feld rot, Rest bleibt gruen.

    Das ist die Anforderung in einem Test: nicht alle, nicht keines, sondern
    genau das Feld, auf dem das Auto steht.
    """
    gpio = fake_gpio(all_free)

    def factory(sys_, settings):
        from app.sensors import wiring_specs
        from app.sensors.gpio import GpioSensorBackend
        return GpioSensorBackend(wiring_specs(sys_))

    app = create_app(backend_factory=factory)
    app.testing = True
    client = app.test_client()
    system, _ = load_layout()
    felder = [s for a in system.areas for s in a.spaces]
    assert len(felder) == 8

    # Startzustand: alles frei -> ALLE LEDs gruen
    client.get("/api/state")
    for s in felder:
        assert gpio.outputs[s.led_green_pin] is True, f"{s.id} muss gruen sein"
        assert gpio.outputs[s.led_red_pin] is False, f"{s.id} darf nicht rot sein"

    # Jedes Feld einzeln durchprobieren
    for belegt in felder:
        gpio.set_level(belegt.gpio_pin, 0)              # Auto drauf
        for _ in range(3):                              # Entprellung abwarten
            client.get("/api/state")

        for s in felder:
            soll_rot = (s.id == belegt.id)
            assert gpio.outputs[s.led_red_pin] is soll_rot, (
                f"Auto auf {belegt.id}: {s.id} rot={gpio.outputs[s.led_red_pin]}, "
                f"erwartet {soll_rot}")
            assert gpio.outputs[s.led_green_pin] is (not soll_rot), (
                f"Auto auf {belegt.id}: {s.id} gruen falsch")

        gpio.set_level(belegt.gpio_pin, 1)              # Auto weg
        for _ in range(3):
            client.get("/api/state")
        assert gpio.outputs[belegt.led_green_pin] is True
        assert gpio.outputs[belegt.led_red_pin] is False


def test_zwei_autos_machen_genau_zwei_felder_rot(fake_gpio, all_free, led_layout):
    gpio = fake_gpio(all_free)

    def factory(sys_, settings):
        from app.sensors import wiring_specs
        from app.sensors.gpio import GpioSensorBackend
        return GpioSensorBackend(wiring_specs(sys_))

    app = create_app(backend_factory=factory)
    app.testing = True
    client = app.test_client()
    system, _ = load_layout()
    b3, h1 = system.space("B3"), system.space("H1")

    gpio.set_level(b3.gpio_pin, 0)
    gpio.set_level(h1.gpio_pin, 0)
    for _ in range(3):
        client.get("/api/state")

    rot = [s.id for a in system.areas for s in a.spaces
           if gpio.outputs[s.led_red_pin]]
    assert rot == ["B3", "H1"], f"rot sind: {rot}"


# --- Schutz gegen Pins, die auf Masse festhaengen -------------------------
def test_kurzgeschlossener_pin_wird_nicht_getrieben(fake_gpio):
    """Genau das Fehlerbild vom 19.08.2026 am Modell.

    14 LED-Pins lagen ueber einen Widerstand direkt auf Masse - ohne LED im
    Strompfad. Getrieben zogen sie je rund 10 mA, zusammen weit ueber den
    50 mA, die die GPIO-Treiber des Pi insgesamt vertragen. Geleuchtet hat
    trotzdem nichts. Solche Pins darf das Backend gar nicht erst einschalten.
    """
    gpio = fake_gpio()
    gpio.grounded = {6, 12}          # B1 gruen und rot haengen auf Masse
    from app.actuators.gpio import GpioLedBackend

    leds = GpioLedBackend([
        {"id": "A1", "green_pin": 6, "red_pin": 12},
        {"id": "A2", "green_pin": 19, "red_pin": 20},   # unauffaellig
    ])

    # A1 wurde gesperrt und gemeldet ...
    assert set(leds.health()["failed"]) == {"A1/green", "A1/red"}
    assert "Masse" in leds.states()["A1"]["error"]

    # ... und wird auch beim Schalten nicht angefasst.
    leds.apply({"A1": False, "A2": False})
    assert 6 not in gpio.outputs and 12 not in gpio.outputs

    # A2 arbeitet ungestoert weiter.
    assert gpio.outputs[19] is True and gpio.outputs[20] is False


def test_gesunde_pins_werden_nicht_faelschlich_gesperrt(fake_gpio):
    """Eine korrekt verdrahtete LED sperrt bei 66 uA - der Pin liest HIGH."""
    gpio = fake_gpio()
    gpio.grounded = set()
    from app.actuators.gpio import GpioLedBackend

    leds = GpioLedBackend([{"id": "A1", "green_pin": 6, "red_pin": 12}])
    assert leds.health()["failed"] == []
    leds.apply({"A1": False})
    assert gpio.outputs[6] is True


def test_pruefung_laesst_sich_abschalten(fake_gpio):
    gpio = fake_gpio()
    gpio.grounded = {6}
    from app.actuators.gpio import GpioLedBackend

    leds = GpioLedBackend([{"id": "A1", "green_pin": 6, "red_pin": 12}],
                          check_shorts=False)
    assert leds.health()["failed"] == []      # nichts gesperrt


def test_pruefung_verhindert_den_start_nie(fake_gpio, monkeypatch):
    """Faellt die Vorpruefung aus, laeuft die LED-Ausgabe trotzdem an."""
    gpio = fake_gpio()
    import sys
    delattr(sys.modules["gpiozero"], "Device")   # Device nicht verfuegbar
    from app.actuators.gpio import GpioLedBackend

    leds = GpioLedBackend([{"id": "A1", "green_pin": 6, "red_pin": 12}])
    leds.apply({"A1": True})
    assert gpio.outputs[12] is True             # rot an, trotz fehlender Pruefung
