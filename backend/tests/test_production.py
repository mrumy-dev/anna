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
def test_wsgi_application_serves_api():
    from wsgi import application

    client = application.test_client()
    assert client.get("/api/health").status_code == 200
    state = client.get("/api/state").get_json()
    assert state["mode"] == "simulated"
    assert state["total"] == 7


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
def test_gpio_backend_survives_bad_pin(monkeypatch):
    fake = types.ModuleType("gpiozero")

    class FakeButton:
        def __init__(self, pin, pull_up=True, bounce_time=None):
            if pin == 27:
                raise RuntimeError("Pin 27 belegt")  # ein Pin faellt aus
            self.pin = pin

        @property
        def is_pressed(self) -> bool:
            return False

        def close(self) -> None:
            pass

    fake.Button = FakeButton
    monkeypatch.setitem(sys.modules, "gpiozero", fake)

    from app.sensors.gpio import GpioSensorBackend

    backend = GpioSensorBackend(
        pin_map={"A": 17, "B": 27, "C": 5},
        invert_map={},
    )
    readings = backend.read_all()

    # A und C funktionieren, B (Pin 27) wurde uebersprungen statt zu crashen.
    assert set(readings.keys()) == {"A", "C"}
