"""Tests fuer die Inbetriebnahme-Hilfen (Pin-Zuordnung und Diagnose).

Deckt genau die Fehlerbilder ab, die beim Anschluss der echten Sensoren
aufgetreten sind:
- BCM- gegen Board-Nummerierung (die Zahl 17 meint zwei verschiedene Kontakte)
- Sensor meldet verkehrt herum (invert)
- Sensor legt aktiv HIGH an statt gegen GND zu ziehen (pull_up=false)
- Pegel bewegt sich gar nicht (Verdrahtung) - erkennbar am Wechselzaehler

Alles ohne Raspberry Pi, ueber den gpiozero-Nachbau aus conftest.py.
"""

from __future__ import annotations

import json

import pytest

from app import pins as pinmap
from app.config import load_layout
from app.main import create_app


# --- Pin-Nummerierung ------------------------------------------------------
def test_resolve_bcm_is_identity():
    assert pinmap.resolve_pin(17, "bcm") == 17


def test_resolve_board_translates():
    # Physischer Header-Pin 11 ist GPIO17.
    assert pinmap.resolve_pin(11, "board") == 17
    assert pinmap.resolve_pin(13, "board") == 27
    assert pinmap.resolve_pin(29, "board") == 5


def test_resolve_board_rejects_power_pins():
    """Genau die Falle: physischer Pin 17 ist 3V3, physischer Pin 25 ist GND."""
    with pytest.raises(pinmap.PinError) as exc:
        pinmap.resolve_pin(17, "board")
    assert "3V3" in str(exc.value)

    with pytest.raises(pinmap.PinError):
        pinmap.resolve_pin(25, "board")


def test_resolve_rejects_unknown_bcm():
    with pytest.raises(pinmap.PinError):
        pinmap.resolve_pin(99, "bcm")


def test_board_confusion_hint_warns_for_power_pin():
    hint = pinmap.board_confusion_hint(17)
    assert hint and "3V3" in hint


def test_describe_pin_mentions_header_position():
    assert "Header-Pin 11" in pinmap.describe_pin(17)


# --- Layout-Konfiguration --------------------------------------------------
def _write_layout(tmp_path, numbering="bcm", pin=17, pull_up=True):
    layout = {
        "settings": {"poll_interval_ms": 1500, "numbering": numbering},
        "areas": [{
            "id": "a", "name": "Areal A", "spaces": [
                {"id": "A1", "type": "normal", "gpio_pin": pin, "pull_up": pull_up},
            ],
        }],
    }
    path = tmp_path / "layout.json"
    path.write_text(json.dumps(layout), encoding="utf-8")
    return path


def test_layout_board_numbering_is_resolved(tmp_path):
    system, settings = load_layout(_write_layout(tmp_path, "board", 11))
    space = system.space("A1")
    assert settings["numbering"] == "board"
    assert space.configured_pin == 11   # so steht es in der Datei
    assert space.gpio_pin == 17         # so liest es die Hardware


def test_layout_rejects_power_pin_in_board_mode(tmp_path):
    with pytest.raises(ValueError) as exc:
        load_layout(_write_layout(tmp_path, "board", 17))
    assert "A1" in str(exc.value)


def test_layout_rejects_unknown_numbering(tmp_path):
    path = tmp_path / "l.json"
    path.write_text(json.dumps({
        "settings": {"numbering": "quatsch"},
        "areas": [{"id": "a", "name": "A", "spaces": []}],
    }), encoding="utf-8")
    with pytest.raises(ValueError):
        load_layout(path)


def test_layout_pull_up_variants(tmp_path):
    system, _ = load_layout(_write_layout(tmp_path, "bcm", 17, pull_up=False))
    assert system.space("A1").pull_up is False


# --- Sensor-Auswertung je Beschaltung -------------------------------------
def _backend(specs):
    from app.sensors.gpio import GpioSensorBackend
    return GpioSensorBackend(specs)


def test_pull_up_low_means_occupied(fake_gpio):
    """Reed gegen GND: LOW = Kontakt geschlossen = belegt."""
    fake_gpio({17: 0})
    backend = _backend([{"id": "A1", "pin": 17, "pull_up": True}])
    assert backend.read_all()["A1"] is True


def test_pull_down_high_means_occupied(fake_gpio):
    """PNP-Sensor: legt bei Belegung aktiv HIGH an -> pull_up=false noetig."""
    gpio = fake_gpio({17: 0})
    backend = _backend([{"id": "A1", "pin": 17, "pull_up": False}])
    assert backend.read_all()["A1"] is False   # LOW = nichts erkannt
    gpio.set_level(17, 1)
    assert backend.read_all()["A1"] is True    # HIGH = belegt


