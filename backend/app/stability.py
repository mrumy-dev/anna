"""Entprellung der Belegungswerte auf Fachebene.

Warum es das braucht: `gpiozero` entprellt bereits elektrisch (bounce_time),
das faengt aber nur das Prellen des Kontakts ab. Auf dem Modellparkplatz gibt es
eine zweite Zitterquelle: Ein Auto steht am Rand des Erfassungsbereichs oder
wird verschoben - dann kippt die Erkennung im Sekundentakt hin und her. In der
Web-App sieht das aus, als wuerde das Feld flackern.

Dieses Modul liegt bewusst in der Domaenenschicht: kein GPIO, kein Flask,
vollstaendig testbar ohne Hardware.

STATUS: Geruest. Die eigentliche Entscheidungsregel ist noch offen -
siehe TODO in `apply()`. Solange das Modul nicht eingebunden ist, verhaelt sich
das Backend unveraendert.
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

        TODO(Team): Entscheidungsregel implementieren (ca. 8 Zeilen).

        Fuer jedes (space_id, occupied) in `readings`:
          1. Ist `space_id` noch unbekannt -> Wert direkt als bestaetigt
             uebernehmen (der erste Messwert nach dem Start soll sofort zaehlen,
             sonst startet die Demo mit falschen Feldern).
          2. Stimmt `occupied` mit dem bestaetigten Wert ueberein -> einen
             eventuell laufenden Zaehler in `_pending` verwerfen.
          3. Weicht `occupied` ab -> Zaehler in `_pending` erhoehen. Erreicht er
             `self.confirmations`, den neuen Wert nach `_confirmed` uebernehmen
             und `_pending` fuer dieses Feld loeschen.
        Rueckgabe: eine Kopie von `_confirmed` (nur die Felder aus `readings`).

        ABWAEGUNG - diese Entscheidung gehoert euch, weil sie vom Verhalten eures
        Modells abhaengt:
          - confirmations=1: sofortige Reaktion, aber sichtbares Flackern bei
            wackligem Sensor.
          - confirmations=2 bei 1,5 s Abfrageintervall: ruhige Anzeige, aber bis
            zu 3 s Verzoegerung, bis ein geparktes Auto erscheint.
          - Hoehere Werte wirken bei der Vorfuehrung schnell traege.
        Ueberlegt auch, ob "belegt werden" und "frei werden" gleich behandelt
        werden sollen - ein zu frueh als frei gemeldetes Feld aergert Besucher
        mehr als ein zu spaet gemeldetes.
        """
        raise NotImplementedError(
            "Entscheidungsregel noch offen - siehe TODO in app/stability.py"
        )

    def reset(self) -> None:
        self._confirmed.clear()
        self._pending.clear()
