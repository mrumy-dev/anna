"""Tests fuer die HTTP-API mit dem Flask-Testclient.

Geprueft wird der API-Vertrag aus docs/API.md:
    GET  /api/health
    GET  /api/state
    POST /api/sim/toggle/<id>
    POST /api/sim/randomize

Diese Tests laufen ohne Raspberry Pi und ohne gpiozero. Der gpio-Modus wird
ueber ein Fake-Backend nachgestellt, damit die 403-Absicherung der
sim-Endpunkte auch auf dem Laptop pruefbar ist (kein Hardware-Import noetig).
"""

from __future__ import annotations

import pytest

from app.main import create_app
from app.sensors.base import SensorBackend


@pytest.fixture
def client():
    """Frischer Simulator-App-Client pro Test (isolierter Zustand)."""
    app = create_app()
    app.testing = True
    return app.test_client()


def _find_space(state: dict, space_id: str) -> dict:
    for area in state["areas"]:
        for space in area["spaces"]:
            if space["id"] == space_id:
                return space
    raise AssertionError(f"Parkfeld {space_id} nicht gefunden")


# --- GET /api/health ------------------------------------------------------
def test_health_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    # Der Vertrag aus docs/API.md muss enthalten sein. Zusatzfelder zum
    # Sensorzustand (sensors_ok/-total/-failed) sind additiv erlaubt.
    assert data["status"] == "ok"
    assert data["mode"] == "simulated"


# --- GET /api/state -------------------------------------------------------
def test_state_top_level_contract(client):
    resp = client.get("/api/state")
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["mode"] == "simulated"
    assert data["total"] == 7
    assert 0 <= data["free"] <= data["total"]
    assert isinstance(data["areas"], list)
    assert len(data["areas"]) == 2


def test_state_area_and_space_fields(client):
    data = client.get("/api/state").get_json()

    area = data["areas"][0]
    for key in ("id", "name", "maps_url", "free", "total",
                "is_full", "counts_by_type", "spaces"):
        assert key in area, f"Feld '{key}' fehlt im Areal"

    space = area["spaces"][0]
    for key in ("id", "type", "type_label", "occupied"):
        assert key in space, f"Feld '{key}' fehlt im Parkfeld"
    assert space["type"] in {"normal", "family", "women", "disabled"}
    assert isinstance(space["occupied"], bool)


def test_state_free_is_consistent_with_spaces(client):
    """Gesamt-free entspricht der Zahl nicht belegter Felder."""
    data = client.get("/api/state").get_json()
    free_counted = sum(
        1 for a in data["areas"] for s in a["spaces"] if not s["occupied"]
    )
    assert data["free"] == free_counted


# --- POST /api/sim/toggle/<id> --------------------------------------------
def test_toggle_changes_occupancy(client):
    before = _find_space(client.get("/api/state").get_json(), "B3")
    resp = client.post("/api/sim/toggle/B3")
    assert resp.status_code == 200
    after = _find_space(resp.get_json(), "B3")
    assert after["occupied"] is not before["occupied"]


def test_toggle_unknown_space_returns_404(client):
    resp = client.post("/api/sim/toggle/ZZ")
    assert resp.status_code == 404


# --- POST /api/sim/randomize ----------------------------------------------
def test_randomize_returns_state(client):
    resp = client.post("/api/sim/randomize")
    assert resp.status_code == 200
    assert resp.get_json()["total"] == 7


# --- gpio-Modus: sim-Endpunkte muessen mit HTTP 403 antworten -------------
class _FakeGpioBackend(SensorBackend):
    """Stellt den gpio-Modus ohne echte Hardware/gpiozero nach."""

    name = "gpio"

    def __init__(self, space_ids):
        self._ids = list(space_ids)

    def read_all(self) -> dict[str, bool]:
        return {sid: False for sid in self._ids}


@pytest.fixture
def gpio_client():
    """App-Client im gpio-Modus - per Backend-Injektion, ohne gpiozero."""
    app = create_app(
        backend_factory=lambda system, settings: _FakeGpioBackend(
            system.space_ids
        )
    )
    app.testing = True
    return app.test_client()


def test_state_reports_gpio_mode(gpio_client):
    assert gpio_client.get("/api/state").get_json()["mode"] == "gpio"


def test_health_reports_gpio_mode(gpio_client):
    assert gpio_client.get("/api/health").get_json()["mode"] == "gpio"


def test_sim_toggle_forbidden_in_gpio_mode(gpio_client):
    resp = gpio_client.post("/api/sim/toggle/B3")
    assert resp.status_code == 403


def test_sim_randomize_forbidden_in_gpio_mode(gpio_client):
    resp = gpio_client.post("/api/sim/randomize")
    assert resp.status_code == 403
