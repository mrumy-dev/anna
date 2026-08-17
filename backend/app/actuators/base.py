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

SELBSTTEST: Fuer Eingaenge kann man Pegel beobachten - fuer Ausgaenge geht das
prinzipiell nicht, man muss sie treiben und hinsehen. Dafuer gibt es
`set_override()`: ein Testmuster uebernimmt die LEDs fuer einige Sekunden,
danach laeuft der Normalbetrieb von selbst weiter. Der Hintergrund-Takt ruft
weiterhin `apply()` auf; solange die Uebernahme laeuft, schreibt sie das
Testmuster statt der Belegung.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

log = logging.getLogger("anna.leds")

#: (gruen_an, rot_an)
Colours = tuple[bool, bool]


def colors_for(occupied: bool | None) -> Colours:
    """Liefert (gruen_an, rot_an) fuer einen Belegungszustand.

    occupied is None bedeutet "unbekannt" -> beide LEDs aus.
    """
    if occupied is None:
        return (False, False)
    return (not occupied, bool(occupied))


class LedBackend(ABC):
    """Gemeinsame Schnittstelle aller LED-Ausgaben."""

    name: str = "abstract"

    def __init__(self) -> None:
        self._override: dict[str, Colours] | None = None
        self._override_until: float = 0.0
        self._override_label: str = ""

    # --- Ausgabe ----------------------------------------------------------
    def apply(self, occupancy: dict[str, bool | None]) -> None:
        """Setzt die LEDs gemaess {space_id: belegt}.

        Laeuft gerade ein Selbsttest, hat dessen Muster Vorrang.
        """
        states = {sid: colors_for(occ) for sid, occ in occupancy.items()}
        if self.override_active():
            states = {sid: self._override.get(sid, (False, False))
                      for sid in states}
        self._write(states)

    @abstractmethod
    def _write(self, states: dict[str, Colours]) -> None:
        """Schreibt den Zustand tatsaechlich auf die Ausgaenge."""
        raise NotImplementedError

    # --- Selbsttest -------------------------------------------------------
    def set_override(self, states: dict[str, Colours] | None,
                     seconds: float = 10.0, label: str = "") -> None:
        """Uebernimmt die LEDs voruebergehend (Testmuster) oder gibt sie frei."""
        if states is None:
            self._override = None
            self._override_until = 0.0
            self._override_label = ""
            log.info("LED-Selbsttest beendet, Normalbetrieb laeuft weiter.")
            return

        self._override = dict(states)
        self._override_until = time.monotonic() + max(0.5, seconds)
        self._override_label = label
        log.info("LED-Selbsttest '%s' fuer %.0f s aktiv.", label or "?", seconds)
        # Sofort schreiben - der Hintergrund-Takt haelt es danach.
        self._write(dict(self._override))

    def override_active(self) -> bool:
        if self._override is None:
            return False
        if time.monotonic() >= self._override_until:
            self._override = None
            self._override_label = ""
            return False
        return True

    def override_info(self) -> dict | None:
        if not self.override_active():
            return None
        return {
            "label": self._override_label,
            "seconds_left": round(self._override_until - time.monotonic(), 1),
        }

    # --- Auskunft ---------------------------------------------------------
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
    """Keine LEDs - abgeschaltet oder nicht startbar.

    `reason` haelt fest WARUM nichts geschaltet wird. Ohne diese Begruendung
    sieht ein abgeschalteter Ausgang exakt wie ein Hardwarefehler aus.
    """

    name = "none"

    def __init__(self, reason: str = "LED-Ansteuerung ist abgeschaltet."):
        super().__init__()
        self.reason = reason

    def _write(self, states: dict[str, Colours]) -> None:
        return None


class SimulatedLedBackend(LedBackend):
    """Haelt den LED-Zustand nur im Speicher.

    Damit laesst sich die LED-Logik am Laptop entwickeln und auf der
    Diagnose-Seite anzeigen, ohne dass eine einzige LED verdrahtet ist.
    """

    name = "simulated"

    def __init__(self, space_ids: list[str]):
        super().__init__()
        self._states: dict[str, dict] = {
            sid: {"green": False, "red": False} for sid in space_ids
        }

    def _write(self, states: dict[str, Colours]) -> None:
        for space_id, (green, red) in states.items():
            if space_id in self._states:
                self._states[space_id] = {"green": green, "red": red}

    def states(self) -> dict[str, dict]:
        return {sid: dict(state) for sid, state in self._states.items()}

    def health(self) -> dict:
        return {"ok": len(self._states), "total": len(self._states), "failed": []}

    def all_off(self) -> None:
        for state in self._states.values():
            state["green"] = False
            state["red"] = False


# --- Testmuster ------------------------------------------------------------
def test_pattern(space_ids: list[str], mode: str,
                 space: str | None = None) -> dict[str, Colours]:
    """Baut das Muster fuer den LED-Selbsttest.

    gruen  - alle gruenen LEDs an   (prueft: sitzt jede gruene LED richtig?)
    rot    - alle roten LEDs an
    beide  - alle LEDs an           (prueft: leuchtet ueberhaupt etwas?)
    aus    - alles dunkel
    feld   - nur ein Feld leuchtet  (prueft: stimmt die Zuordnung Feld <-> LED?)
    """
    mode = (mode or "").strip().lower()
    if mode in {"gruen", "green"}:
        return {sid: (True, False) for sid in space_ids}
    if mode in {"rot", "red"}:
        return {sid: (False, True) for sid in space_ids}
    if mode in {"beide", "both", "all"}:
        return {sid: (True, True) for sid in space_ids}
    if mode in {"aus", "off"}:
        return {sid: (False, False) for sid in space_ids}
    if mode in {"feld", "field"}:
        if space not in space_ids:
            raise ValueError(f"Unbekanntes Parkfeld '{space}'.")
        return {sid: (sid == space, sid == space) for sid in space_ids}
    raise ValueError(
        f"Unbekanntes Testmuster '{mode}'. Erlaubt: gruen, rot, beide, aus, feld."
    )
