# ANNA Backend (Teilprojekt Informatik)

Backend und Web-App für den ANNA-Smart-Parking-Demonstrator. Läuft **ohne
Raspberry Pi** am Laptop (Sensor-Simulator) und auf dem Pi mit echten
Reed-Schaltern – nur über eine Umgebungsvariable umgeschaltet.

→ Projektkontext (Entscheidungen, Konventionen, Backlog): **`docs/Projektkontext.md`**
→ Architekturkonzept (Lieferobjekt): **`docs/Architekturkonzept.md`**
→ API-Vertrag (Schnittstelle Frontend <-> Backend): **`docs/API.md`**

## Installation & Start

**`python run.py` ist der Echtbetrieb.** Die Web-App zeigt dann ausschliesslich,
was die Sensoren am Modellparkplatz melden – grün = frei, rot = belegt. Von Hand
lässt sich daran nichts ändern; die Simulationsbefehle antworten mit HTTP 403.

```bash
# Auf dem Raspberry Pi
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-pi.txt    # gpiozero + lgpio (fuer den Echtbetrieb)

python run.py                          # -> http://<IP-des-Pi>:5000
```

Fehlt `gpiozero`, startet das Backend **nicht** und sagt im Klartext, was zu tun
ist – es zeigt niemals ersatzweise erfundene Daten.

Zum Entwickeln ohne Hardware muss der Simulator **ausdrücklich** angefordert
werden (dann erscheint ein unübersehbares rotes Banner in der App):

```bash
ANNA_BACKEND=simulated python run.py
```

`run.py` startet mit **Debug aus** und **threaded** (mehrere Besucher +
Live-Updates gleichzeitig). Auf macOS ist Port 5000 oft belegt – dann
`ANNA_PORT=5050 …`.

### Umgebungsvariablen

| Variable | Standard | Bedeutung |
|---|---|---|
| `ANNA_HOST` | `0.0.0.0` | Bind-Adresse (im WLAN erreichbar) |
| `ANNA_PORT` | `5000` | Port |
| `ANNA_BACKEND` | **`gpio`** | `gpio` = Echtbetrieb, `simulated` = ohne Hardware |
| `ANNA_DEBUG` | `0` | `1` = Debug-Modus (nur Entwicklung) |
| `ANNA_SERVER` | `werkzeug` | `werkzeug` (threaded) oder `waitress` |
| `ANNA_THREADS` | `8` | Threads bei `waitress` |
| `ANNA_STRICT` | `0` | `1` = Start abbrechen, wenn im `gpio`-Modus kein Sensor läuft |
| `ANNA_DIAG` | `0` | `1` = Pin-Zuordnung über `/diag` änderbar (nur zum Einrichten) |

### Läuft wirklich die echte Hardware?

Damit eine Vorführung nie versehentlich mit erfundenen Daten läuft, zeigt die
App die Betriebsart selbst an: grünes **LIVE**-Abzeichen bei echten Sensoren,
rotes **SIMULATION**-Abzeichen plus unübersehbares Banner (inkl. Rechnername)
im Simulationsmodus. Prüfen lässt es sich auch direkt:

```bash
curl http://<IP-des-Pi>:5000/api/health
# {"status":"ok","mode":"gpio","live":true,"host":"raspberrypi","sensors_ok":7,...}
```

`ANNA_STRICT=1` (im systemd-Dienst voreingestellt) bricht den Start ab, wenn der
`gpio`-Modus verlangt ist, aber kein einziger Sensor geöffnet werden konnte –
besser ein Dienst, der sichtbar nicht startet, als eine App, die überzeugend
aussieht und nichts misst.

### Produktiver WSGI-Server (optional)

Der eingebaute Server genügt für den Demonstrator. Für einen härteren Server:

```bash
ANNA_SERVER=waitress python run.py
# oder direkt:
waitress-serve --host=0.0.0.0 --port=5000 --threads=8 wsgi:application
```

## Tests

```bash
pytest        # laeuft ohne Pi/Hardware; 36 Tests
```

## Auf dem Raspberry Pi

**Ein-Befehl-Einrichtung inkl. Autostart** (auf dem Pi, im geklonten Repo):

```bash
bash backend/deploy/install.sh
```

Das Skript legt ein venv an, installiert Basis- **und** GPIO-Abhängigkeiten und
registriert den systemd-Dienst `anna` (Start beim Booten). Danach läuft die
Web-App unter `http://<IP-des-Pi>:5000`.

Manuell geht es auch:

```bash
pip install -r requirements.txt
pip install -r requirements-pi.txt     # gpiozero + lgpio (nur auf dem Pi)
python run.py                          # Echtbetrieb ist der Standard
```

