"""Abstrakte Sensor-Schnittstelle.

Jedes Backend (Simulator oder echtes GPIO) liefert ueber dieselbe Methode
`read_all()` ein Dictionary {space_id: occupied}. Das Backend wird beim Start
ueber eine Umgebungsvariable gewaehlt (siehe app/config.py), sodass derselbe
Code auf dem Laptop (Simulator) und auf dem Raspberry Pi (GPIO) laeuft.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


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

    def close(self) -> None:
        """Ressourcen freigeben (z. B. GPIO-Pins). Default: nichts zu tun."""
        return None
