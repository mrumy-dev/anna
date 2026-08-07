"""Simuliertes Sensor-Backend (kein Raspberry Pi noetig).

Haelt den Belegungszustand im Speicher. Felder lassen sich ueber die API
umschalten (Klick im Web-UI) oder zufaellig setzen. Damit kann die komplette
Software inkl. Web-UI am Laptop entwickelt und vorgefuehrt werden, bevor die
echten Sensoren von Elektro geliefert sind.

Der Simulator liefert bewusst dieselben Diagnosedaten wie das GPIO-Backend
(Rohpegel, Pegelwechsel). So laesst sich die Diagnose-Seite ohne Hardware
entwickeln und vorfuehren - der simulierte "Rohpegel" verhaelt sich dabei wie
ein Reed-Schalter mit Pull-up: 1 = offen/frei, 0 = geschlossen/belegt.
"""

from __future__ import annotations

import random

from .base import ChangeTracker, SensorBackend


class SimulatedSensorBackend(SensorBackend):
    name = "simulated"

    def __init__(self, space_ids: list[str], prefill: int = 2):
        # Alle Felder zu Beginn frei ...
        self._state: dict[str, bool] = {sid: False for sid in space_ids}
        # ... ausser ein paar belegten, damit die Demo nicht leer startet.
        for sid in space_ids[:prefill]:
            self._state[sid] = True
        self._tracker = ChangeTracker()

    def read_all(self) -> dict[str, bool]:
        for space_id, occupied in self._state.items():
            self._tracker.record(space_id, 0 if occupied else 1)
        return dict(self._state)

    def diagnostics(self) -> list[dict]:
        readings = self.read_all()
        return [
            {
                "space_id": space_id,
                "pin": None,
                "configured_pin": None,
                "pin_label": "Simulation (kein Pin)",
                "board_pin": None,
                "hint": None,
                "raw": 0 if occupied else 1,
                "occupied": occupied,
                "invert": False,
                "pull_up": True,
                "ok": True,
                "error": None,
                "changes": self._tracker.changes(space_id),
                "last_change_s": self._tracker.seconds_since_change(space_id),
            }
            for space_id, occupied in readings.items()
        ]

    # --- Steuerung nur im Simulationsmodus --------------------------------
    def toggle(self, space_id: str) -> bool:
        if space_id in self._state:
            self._state[space_id] = not self._state[space_id]
        return self._state.get(space_id, False)

    def set(self, space_id: str, occupied: bool) -> None:
        if space_id in self._state:
            self._state[space_id] = occupied

    def randomize(self) -> None:
        for sid in self._state:
            self._state[sid] = random.random() < 0.5