def test_active_state_without_internal_resistor(fake_gpio):
    gpio = fake_gpio({17: 1})
    backend = _backend([{"id": "A1", "pin": 17, "pull_up": None,
                         "active_state": False}])
    assert backend.read_all()["A1"] is False
    gpio.set_level(17, 0)
    assert backend.read_all()["A1"] is True


def test_invert_flips_result(fake_gpio):
    fake_gpio({17: 1})  # offen = eigentlich frei
    backend = _backend([{"id": "A1", "pin": 17, "pull_up": True, "invert": True}])
    assert backend.read_all()["A1"] is True


# --- Rohpegel und Wechselzaehler ------------------------------------------
def test_diagnostics_reports_raw_level(fake_gpio):
    gpio = fake_gpio({17: 1})
    backend = _backend([{"id": "A1", "pin": 17, "configured_pin": 17,
                         "pull_up": True}])

    row = backend.diagnostics()[0]
    assert row["raw"] == 1
    assert row["occupied"] is False
    assert row["pin"] == 17
    assert row["board_pin"] == 11
    assert row["ok"] is True

    gpio.set_level(17, 0)
    row = backend.diagnostics()[0]
    assert row["raw"] == 0
    assert row["occupied"] is True


def test_change_counter_detects_dead_wiring(fake_gpio):
    """Der entscheidende Test: bewegt sich der Pegel ueberhaupt?"""
    gpio = fake_gpio({17: 1, 27: 1})
    backend = _backend([
        {"id": "A1", "pin": 17, "pull_up": True},
        {"id": "A2", "pin": 27, "pull_up": True},   # bleibt unveraendert
    ])

    backend.read_all()
    gpio.set_level(17, 0)
    backend.read_all()
    gpio.set_level(17, 1)
    backend.read_all()

    rows = {r["space_id"]: r for r in backend.diagnostics()}
    assert rows["A1"]["changes"] >= 2      # Auto drauf und wieder weg
    assert rows["A2"]["changes"] == 0      # totes Feld bleibt bei 0
    assert rows["A1"]["last_change_s"] is not None
    assert rows["A2"]["last_change_s"] is None


def test_diagnostics_hint_for_board_confusion(fake_gpio):
    fake_gpio({17: 1})
    backend = _backend([{"id": "A1", "pin": 17, "configured_pin": 17,
                         "pull_up": True}])
    assert "3V3" in backend.diagnostics()[0]["hint"]


# --- Pin-Suche -------------------------------------------------------------
def test_scan_finds_the_moving_pin(fake_gpio):
    gpio = fake_gpio({17: 1, 6: 1})
    backend = _backend([{"id": "A1", "pin": 17, "pull_up": True}])

    # Waehrend des Scans wackelt der noch nicht zugeordnete Pin GPIO6.
    original = backend._raw_level
    state = {"n": 0}

    def wobble(space_id):
        state["n"] += 1
        gpio.set_level(6, state["n"] % 2)
        return original(space_id)

    backend._raw_level = wobble
    rows = backend.scan(duration_s=0.4, interval_s=0.02)

    by_pin = {r["pin"]: r for r in rows}
    assert by_pin[6]["changes"] > 0        # der bewegte Pin faellt auf
    assert by_pin[6]["assigned_to"] is None
    assert rows[0]["pin"] == 6             # nach Wechseln sortiert


# --- API -------------------------------------------------------------------
@pytest.fixture
def gpio_app(fake_gpio):
    """App im gpio-Modus mit simulierter Hardware."""
    gpio = fake_gpio({17: 1, 27: 1, 22: 1, 23: 1, 24: 1, 25: 1, 5: 1})

    def factory(system, settings):
        from app.sensors import wiring_specs
        from app.sensors.gpio import GpioSensorBackend
        return GpioSensorBackend(wiring_specs(system))

    app = create_app(backend_factory=factory)
    app.testing = True
    return app.test_client(), gpio


def test_api_diagnostics_in_simulation():
    app = create_app()
    app.testing = True
    data = app.test_client().get("/api/diagnostics").get_json()
    assert data["mode"] == "simulated"
    assert data["numbering"] == "bcm"
    assert len(data["spaces"]) == 7
    assert data["spaces"][0]["space_id"] == "B1"


