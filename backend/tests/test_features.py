"""Tests fuer die additiven Backend-Funktionen:

- Reservierung (Domaene + API: /api/reserve, /api/reservations)
- Statistik (Domaene StatsCollector + API: /api/stats)
- Live-Stream (/api/stream als Server-Sent-Events)
- GpioSensorBackend.read_all inkl. invert (ueber ein Fake-gpiozero-Modul,
  d. h. ohne echte Hardware und ohne installiertes gpiozero)

Der Kernvertrag /api/state bleibt unveraendert; das wird hier mitgeprueft.
"""

from __future__ import annotations

import sys
import types

import pytest

from app.main import create_app
from app.models import Area, ParkingSystem, Space, SpaceType, StatsCollector


@pytest.fixture
def client():
    app = create_app()
    app.testing = True
    return app.test_client()


def _space(state: dict, space_id: str) -> dict:
    for area in state["areas"]:
        for s in area["spaces"]:
            if s["id"] == space_id:
                return s
    raise AssertionError(f"Parkfeld {space_id} nicht gefunden")


# --- Reservierung: Domaene ------------------------------------------------
def _system() -> ParkingSystem:
    return ParkingSystem([
        Area("a", "Areal A", "", [
            Space("A1", SpaceType.NORMAL),
            Space("A2", SpaceType.FAMILY, occupied=True),
        ]),
    ])


def test_reserve_free_space():
    system = _system()
    assert system.reserve("A1") == {"ok": True}
    assert [r["id"] for r in system.reservations()] == ["A1"]


def test_reserve_occupied_space_fails():
    system = _system()
    result = system.reserve("A2")
    assert result["ok"] is False
    assert system.reservations() == []


def test_reserve_unknown_space_fails():
    assert _system().reserve("ZZ")["ok"] is False


def test_cancel_reservation():
    system = _system()
    system.reserve("A1")
    system.cancel_reservation("A1")
    assert system.reservations() == []


def test_occupying_clears_reservation():
    system = _system()
    system.reserve("A1")
    system.apply_readings({"A1": True})
    assert system.reservations() == []


# --- Reservierung: API ----------------------------------------------------
def test_reserve_endpoint_and_listing(client):
    # B3 ist im Standard-Layout zu Beginn frei.
    resp = client.post("/api/reserve/B3")
    assert resp.status_code == 200
    assert [r["id"] for r in resp.get_json()["reservations"]] == ["B3"]

    listing = client.get("/api/reservations").get_json()["reservations"]
    assert listing[0]["id"] == "B3"
    assert listing[0]["area_id"] == "blumenstrasse"

    cancel = client.delete("/api/reserve/B3")
    assert cancel.status_code == 200
    assert cancel.get_json()["reservations"] == []


def test_reserve_occupied_returns_409(client):
    # B1 ist im Standard-Layout (prefill=2) zu Beginn belegt.
    resp = client.post("/api/reserve/B1")
    assert resp.status_code == 409


def test_reserve_unknown_returns_404(client):
    assert client.post("/api/reserve/ZZ").status_code == 404


def test_state_contract_has_no_reserved_field(client):
    """Reservierung darf den /api/state-Vertrag nicht veraendern."""
    client.post("/api/reserve/B3")
    space = _space(client.get("/api/state").get_json(), "B3")
    assert "reserved" not in space


# --- Statistik: Domaene ---------------------------------------------------
def test_stats_collector_aggregates():
    stats = StatsCollector()
    stats.record({"total": 7, "free": 7, "areas": [
        {"id": "x", "name": "X", "total": 7, "free": 7}]})
    stats.record({"total": 7, "free": 3, "areas": [
        {"id": "x", "name": "X", "total": 7, "free": 3}]})
    data = stats.to_dict()
    assert data["samples"] == 2
    assert data["peak_occupied"] == 4       # max(0, 4)
    assert data["avg_occupied"] == 2.0      # (0 + 4) / 2
    assert data["areas"][0]["peak_occupied"] == 4


# --- Statistik: API -------------------------------------------------------
def test_stats_endpoint(client):
    data = client.get("/api/stats").get_json()
    assert data["samples"] >= 1
    assert "peak_occupied" in data and "avg_occupied" in data
    assert isinstance(data["areas"], list) and len(data["areas"]) == 2


# --- Live-Stream (SSE) ----------------------------------------------------
def test_stream_emits_sse_event(client):
    resp = client.get("/api/stream?limit=1")
    assert resp.status_code == 200
    assert resp.mimetype == "text/event-stream"
    body = resp.get_data(as_text=True)
    assert body.startswith("data: ")
    assert '"mode": "simulated"' in body or '"mode":"simulated"' in body


# --- GpioSensorBackend ueber Fake-gpiozero --------------------------------
def test_gpio_backend_reads_and_inverts(fake_gpio):
    """Prueft Lazy-Import und invert-Logik ohne echte Hardware."""
    # Pin 17 auf LOW = Reed geschlossen = belegt; Pin 27 bleibt HIGH (offen).
    fake_gpio({17: 0, 27: 1})

    from app.sensors.gpio import GpioSensorBackend

    backend = GpioSensorBackend([
        {"id": "B1", "pin": 17, "invert": False, "pull_up": True},
        {"id": "B2", "pin": 27, "invert": True, "pull_up": True},
        {"id": "B3", "pin": None, "invert": False, "pull_up": True},
    ])
    readings = backend.read_all()

    assert backend.name == "gpio"
    assert readings["B1"] is True   # LOW, nicht invertiert -> belegt
    assert readings["B2"] is True   # HIGH (frei), invertiert -> belegt
    assert "B3" not in readings     # Pin None wird uebersprungen
