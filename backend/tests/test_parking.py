"""Tests fuer die Belegungslogik und das simulierte Backend.

Laeuft ohne Raspberry Pi:  pytest
"""

from app.config import load_layout
from app.models import Area, ParkingSystem, Space, SpaceType
from app.sensors.simulated import SimulatedSensorBackend


def build_system() -> ParkingSystem:
    return ParkingSystem([
        Area("a", "Areal A", "", [
            Space("A1", SpaceType.NORMAL),
            Space("A2", SpaceType.FAMILY),
        ]),
        Area("b", "Areal B", "", [
            Space("B1", SpaceType.WOMEN),
        ]),
    ])


def test_layout_file_loads():
    system, settings = load_layout()
    assert system.areas, "Layout sollte mindestens ein Areal enthalten"
    assert settings.get("poll_interval_ms")


def test_free_and_total_counts():
    system = build_system()
    assert system.to_dict()["total"] == 3
    assert system.to_dict()["free"] == 3

    system.space("A1").occupied = True
    assert system.to_dict()["free"] == 2


def test_free_by_type():
    system = build_system()
    area_a = system.areas[0]
    assert area_a.free(SpaceType.FAMILY) == 1
    system.space("A2").occupied = True
    assert area_a.free(SpaceType.FAMILY) == 0
    assert area_a.free(SpaceType.NORMAL) == 1


def test_area_is_full():
    system = build_system()
    area_b = system.areas[1]
    assert not area_b.is_full()
    system.space("B1").occupied = True
    assert area_b.is_full()


def test_apply_readings_from_backend():
    system = build_system()
    backend = SimulatedSensorBackend(system.space_ids, prefill=0)
    backend.set("A1", True)
    system.apply_readings(backend.read_all())
    assert system.space("A1").occupied is True
    assert system.space("A2").occupied is False


def test_simulator_toggle():
    backend = SimulatedSensorBackend(["X1"], prefill=0)
    assert backend.read_all()["X1"] is False
    backend.toggle("X1")
    assert backend.read_all()["X1"] is True


def test_serialized_state_has_mode_fields():
    system = build_system()
    data = system.to_dict()
    assert set(["areas", "total", "free"]).issubset(data.keys())
    area = data["areas"][0]
    assert "counts_by_type" in area and "spaces" in area
