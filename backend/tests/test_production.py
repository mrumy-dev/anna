"""Tests fuer die produktionsrelevanten Bausteine:

- WSGI-Einstiegspunkt (wsgi.application) bedient die API.
- Layout-Validierung (fehlende Datei, doppelte Feld-IDs).
- GPIO-Backend bleibt robust, wenn ein einzelner Pin nicht initialisierbar ist
  (nachgestellt ueber ein Fake-gpiozero-Modul, ohne echte Hardware).

Laeuft ohne Raspberry Pi und ohne gpiozero.
"""

from __future__ import annotations

import json
import sys
import types

import pytest


# --- WSGI-Einstiegspunkt ---------------------------------------------------
def test_wsgi_application_serves_api(space_count):
    from wsgi import application

    client = application.test_client()
    assert client.get("/api/health").status_code == 200
    state = client.get("/api/state").get_json()
    assert state["mode"] == "simulated"
    assert state["total"] == space_count


# --- Regression: Import darf keine App (und keine GPIO-Pins) erzeugen ------
def test_importing_main_creates_no_app():
    """Fruehere Fehlerquelle: `app = create_app()` auf Modulebene.

    Dadurch hat schon `from app import create_app` in run.py saemtliche
    GPIO-Pins belegt; die danach regulaer erzeugte App bekam keinen Pin mehr
    und alle Parkfelder blieben stumm auf "frei" stehen.
    """
    import app.main as main_module

    assert not hasattr(main_module, "app"), (
        "app/main.py darf keine App auf Modulebene erzeugen - sonst belegt "
        "bereits der Import die GPIO-Pins."
    )


def test_gpio_startup_like_run_py_gets_all_sensors(fake_gpio, all_free, space_count):
    """Startet wie run.py und prueft, dass WIRKLICH alle Sensoren aktiv sind.

    Genau dieser Test haette den Ausfall auf dem Raspberry Pi aufgedeckt:
    vorher meldete jedes Feld 'GPIO.. is already in use'.
    """
    fake_gpio(all_free)

    from app import create_app  # genau der Import aus run.py
    from app.sensors import wiring_specs
    from app.sensors.gpio import GpioSensorBackend

    application = create_app(
        backend_factory=lambda system, settings: GpioSensorBackend(
            wiring_specs(system)
        )
    )
    application.testing = True

    rows = application.test_client().get("/api/diagnostics").get_json()["spaces"]
    assert len(rows) == space_count
    broken = [r["space_id"] for r in rows if not r["ok"]]
    assert not broken, f"Diese Felder haben keinen Sensor bekommen: {broken}"


# --- Layout-Validierung ----------------------------------------------------
def test_load_layout_missing_file(tmp_path):
    from app.config import load_layout

    with pytest.raises(FileNotFoundError):
        load_layout(tmp_path / "gibtsnicht.json")


def test_load_layout_duplicate_ids(tmp_path):
    from app.config import load_layout

    layout = {
        "settings": {"poll_interval_ms": 1500},
        "areas": [
            {"id": "a", "name": "A", "spaces": [
                {"id": "X1", "type": "normal"},
                {"id": "X1", "type": "family"},
            ]},
        ],
    }
    path = tmp_path / "layout.json"
    path.write_text(json.dumps(layout), encoding="utf-8")

    with pytest.raises(ValueError):
        load_layout(path)


def test_load_layout_empty_areas(tmp_path):
    from app.config import load_layout

    path = tmp_path / "layout.json"
    path.write_text(json.dumps({"areas": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_layout(path)


# --- GPIO-Backend bleibt bei einem defekten Pin robust ---------------------
def test_gpio_backend_survives_bad_pin(fake_gpio):
    fake_gpio(fail_pins=(27,))  # ein Pin laesst sich nicht oeffnen

    from app.sensors.gpio import GpioSensorBackend

    backend = GpioSensorBackend([
        {"id": "A", "pin": 17},
        {"id": "B", "pin": 27},
        {"id": "C", "pin": 5},
    ])
    readings = backend.read_all()

    # A und C funktionieren, B (Pin 27) wurde uebersprungen statt zu crashen.
    assert set(readings.keys()) == {"A", "C"}

    # Die Diagnose zeigt das defekte Feld weiterhin an - mit Fehlertext.
    rows = {r["space_id"]: r for r in backend.diagnostics()}
    assert rows["B"]["ok"] is False
    assert rows["B"]["error"]
    assert rows["A"]["ok"] is True