def test_api_diagnostics_in_gpio_mode(gpio_app):
    client, gpio = gpio_app
    data = client.get("/api/diagnostics").get_json()
    assert data["mode"] == "gpio"
    rows = {r["space_id"]: r for r in data["spaces"]}
    assert rows["B1"]["pin"] == 17
    assert rows["B1"]["raw"] == 1
    assert rows["B1"]["occupied"] is False

    gpio.set_level(17, 0)          # Auto auf B1 stellen
    rows = {r["space_id"]: r for r in client.get("/api/diagnostics").get_json()["spaces"]}
    assert rows["B1"]["occupied"] is True
    assert rows["B1"]["changes"] >= 1


def test_api_pin_reference():
    app = create_app()
    app.testing = True
    data = app.test_client().get("/api/diag/pins").get_json()
    pins = {p["bcm"]: p for p in data["pins"]}
    assert pins[17]["board"] == 11
    assert pins[2]["safe"] is False       # I2C ist als Sensoreingang heikel
    assert pins[17]["safe"] is True


def test_scan_endpoint_rejected_in_simulation():
    app = create_app()
    app.testing = True
    resp = app.test_client().post("/api/diag/scan")
    assert resp.status_code == 400
    assert "gpio" in resp.get_json()["error"]


def test_assign_forbidden_without_env(gpio_app, monkeypatch):
    monkeypatch.delenv("ANNA_DIAG", raising=False)
    client, _ = gpio_app
    resp = client.post("/api/diag/assign/B1", json={"invert": True})
    assert resp.status_code == 403


def test_assign_writes_layout_and_reloads(tmp_path, monkeypatch, fake_gpio):
    layout = {
        "settings": {"poll_interval_ms": 1500, "numbering": "bcm"},
        "areas": [{"id": "a", "name": "Areal A", "spaces": [
            {"id": "A1", "type": "normal", "gpio_pin": 17, "invert": False},
        ]}],
    }
    path = tmp_path / "layout.json"
    path.write_text(json.dumps(layout), encoding="utf-8")
    monkeypatch.setenv("ANNA_LAYOUT", str(path))
    monkeypatch.setenv("ANNA_DIAG", "1")
    fake_gpio({17: 1, 6: 1})

    def factory(system, settings):
        from app.sensors import wiring_specs
        from app.sensors.gpio import GpioSensorBackend
        return GpioSensorBackend(wiring_specs(system))

    app = create_app(backend_factory=factory)
    app.testing = True
    client = app.test_client()

    resp = client.post("/api/diag/assign/A1", json={"gpio_pin": 6, "invert": True})
    assert resp.status_code == 200

    # Datei wurde geschrieben ...
    saved = json.loads(path.read_text(encoding="utf-8"))
    space = saved["areas"][0]["spaces"][0]
    assert space["gpio_pin"] == 6
    assert space["invert"] is True

    # ... und das laufende Backend nutzt sofort den neuen Pin.
    rows = {r["space_id"]: r for r in client.get("/api/diagnostics").get_json()["spaces"]}
    assert rows["A1"]["pin"] == 6
    assert rows["A1"]["invert"] is True


def test_assign_rejects_impossible_pin(tmp_path, monkeypatch, fake_gpio):
    path = tmp_path / "layout.json"
    path.write_text(json.dumps({
        "settings": {"numbering": "bcm"},
        "areas": [{"id": "a", "name": "A", "spaces": [
            {"id": "A1", "type": "normal", "gpio_pin": 17},
        ]}],
    }), encoding="utf-8")
    monkeypatch.setenv("ANNA_LAYOUT", str(path))
    monkeypatch.setenv("ANNA_DIAG", "1")
    fake_gpio({17: 1})

    def factory(system, settings):
        from app.sensors import wiring_specs
        from app.sensors.gpio import GpioSensorBackend
        return GpioSensorBackend(wiring_specs(system))

    app = create_app(backend_factory=factory)
    app.testing = True
    resp = app.test_client().post("/api/diag/assign/A1", json={"gpio_pin": 99})
    assert resp.status_code == 400


def test_diag_page_renders():
    app = create_app()
    app.testing = True
    html = app.test_client().get("/diag").get_data(as_text=True)
    assert "Sensor-Diagnose" in html
    assert "diag.js" in html


def test_state_contract_unchanged_by_diagnostics():
    """Der Vertrag aus docs/API.md darf sich nicht veraendert haben."""
    app = create_app()
    app.testing = True
    state = app.test_client().get("/api/state").get_json()
    assert set(state.keys()) == {"areas", "total", "free", "mode"}
    space = state["areas"][0]["spaces"][0]
    assert set(space.keys()) == {"id", "type", "type_label", "occupied"}
