# Projektkontext – Teilprojekt Informatik (ANNA)

Diese Datei fasst Kontext und Konventionen fuer die Backend- und Frontend-
Entwicklung zusammen. Bitte vor dem Arbeiten lesen.

## Was ist ANNA?

ANNA ist ein **Smart-Parking-Demonstrator** (Schulprojekt, HFTM, „Projektorientierte
Engineering-Ausbildung" PoE, Gruppe 11). Ein Modellparkplatz erkennt mit Sensoren,
welche Parkfelder belegt sind, und zeigt das in einer Web-App an. Es ist ein
interdisziplinäres Projekt (Maschinenbau, Elektro, Informatik, Prozesstechnik).

**Unser Teil (Teilprojekt Informatik):** die Software – Sensoren auslesen,
Belegungslogik, JSON-API und Web-UI. Autoren: Faris Ridzal, Mohamed Rumy.

## Bindende Projektentscheidungen (nicht eigenmächtig ändern)

- **Variante 2 „Komfort":** frei/belegt je Feld **+ Filter** nach Typ (Familie,
  Frauen, Behinderte). Anfahrt = **Weiterleitung an Google Maps**, **keine eigene
  GPS-Navigation**.
- **Rechner: Raspberry Pi 4**, Sprache **Python**.
- **Sensor: Magnetschalter / Reed-Kontakt** je Parkfeld (digitales Signal).
- **Modell:** 2 Areale – *Blumenstrasse* (4 Felder), *Hauptstrasse* (3 Felder),
  7 total. Belegt durch metallene Modellautos.
- Markenfarben: Dunkelblau (#16314f) + Grün (#3aaa35).

## Was diese Codebasis schon kann

Ein lauffähiges Flask-Backend mit sauberer Schichtung und eine vollständige
Web-App, die **ohne Raspberry Pi** am Laptop läuft (Sensor-Simulator) und auf dem
Pi nur durch eine Umgebungsvariable auf echtes GPIO umgestellt wird.

```
anna-backend/
├── config/parking_layout.json   # Areale, Felder, Typen, GPIO-Pins  <- Schnittstelle zu Elektro
├── app/
│   ├── models.py                # Domäne: Area, Space, SpaceType, ParkingSystem, StatsCollector
│   ├── config.py                # Layout laden
│   ├── main.py                  # Flask: API + Auslieferung Web-UI
│   ├── sensors/
│   │   ├── base.py              # SensorBackend (abstrakt): read_all()
│   │   ├── simulated.py         # Simulator (Standard, ohne Hardware)
│   │   └── gpio.py              # gpiozero-Backend (echte Reed-Schalter)
│   └── web/                     # Web-App: templates/index.html, static/{style.css,app.js,icon.svg,manifest.webmanifest}
├── tests/                       # pytest (laeuft ohne Pi): test_parking, test_api, test_features
├── docs/Architekturkonzept.md   # benotetes Lieferobjekt (Deutsch)
└── run.py
```

API (Kernvertrag in `docs/API.md`): `GET /api/state`, `GET /api/health`,
`POST /api/sim/toggle/<id>`, `POST /api/sim/randomize` (sim-Endpunkte nur im
Simulationsmodus). Additiv: `GET /api/stream` (SSE), `GET /api/stats`,
`GET /api/reservations`, `POST`/`DELETE /api/reserve/<id>`.

## So läuft es

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py            # Simulator -> http://localhost:5000
pytest                   # Tests
```
Auf macOS belegt der AirPlay-Empfänger Port 5000; dann
`ANNA_PORT=5050 python run.py` verwenden.
Auf dem Pi zusätzlich `pip install gpiozero lgpio`, dann
`ANNA_BACKEND=gpio python run.py`.

## Architekturprinzip (bitte beibehalten)

1. **Hardware steckt nur hinter `SensorBackend`.** Neue Sensorarten = neue
   Implementierung von `read_all()`. Die Domäne und das Web kennen kein GPIO.
2. **Das Modell ist konfigurationsgetrieben.** Felder, Typen und Pins stehen in
   `parking_layout.json`, nicht im Code.
3. **Es muss immer ohne Hardware lauffähig bleiben** (Simulator). Niemals einen
   harten Import von `gpiozero` auf Modulebene einführen – nur lazy in `gpio.py`.
4. Domänenlogik bleibt frei von Flask- und Hardware-Abhängigkeiten und ist
   getestet.
5. **Der API-Vertrag in `docs/API.md` bleibt stabil.** Zusatzfunktionen kommen
   über neue Endpunkte, nicht durch Änderung bestehender Antworten.

## Konventionen

- **UI-Texte auf Deutsch**, Code-Bezeichner auf Englisch.
- Keine Umlaute in Code-Kommentaren/Strings, die in Konsolen landen (ae/oe/ue),
  um Encoding-Probleme auf dem Pi zu vermeiden. In der Web-UI sind Umlaute ok.
- Kleine, klar benannte Funktionen; Typannotationen verwenden.
- Vor dem Commit: `pytest` muss grün sein.

## Offene Aufgaben (Backlog)

Kurzfristig (diese/nächste Woche):
- [x] `docs/Architekturkonzept.md` inhaltlich finalisiert (Status Version 1.0,
      Datum 18.06.2026, Änderungsverlauf). Word-Export nach `docs/`.
- [ ] GPIO-Pins mit Elektro abstimmen und in `parking_layout.json` eintragen.
- [ ] Sensor-Frage klären (Magnet am Auto vs. induktiver Sensor) und im
      Architekturkonzept festhalten.

Software-Ausbau:
- [x] Produktionsreif fuer den Pi: Debug standardmaessig aus, threaded-Server
      (mehrere Besucher + SSE), optionaler WSGI-Server (waitress/gunicorn via
      `wsgi.py`), GPIO-Cleanup, robustes GPIO-Backend (defekter Pin killt den
      Start nicht), Layout-Validierung, systemd-Autostart (`deploy/`).
- [ ] `GpioSensorBackend` auf echter Hardware verifizieren (Pull-up, Entprellung,
      ggf. `invert` je Feld). Logik (inkl. `invert`) und Ausfallsicherheit sind
      per Fake-gpiozero-Test bereits abgesichert; finaler Test steht am echten Pi aus.
- [x] Live-Updates per Server-Sent-Events (`GET /api/stream`, additiv).
- [x] AP 5.3 teilweise: Reservierung (`/api/reserve/...`) und
      Statistik/Auslastung (`/api/stats`) umgesetzt. Schranke als Aktor offen.
- [x] Web-UI als vollständige Web-App (Live-Updates, Reservierung, Auslastung,
      installierbar). Optional: eigene Detailansicht je Areal.
- [x] Tests erweitert: API-Endpunkte mit Flask-Testclient (`tests/test_api.py`),
      Reservierung/Statistik/SSE/GPIO-Backend (`tests/test_features.py`).
      `create_app(backend_factory=...)` erlaubt Backend-Injektion für Tests.

Beim Erledigen einer Aufgabe: Häkchen setzen und kurz dokumentieren, was geändert
wurde (hilft beim Projektcontrolling und Änderungsmanagement, das benotet wird).

## Nützlicher Bewertungskontext

Benotet werden u. a. **branchenspezifische Vorgehensweisen** (für uns: saubere
Software-Praxis – Versionskontrolle/Git, modularer Aufbau, dokumentierte
Schnittstelle, Tests) und **Nachhaltigkeit**. Solche Aspekte beim Ausbau bewusst
mitnehmen und im Bericht sichtbar machen.
