# ANNA Backend (Teilprojekt Informatik)

Backend und funktionsfähige Platzhalter-Oberfläche für den ANNA-Smart-Parking-
Demonstrator. Läuft **ohne Raspberry Pi** am Laptop (Sensor-Simulator) und auf dem
Pi mit echten Reed-Schaltern – nur über eine Umgebungsvariable umgeschaltet.

→ Kontext für Claude Code: **`CLAUDE.md`**
→ Architekturkonzept (Lieferobjekt): **`docs/Architekturkonzept.md`**
→ API-Vertrag (Schnittstelle zum Design): **`docs/API.md`**

## Installation & Start

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python run.py                    # Simulator -> http://localhost:5000
```

Im Simulationsmodus kannst du im Browser auf ein Parkfeld tippen, um es belegt/frei
zu schalten, oder „Zufaellig setzen" verwenden – ideal für eine Vorführung ohne
Hardware.

## Tests

```bash
pytest
```

## Auf dem Raspberry Pi

```bash
pip install gpiozero lgpio       # zusaetzlich zum requirements.txt
ANNA_BACKEND=gpio python run.py
```

Die echten GPIO-Pins werden aus `config/parking_layout.json` gelesen. Diese Datei
ist die Schnittstelle zu Elektro: dort steht, welches Parkfeld an welchem Pin hängt
(BCM-Nummerierung). Verdrahtung je Sensor: Reed-Schalter zwischen GPIO und GND.

### Autostart als Dienst (optional)

`/etc/systemd/system/anna.service`:

```ini
[Unit]
Description=ANNA Parking Backend
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/anna/backend
Environment=ANNA_BACKEND=gpio
ExecStart=/home/pi/anna/backend/.venv/bin/python run.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now anna
```

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
