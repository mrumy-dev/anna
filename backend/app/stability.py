"""Entprellung der Belegungswerte auf Fachebene.

Warum es das braucht: `gpiozero` entprellt bereits elektrisch (bounce_time),
das faengt aber nur das Prellen des Kontakts ab. Auf dem Modellparkplatz gibt es
eine zweite Zitterquelle: Ein Auto steht am Rand des Erfassungsbereichs oder
wird verschoben - dann kippt die Erkennung im Sekundentakt hin und her. In der
Web-App sieht das aus, als wuerde das Feld flackern.

Dieses Modul liegt bewusst in der Domaenenschicht: kein GPIO, kein Flask,
vollstaendig testbar ohne Hardware.

Gewaehlte Einstellung: `confirmations = 2` (in config/parking_layout.json unter
settings anpassbar). Bei 1,5 s Abfrageintervall heisst das: ein Feldwechsel wird
nach spaetestens rund 3 s angezeigt, einzelne Ausreisser verschwinden ganz.

Angewendet wird die Glaettung nur auf echte Sensoren. Im Simulator gibt es kein
elektrisches Rauschen - dort wuerde sie das Umschalten per Klick nur verzoegern.
"""

from __future__ import annotations


class ReadingStabilizer:
    """Uebernimmt einen neuen Zustand erst nach mehrfacher Bestaetigung.

    Beispiel mit confirmations=2:

        Messung 1: B1 belegt   -> gemeldet wird weiterhin "frei" (1 von 2)
        Messung 2: B1 belegt   -> jetzt gilt B1 als belegt
        Messung 3: B1 frei     -> weiterhin "belegt" (1 von 2)
        Messung 4: B1 belegt   -> Zaehler zurueckgesetzt, bleibt "belegt"

    confirmations=1 schaltet die Glaettung praktisch ab (jede Messung zaehlt).
    """

    def __init__(self, confirmations: int = 2):
        if confirmations < 1:
            raise ValueError("confirmations muss mindestens 1 sein.")
        self.confirmations = confirmations
        # Der zuletzt als gueltig uebernommene Zustand je Parkfeld.
        self._confirmed: dict[str, bool] = {}
        # Ein abweichender Messwert und wie oft er schon in Folge auftrat.
        self._pending: dict[str, tuple[bool, int]] = {}

    def apply(self, readings: dict[str, bool]) -> dict[str, bool]:
        """Filtert die Rohmessung und gibt den geglaetteten Zustand zurueck.

        Regel: Ein abweichender Messwert muss `confirmations` Mal HINTEREINANDER
        auftreten, bevor er uebernommen wird. Ein einzelner Ausreisser dazwischen
        setzt den Zaehler zurueck. Der allererste Messwert je Feld gilt sofort -
        sonst wuerde die Anzeige beim Start mit falschen Feldern beginnen.
        """
        result: dict[str, bool] = {}

        for space_id, occupied in readings.items():
            confirmed = self._confirmed.get(space_id)

            if confirmed is None:
                # Erster Messwert nach dem Start: sofort uebernehmen.
                self._confirmed[space_id] = occupied
                self._pending.pop(space_id, None)
            elif occupied == confirmed:
                # Bestaetigt den geltenden Zustand -> laufenden Zaehler verwerfen.
                self._pending.pop(space_id, None)
            else:
                pending_value, count = self._pending.get(space_id, (occupied, 0))
                count = count + 1 if pending_value == occupied else 1
                if count >= self.confirmations:
                    self._confirmed[space_id] = occupied
                    self._pending.pop(space_id, None)
                else:
                    self._pending[space_id] = (occupied, count)

            result[space_id] = self._confirmed[space_id]

        return result

    def reset(self) -> None:
        self._confirmed.clear()
        self._pending.clear()
