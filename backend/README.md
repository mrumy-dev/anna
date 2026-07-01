# ANNA Backend (Teilprojekt Informatik)

Backend und Web-App für den ANNA-Smart-Parking-Demonstrator. Läuft **ohne
Raspberry Pi** am Laptop (Sensor-Simulator) und auf dem Pi mit echten
Reed-Schaltern – nur über eine Umgebungsvariable umgeschaltet.

→ Projektkontext (Entscheidungen, Konventionen, Backlog): **`docs/Projektkontext.md`**
→ Architekturkonzept (Lieferobjekt): **`docs/Architekturkonzept.md`**
→ API-Vertrag (Schnittstelle Frontend <-> Backend): **`docs/API.md`**

## Installation & Start

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python run.py                    # Simulator -> http://localhost:5000
```

Im Simulationsmodus kannst du im Browser auf ein Parkfeld tippen, um es belegt/frei
zu schalten, oder „Zufaellig setzen" verwenden – ideal für eine Vorführung ohne
Hardware. `run.py` startet mit **Debug aus** und **threaded** (mehrere Besucher +
Live-Updates gleichzeitig). Auf macOS ist Port 5000 oft belegt – dann
`ANNA_PORT=5050 python run.py`.

### Umgebungsvariablen

| Variable | Standard | Bedeutung |
|---|---|---|
| `ANNA_HOST` | `0.0.0.0` | Bind-Adresse (im WLAN erreichbar) |
| `ANNA_PORT` | `5000` | Port |
| `ANNA_BACKEND` | `simulated` | `simulated` oder `gpio` |
| `ANNA_DEBUG` | `0` | `1` = Debug-Modus (nur Entwicklung) |
| `ANNA_SERVER` | `werkzeug` | `werkzeug` (threaded) oder `waitress` |
| `ANNA_THREADS` | `8` | Threads bei `waitress` |

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
ANNA_BACKEND=gpio python run.py
```

Die echten GPIO-Pins werden aus `config/parking_layout.json` gelesen. Diese Datei
ist die Schnittstelle zu Elektro: dort steht, welches Parkfeld an welchem Pin hängt
(BCM-Nummerierung). Verdrahtung je Sensor: Reed-Schalter zwischen GPIO und GND. Ein
fehlender oder defekter Pin bricht den Start **nicht** ab (das Feld bleibt „frei"),
sondern wird nur im Log gemeldet.

Dienst verwalten:

```bash
sudo systemctl status anna     # Status
journalctl -u anna -f          # Logs live
sudo systemctl restart anna    # nach Konfig-Aenderung
```

Die Vorlage `deploy/anna.service` liegt im Repo (Pfade/Benutzer ggf. anpassen).

## Konfiguration

Alles Modellspezifische steht in `config/parking_layout.json`: Areale, Parkfelder,
Typen (`normal`/`family`/`women`/`disabled`), GPIO-Pins und Einstellungen
(`poll_interval_ms`, `bounce_time_s`, `default_invert`). Mehr Felder oder andere
Pins = nur diese Datei ändern, kein Code-Eingriff.

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
