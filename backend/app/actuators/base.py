"""Abstrakte Aktor-Schnittstelle fuer die Status-LEDs.

Je Parkfeld gibt es zwei LEDs:

    frei    -> gruene LED an,  rote LED aus
    belegt  -> rote LED an,    gruene LED aus

Die Zuordnung folgt direkt der Belegung: 0 (frei) = gruen, 1 (belegt) = rot.

Ein dritter Fall ist wichtig: Meldet ein Sensor gar nichts (Pin defekt, nicht
verdrahtet), ist die Belegung UNBEKANNT. Dann bleiben beide LEDs dunkel - eine
dunkle Stelle im Modell ist ehrlicher als ein gruenes Licht, das faelschlich
"frei" verspricht.

Wie beim Sensor-Backend steckt die Hardware ausschliesslich hinter dieser
Schnittstelle; die Farblogik selbst ist reine Rechnung und ohne Raspberry Pi
testbar.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

log = logging.getLogger("anna.leds")


def colors_for(occupied: bool | None) -> tuple[bool, bool]:
    """Liefert (gruen_an, rot_an) fuer einen Belegungszustand.

    occupied is None bedeutet "unbekannt" -> beide LEDs aus.
    """
    if occupied is None:
        return (False, False)
    return (not occupied, bool(occupied))


class LedBackend(ABC):
    """Gemeinsame Schnittstelle aller LED-Ausgaben."""

    name: str = "abstract"

    @abstractmethod
    def apply(self, occupancy: dict[str, bool | None]) -> None:
        """Setzt die LEDs gemaess {space_id: belegt}."""
        raise NotImplementedError

    def states(self) -> dict[str, dict]:
        """Aktueller LED-Zustand je Feld - fuer die Diagnose-Anzeige."""
        return {}

    def health(self) -> dict:
        return {"ok": 0, "total": 0, "failed": []}

    def all_off(self) -> None:
        """Alle LEDs ausschalten (beim Beenden)."""
        return None

    def close(self) -> None:
        return None


class NullLedBackend(LedBackend):
    """Keine LEDs - wenn die Ansteuerung nicht eingeschaltet ist."""

    name = "none"

    def apply(self, occupancy: dict[str, bool | None]) -> None:
        return None


class SimulatedLedBackend(LedBackend):
    """Haelt den LED-Zustand nur im Speicher.

    Damit laesst sich die LED-Logik am Laptop entwickeln und auf der
    Diagnose-Seite anzeigen, ohne dass eine einzige LED verdrahtet ist.
    """

    name = "simulated"

    def __init__(self, space_ids: list[str]):
        self._states: dict[str, dict] = {
            sid: {"green": False, "red": False} for sid in space_ids
        }

    def apply(self, occupancy: dict[str, bool | None]) -> None:
        for space_id, occupied in occupancy.items():
            if space_id not in self._states:
                continue
            green, red = colors_for(occupied)
            self._states[space_id] = {"green": green, "red": red}

    def states(self) -> dict[str, dict]:
        return {sid: dict(state) for sid, state in self._states.items()}

    def health(self) -> dict:
        return {"ok": len(self._states), "total": len(self._states), "failed": []}

    def all_off(self) -> None:
        for state in self._states.values():
            state["green"] = False
            state["red"] = False
