# ANNA – Projektpaket Informatik

Paket für das Teilprojekt **Informatik** des PoE-Projekts ANNA (Smart-Parking-
Demonstrator, HFTM). Es ist für zwei Werkzeuge aufgebaut:

- **`design/`** → für **Claude Design**: Oberfläche der App entwerfen.
- **`backend/`** → für **Claude Code**: Backend bauen und Architekturkonzept
  ausarbeiten.

Beide Teile sind über einen festen **API-Vertrag** (`backend/docs/API.md`)
verbunden: Das Design zeigt genau die Daten, die das Backend liefert.

```
anna/
├── design/                     →  CLAUDE DESIGN
│   ├── Design-Brief.md           Briefing zum Einfügen in Claude Design
│   ├── Brand.md                  Farben, Typografie, Ton
│   └── brand/anna-logo.jpeg      Logo als Referenz
│
└── backend/                    →  CLAUDE CODE
    ├── CLAUDE.md                 Kontext + Aufgabenliste für Claude Code
    ├── README.md                 Installation, Betrieb, Tests, Deployment
    ├── docs/
    │   ├── Architekturkonzept.md  benotetes Lieferobjekt (AP 2.3)
    │   └── API.md                 Schnittstelle Design <-> Backend
    ├── config/parking_layout.json Modell + Pin-Belegung (Schnittstelle zu Elektro)
    ├── app/ …                     Flask-Backend + Platzhalter-Web-UI
    └── tests/ …                   pytest
```

## Empfohlener Ablauf

**1. Oberfläche in Claude Design**
Den Inhalt von `design/Design-Brief.md` in Claude Design einfügen, das Logo
`design/brand/anna-logo.jpeg` anhängen. Claude Design entwirft die Screens
(Übersicht, Areal-Detail, „voll"-Zustand). Farben/Typo aus `Brand.md`. Das fertige
Design exportieren.

**2. Backend in Claude Code**
Den Ordner `backend/` in Claude Code öffnen. Claude Code liest `CLAUDE.md` (voller
Kontext und Backlog) und kann sofort loslegen: Backend läuft mit
`python run.py` (Simulator, keine Hardware nötig). Tests mit `pytest`.

**3. Zusammenführen**
Das aus Claude Design exportierte UI ersetzt die Platzhalter-Oberfläche in
`backend/app/web/` und wird gegen die Endpunkte aus `backend/docs/API.md`
verdrahtet. Da die API-Form fest ist, passt beides zusammen.

## Worauf das Paket bereits Rücksicht nimmt

- **Raspberry Pi 4 + Python** statt Arduino (Entscheid aus Sitzungsprotokoll 04).
- **Variante 2:** frei/belegt + Filter (Familie/Frauen/Behinderte) + Google-Maps-
  Weiterleitung.
- Entwicklung **ohne Hardware** möglich (Sensor-Simulator), Umschalten auf echte
  Sensoren über `ANNA_BACKEND=gpio`.
- Modell mit 2 Arealen (Blumenstrasse 4 + Hauptstrasse 3 Felder).

Details und offene Punkte (u. a. die Sensor-/Magnet-Frage mit Elektro) stehen in
`backend/docs/Architekturkonzept.md`.
