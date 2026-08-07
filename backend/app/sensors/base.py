"""Abstrakte Sensor-Schnittstelle.

Jedes Backend (Simulator oder echtes GPIO) liefert ueber dieselbe Methode
`read_all()` ein Dictionary {space_id: occupied}. Das Backend wird beim Start
ueber eine Umgebungsvariable gewaehlt (siehe app/config.py), sodass derselbe
Code auf dem Laptop (Simulator) und auf dem Raspberry Pi (GPIO) laeuft.

Zusaetzlich liefert jedes Backend `diagnostics()`. Das ist die Grundlage der
Diagnose-Seite: sie zeigt nicht nur die fertige Interpretation "belegt/frei",
sondern auch den ROHEN elektrischen Pegel und wie oft er sich bereits geaendert
hat. Damit laesst sich beim Einrichten der Hardware die entscheidende Frage
beantworten: bewegt sich der Pin ueberhaupt?
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod


class ChangeTracker:
    """Zaehlt Pegelwechsel je Parkfeld.

    Ohne diese Information ist eine Ferndiagnose kaum moeglich: Ein Feld, das
    dauerhaft "frei" meldet, kann entweder falsch verdrahtet sein (Pegel bewegt
    sich nie) oder nur falsch interpretiert werden (Pegel wechselt, aber die
    Zuordnung belegt/frei ist verdreht). Der Zaehler unterscheidet beides.
    """

    def __init__(self) -> None:
        self._last: dict[str, int] = {}
        self._changes: dict[str, int] = {}
        self._last_change_at: dict[str, float] = {}

    def record(self, key: str, level: int | None) -> None:
        if level is None:
            return
        previous = self._last.get(key)
        if previous is not None and previous != level:
            self._changes[key] = self._changes.get(key, 0) + 1
            self._last_change_at[key] = time.monotonic()
        self._last[key] = level

    def changes(self, key: str) -> int:
        return self._changes.get(key, 0)

    def seconds_since_change(self, key: str) -> float | None:
        stamp = self._last_change_at.get(key)
        return None if stamp is None else round(time.monotonic() - stamp, 1)

    def reset(self) -> None:
        self._last.clear()
        self._changes.clear()
        self._last_change_at.clear()


class SensorBackend(ABC):
    """Gemeinsame Schnittstelle aller Sensor-Quellen."""

    #: Klartextname fuer die API ("simulated" oder "gpio").
    name: str = "abstract"

    @abstractmethod
    def read_all(self) -> dict[str, bool]:
        """Liefert {space_id: occupied} fuer alle Parkfelder.

        occupied == True bedeutet: Feld ist belegt.
        """
        raise NotImplementedError

    def diagnostics(self) -> list[dict]:
        """Detailzustand je Parkfeld fuer die Diagnose-Seite.

        Standard: leitet alles aus read_all() ab. Backends mit echter Hardware
        ergaenzen Rohpegel, Pin-Nummer und Fehlerzustand.
        """
        return [
            {
                "space_id": space_id,
                "pin": None,
                "raw": None,
                "occupied": occupied,
                "ok": True,
                "error": None,
                "changes": 0,
                "last_change_s": None,
            }
            for space_id, occupied in self.read_all().items()
        ]

    def close(self) -> None:
        """Ressourcen freigeben (z. B. GPIO-Pins). Default: nichts zu tun."""
        return None
