# ANNA – Teilprojekt Informatik

Software für den **Smart-Parking-Demonstrator ANNA** (PoE-Projekt, HFTM,
Gruppe 11). Ein Modellparkplatz erkennt mit Sensoren, welche Parkfelder belegt
sind; eine Web-App zeigt das in Echtzeit an. Dieses Repository enthält das
**Backend (Flask-API)** und das **Frontend (Web-App)**.

Autoren: Faris Ridzal, Mohamed Rumy.

```
anna/
└── backend/
    ├── README.md                  Installation, Betrieb, Tests, Deployment
    ├── docs/
    │   ├── Architekturkonzept.md   benotetes Lieferobjekt (AP 2.3) + .docx-Export
    │   ├── API.md                  API-Vertrag (Frontend <-> Backend)
    │   └── Projektkontext.md       Entscheidungen, Konventionen, Backlog
    ├── config/parking_layout.json  Modell + Pin-Belegung (Schnittstelle zu Elektro)
    ├── app/                        Flask-Backend + Web-App (HTML/CSS/JS)
    └── tests/                      pytest
```

## Schnellstart

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python run.py            # Simulator -> http://localhost:5000
pytest                   # Tests
```

Im Simulationsmodus laufen Backend und Web-App **ohne Hardware** am Laptop: auf
ein Parkfeld tippen, um es zu belegen/frei zu geben, oder „Zufaellig setzen".
Auf macOS belegt der AirPlay-Empfänger Port 5000 – dann `ANNA_PORT=5050
python run.py` verwenden.

Auf dem **Raspberry Pi 4** mit echten Reed-Schaltern: `pip install gpiozero lgpio`
und `ANNA_BACKEND=gpio python run.py` (Pin-Belegung in
`backend/config/parking_layout.json`). Details siehe `backend/README.md`.

## Was die App kann

- **Live-Anzeige** frei/belegt je Parkfeld (Polling + Server-Sent-Events).
- **Filter** nach Parkfeldtyp (Alle / Normal / Familie / Frauen / Behinderte).
- **„Voll"-Zustand** je Areal mit Verweis auf ein freies Alternativ-Areal.
- **Anfahrt** per Google-Maps-Link (keine eigene Navigation, Variante 2).
- **Reservierung** einzelner Felder und **Auslastungsanzeige**.
- Mobil-zuerst, responsiv, **als Web-App installierbar** (Homescreen).

## Architektur in einem Satz

Reed-Schalter → GPIO → **Sensor-Backend** (austauschbar: Simulator/GPIO) →
**Domänenmodell** (Belegungslogik) → **Flask-JSON-API** → **Web-App**.

Das Backend ist konfigurationsgetrieben (`config/parking_layout.json`) und läuft
immer ohne Hardware (Simulator). Hintergrund, Entscheidungen und offene Punkte
(u. a. die Sensor-/Magnet-Frage mit Elektro) stehen in
`backend/docs/Architekturkonzept.md`.
