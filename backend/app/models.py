"""Domaenenmodell fuer ANNA.

Enthaelt die fachliche Logik unabhaengig von Hardware und Web-Framework:
- Welche Parkareale und Parkfelder gibt es?
- Welcher Typ hat ein Parkfeld (normal/family/women/disabled)?
- Wie viele Felder sind frei (gesamt und je Typ)?

Die Hardware (Sensoren) und das Web-Backend greifen nur ueber dieses Modell
zu. Dadurch laesst sich die gesamte Logik ohne Raspberry Pi testen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SpaceType(str, Enum):
    """Parkfeldtyp gemaess gewaehlter Variante 2 (Komfort)."""

    NORMAL = "normal"
    FAMILY = "family"
    WOMEN = "women"
    DISABLED = "disabled"

    @property
    def label_de(self) -> str:
        return {
            SpaceType.NORMAL: "Normal",
            SpaceType.FAMILY: "Familie",
            SpaceType.WOMEN: "Frauen",
            SpaceType.DISABLED: "Behinderte",
        }[self]


@dataclass
class Space:
    """Ein einzelnes Parkfeld."""

    id: str
    type: SpaceType
    # gpio_pin ist IMMER die aufgeloeste BCM-Nummer (siehe app/pins.py).
    gpio_pin: int | None = None
    # So stand die Nummer in der Konfiguration - nur fuer die Diagnose-Anzeige,
    # damit man Konfigurationswert und tatsaechlich gelesenen Pin vergleichen kann.
    configured_pin: int | None = None
    invert: bool = False
    # Interner Widerstand des Pi:
    #   True  -> Pull-up  (Reed-Schalter gegen GND; Standard)
    #   False -> Pull-down (Sensor zieht bei Belegung aktiv auf HIGH, z. B. PNP)
    #   None  -> kein interner Widerstand (externe Beschaltung), active_state noetig
    pull_up: bool | None = True
    active_state: bool | None = None
    # Status-LEDs je Feld (BCM-Nummern, None = nicht verdrahtet).
    # frei -> gruen, belegt -> rot. Siehe app/actuators/.
    led_green_pin: int | None = None
    led_red_pin: int | None = None
    occupied: bool = False
    # Reservierung ist eine additive Funktion (AP 5.3). Sie wird bewusst NICHT
    # in to_dict() ausgegeben, damit der /api/state-Vertrag unveraendert bleibt;
    # der Reservierungsstand wird ueber eigene Endpunkte angeboten.
    reserved: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "type_label": self.type.label_de,
            "occupied": self.occupied,
        }


@dataclass
class Area:
    """Ein Parkareal mit mehreren Parkfeldern."""

    id: str
    name: str
    maps_url: str
    spaces: list[Space] = field(default_factory=list)

    def total(self, type: SpaceType | None = None) -> int:
        return sum(1 for s in self.spaces if type is None or s.type == type)

    def free(self, type: SpaceType | None = None) -> int:
        return sum(
            1
            for s in self.spaces
            if (type is None or s.type == type) and not s.occupied
        )

    def is_full(self) -> bool:
        return self.free() == 0

    def to_dict(self) -> dict:
        # Frei-/Gesamtzahlen je Typ, damit der Filter im Frontend einfach ist.
        counts = {}
        for t in SpaceType:
            total = self.total(t)
            if total:
                counts[t.value] = {"free": self.free(t), "total": total}
        return {
            "id": self.id,
            "name": self.name,
            "maps_url": self.maps_url,
            "free": self.free(),
            "total": self.total(),
            "is_full": self.is_full(),
            "counts_by_type": counts,
            "spaces": [s.to_dict() for s in self.spaces],
        }


class ParkingSystem:
    """Haelt alle Areale und spiegelt den aktuellen Sensorzustand wider."""

    def __init__(self, areas: list[Area]):
        self.areas = areas
        self._by_id: dict[str, Space] = {
            s.id: s for a in areas for s in a.spaces
        }

    # --- Zugriff -----------------------------------------------------------
    def space(self, space_id: str) -> Space | None:
        return self._by_id.get(space_id)

    @property
    def space_ids(self) -> list[str]:
        return list(self._by_id.keys())

    # --- Zustand aktualisieren --------------------------------------------
    def apply_readings(self, readings: dict[str, bool]) -> None:
        """Uebernimmt {space_id: occupied} aus einem Sensor-Backend."""
        for space_id, occupied in readings.items():
            space = self._by_id.get(space_id)
            if space is not None:
                space.occupied = occupied
                # Belegt ein Auto ein reserviertes Feld, ist die Reservierung
                # eingeloest und wird automatisch aufgehoben.
                if occupied:
                    space.reserved = False

    # --- Reservierung (additive Funktion, AP 5.3) -------------------------
    def reserve(self, space_id: str) -> dict:
        """Reserviert ein freies Feld. Gibt {ok, reason?} zurueck."""
        space = self._by_id.get(space_id)
        if space is None:
            return {"ok": False, "reason": "Unbekanntes Parkfeld."}
        if space.occupied:
            return {"ok": False,
                    "reason": "Feld ist belegt und nicht reservierbar."}
        space.reserved = True
        return {"ok": True}

    def cancel_reservation(self, space_id: str) -> None:
        space = self._by_id.get(space_id)
        if space is not None:
            space.reserved = False

    def reservations(self) -> list[dict]:
        return [
            {
                "id": s.id,
                "area_id": a.id,
                "type": s.type.value,
                "type_label": s.type.label_de,
            }
            for a in self.areas
            for s in a.spaces
            if s.reserved
        ]

    # --- Serialisierung fuer die API --------------------------------------
    def to_dict(self) -> dict:
        return {
            "areas": [a.to_dict() for a in self.areas],
            "total": sum(a.total() for a in self.areas),
            "free": sum(a.free() for a in self.areas),
        }


class StatsCollector:
    """Sammelt Belegungsstatistik ueber die Laufzeit (im Speicher).

    Wird bei jedem Zustands-Lesevorgang mit dem serialisierten State
    gefuettert und liefert Mittelwert/Spitzenwert der Belegung - gesamt und
    je Areal. Bewusst persistenzfrei: fuer einen Demonstrator genuegt eine
    Auswertung seit dem Start, ohne Datenbank (Nachhaltigkeit/Einfachheit).
    """

    def __init__(self) -> None:
        self._samples = 0
        self._sum_occupied = 0
        self._peak_occupied = 0
        self._areas: dict[str, dict] = {}

    def record(self, state: dict) -> None:
        occupied = state["total"] - state["free"]
        self._samples += 1
        self._sum_occupied += occupied
        self._peak_occupied = max(self._peak_occupied, occupied)
        for area in state["areas"]:
            occ = area["total"] - area["free"]
            entry = self._areas.setdefault(
                area["id"],
                {"name": area["name"], "total": area["total"],
                 "samples": 0, "sum_occupied": 0, "peak_occupied": 0},
            )
            entry["name"] = area["name"]
            entry["total"] = area["total"]
            entry["samples"] += 1
            entry["sum_occupied"] += occ
            entry["peak_occupied"] = max(entry["peak_occupied"], occ)

    def to_dict(self) -> dict:
        def avg(total: int, n: int) -> float:
            return round(total / n, 2) if n else 0.0

        return {
            "samples": self._samples,
            "peak_occupied": self._peak_occupied,
            "avg_occupied": avg(self._sum_occupied, self._samples),
            "areas": [
                {
                    "id": area_id,
                    "name": entry["name"],
                    "total": entry["total"],
                    "peak_occupied": entry["peak_occupied"],
                    "avg_occupied": avg(entry["sum_occupied"], entry["samples"]),
                }
                for area_id, entry in self._areas.items()
            ],
        }
