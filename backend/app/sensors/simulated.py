"""Simuliertes Sensor-Backend (kein Raspberry Pi noetig).

Haelt den Belegungszustand im Speicher. Felder lassen sich ueber die API
umschalten (Klick im Web-UI) oder zufaellig setzen. Damit kann die komplette
Software inkl. Web-UI am Laptop entwickelt und vorgefuehrt werden, bevor die
echten Sensoren von Elektro geliefert sind.
"""

from __future__ import annotations

import random

from .base import SensorBackend


class SimulatedSensorBackend(SensorBackend):
    name = "simulated"

    def __init__(self, space_ids: list[str], prefill: int = 2):
        # Alle Felder zu Beginn frei ...
        self._state: dict[str, bool] = {sid: False for sid in space_ids}
        # ... ausser ein paar belegten, damit die Demo nicht leer startet.
        for sid in space_ids[:prefill]:
            self._state[sid] = True

    def read_all(self) -> dict[str, bool]:
        return dict(self._state)

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