Die echten GPIO-Pins werden aus `config/parking_layout.json` gelesen. Diese Datei
ist die Schnittstelle zu Elektro: dort steht, welches Parkfeld an welchem Pin hängt.
Verdrahtung je Sensor: Reed-Schalter zwischen GPIO und GND. Ein fehlender oder
defekter Pin bricht den Start **nicht** ab (das Feld bleibt „frei"), sondern wird
nur im Log gemeldet.

> **Wichtig – zwei Zählweisen:** `gpiozero` versteht Zahlen immer als **BCM**
> (GPIO17 sitzt auf Header-Pin 11). Wer die Pins auf der Steckerleiste abzählt,
> meint die **physische** Nummer – dann in den `settings`
> `"numbering": "board"` setzen. Sonst liest die Software andere Pins, als
> verdrahtet sind. Details: `docs/Sensor-Inbetriebnahme.md`.

### Sensoren prüfen (Inbetriebnahme)

Registriert die App ein belegtes Feld nicht, zeigt die **Diagnose-Seite** sofort,
woran es liegt – sie stellt den *rohen* Pegel neben die Auswertung:

```
http://<IP-des-Pi>:5000/diag
```

Entscheidend ist die Spalte **Wechsel**: Stellt man ein Auto auf ein Feld und
zählt sie nicht hoch, kommt das Signal gar nicht am Pi an (Verdrahtung, Pin-Nummer
oder Sensortyp). Zählt sie hoch, ist nur die Auswertung verdreht → `invert`.

Ohne Browser geht es auch direkt am Pi:

```bash
python scripts/gpio_check.py            # Live-Tabelle aller Felder
python scripts/gpio_check.py --scan     # findet den tatsächlich verdrahteten Pin
python scripts/gpio_check.py --pinout   # Tabelle BCM <-> Header-Pin
```

Zum Korrigieren der Zuordnung direkt aus dem Browser das Backend mit
`ANNA_DIAG=1` starten (Schreibzugriff; für die Vorführung wieder entfernen).

Dienst verwalten:

```bash
sudo systemctl status anna     # Status
journalctl -u anna -f          # Logs live
sudo systemctl restart anna    # nach Konfig-Aenderung
```

Die Vorlage `deploy/anna.service` liegt im Repo (Pfade/Benutzer ggf. anpassen).

## Konfiguration

Alles Modellspezifische steht in `config/parking_layout.json`: Areale, Parkfelder,
Typen (`normal`/`family`/`women`/`disabled`), GPIO-Pins und die Einstellungen.
Mehr Felder oder andere Pins = nur diese Datei ändern, kein Code-Eingriff.

| Einstellung | Standard | Bedeutung |
|---|---|---|
| `poll_interval_ms` | `1500` | Abfrageintervall der Web-App |
| `bounce_time_s` | `0.05` | elektrische Entprellung in `gpiozero` |
| `confirmations` | `2` | wie oft ein neuer Zustand bestätigt sein muss, bevor die App ihn zeigt (verhindert Flackern; `1` schaltet die Glättung ab) |
| `numbering` | `bcm` | `bcm` = GPIO-Nummer, `board` = physischer Header-Pin |
| `default_invert` | `false` | belegt/frei vertauscht |
| `default_pull_up` | `true` | interner Widerstand (siehe Sensortypen) |

Die Glättung wirkt nur auf echte Sensoren – im Simulator schaltet eine
angetippte Kachel weiterhin sofort um. Die Diagnose-Seite `/diag` zeigt
absichtlich den **ungeglätteten** Sensorwert.

## Architektur in einem Satz

Reed-Schalter → GPIO → **Sensor-Backend** (austauschbar: Simulator/GPIO) →
**Domänenmodell** (Belegungslogik) → **Flask-JSON-API** → **Web-UI**.

## Architekturkonzept nach Word exportieren

Die fertige Word-Fassung liegt bereits unter **`docs/Architekturkonzept.docx`**
(A4, Markenfarben, Inhaltsverzeichnis, Kopf-/Fusszeile). Die Mermaid-Diagramme
sind dabei in Word-native Darstellungen übersetzt (Pipeline- und Tabellenform),
sodass kein Render-Tool nötig ist.

Neu erzeugen (verwendet `docx-js`, kein pandoc/mermaid-cli erforderlich):

```bash
cd scripts && npm install docx && node build_docx.js
# erzeugt Architekturkonzept.docx -> nach ../docs/ kopieren
```

Alternativ via pandoc, falls installiert (Mermaid-Blöcke erscheinen dann als
Code; gerenderte Diagramme sieht man in der VS-Code-Vorschau oder auf GitHub):

```bash
pandoc docs/Architekturkonzept.md -o docs/Architekturkonzept.docx
```
