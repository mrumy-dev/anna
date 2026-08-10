# Pin-Belegung – Übergabe an Elektro

> **Diese Datei wird erzeugt.** Quelle ist `config/parking_layout.json`;
> erstellt mit `python scripts/pinplan.py --write`. Nicht von Hand bearbeiten –
> Änderungen gehören in die JSON, sonst laufen Tabelle und Software auseinander.

## Die zwei Zählweisen

Jede Zeile nennt **beide** Nummern, weil genau ihre Verwechslung die häufigste
Fehlerquelle ist:

- **BCM** ist die GPIO-Nummer, mit der die Software arbeitet (`GPIO17`).
- **Header** ist die abgezählte Position auf der 40-poligen Steckerleiste.

Die Konfiguration ist zurzeit auf `numbering: "bcm"` gestellt – die Zahlen
in der JSON sind also **GPIO-Nummern (BCM)**.

> Als *physische* Pins wären die Zahlen 17 und 25 die 3,3-V-Versorgung bzw. Masse –
> dort kann nie ein Signal anliegen. Wird nach Header-Nummern verdrahtet, muss in
> der JSON `"numbering": "board"` gesetzt werden.

## Sensoren (ein Reed-/Magnetschalter je Parkfeld)

Verdrahtung: **Schalter zwischen GPIO-Pin und GND**, interner Pull-up aktiv.

| Parkfeld | Areal | Typ | BCM | Header | Status | Hinweis |
|---|---|---|---|---|---|---|
| B1 | Parkplatz Blumenstrasse | normal | GPIO17 | 11 | **bestätigt** |  |
| B2 | Parkplatz Blumenstrasse | family | GPIO27 | 13 | **bestätigt** |  |
| B3 | Parkplatz Blumenstrasse | women | GPIO22 | 15 | **bestätigt** |  |
| B4 | Parkplatz Blumenstrasse | disabled | GPIO23 | 16 | **bestätigt** |  |
| H1 | Parkplatz Hauptstrasse | normal | GPIO24 | 18 | **bestätigt** |  |
| H2 | Parkplatz Hauptstrasse | normal | GPIO25 | 22 | **bestätigt** |  |
| H3 | Parkplatz Hauptstrasse | family | GPIO5 | 29 | **bestätigt** |  |
| H4 | Parkplatz Hauptstrasse | normal | GPIO4 | 7 | Vorschlag |  |

## Status-LEDs (grün + rot je Parkfeld)

**frei = grün, belegt = rot** (0 = grün, 1 = rot). Liefert ein Sensor gar nichts,
bleiben beide LEDs dunkel. Verdrahtung je LED: **GPIO → Vorwiderstand (z. B. 330 Ω) → LED → GND**.

| Parkfeld | grün BCM | grün Header | rot BCM | rot Header | Status | Hinweis |
|---|---|---|---|---|---|---|
| B1 | GPIO6 | 31 | GPIO12 | 32 | Vorschlag |  |
| B2 | GPIO13 | 33 | GPIO16 | 36 | Vorschlag |  |
| B3 | GPIO19 | 35 | GPIO20 | 38 | Vorschlag |  |
| B4 | GPIO21 | 40 | GPIO26 | 37 | Vorschlag |  |
| H1 | GPIO7 | 26 | GPIO8 | 24 | Vorschlag |  |
| H2 | GPIO9 | 21 | GPIO10 | 19 | Vorschlag |  |
| H3 | GPIO11 | 23 | GPIO18 | 12 | Vorschlag |  |
| H4 | GPIO2 | 3 | GPIO3 | 5 | Vorschlag | I2C SDA - hat feste 1k8-Pull-ups auf der Platine / I2C SCL - hat feste 1k8-Pull-ups auf der Platine |

Die LED-Ansteuerung ist zurzeit **abgeschaltet** (`leds_enabled: false`).
Sie wird erst aktiv, wenn die Verdrahtung steht und der Wert in der JSON auf `true`
gesetzt wird – LEDs sind Ausgänge, ein falsch zugeordneter Ausgang kann Hardware
beschädigen.

## Pin-Budget

- Belegt: **24** GPIOs (8 Felder × 1 Sensor + 2 LEDs).
- Nutzbar sind GPIO2–27 (26 Stück); GPIO0/1 sind für das HAT-EEPROM reserviert.
- Noch frei: **GPIO14 (Header 8), GPIO15 (Header 10)**.
- GPIO14/15 sind für die serielle Konsole vorgesehen; GPIO2/3 tragen feste
  Pull-up-Widerstände (daran hängende LEDs glimmen beim Booten kurz).
- Weitere Aktoren (z. B. Schranke) benötigen einen Portexpander (MCP23017) oder
  ein Schieberegister.

## Änderungen

Pin ändern → in `config/parking_layout.json` eintragen → `python scripts/pinplan.py --write`
→ Dienst neu starten (`sudo systemctl restart anna`). Die Zuordnung lässt sich auch
im laufenden Betrieb über die Diagnose-Seite `/diag` korrigieren (`ANNA_DIAG=1`).
