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
- **Modell:** 2 Areale – *Blumenstrasse* (4 Felder), *Hauptstrasse* (4 Felder),
  8 total. Belegt durch metallene Modellautos.
- **Status-LEDs:** je Feld eine gruene und eine rote LED (frei = gruen,
  belegt = rot). Ansteuerung ueber `leds_enabled` in der Layout-Konfiguration.
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
- [x] **Fehler behoben:** `app/main.py` erzeugte auf Modulebene eine App. Dadurch
      belegte bereits der Import in `run.py` alle GPIO-Pins; die eigentliche App
      bekam keinen Pin mehr und meldete stumm nur "frei". Kein App-Objekt mehr
      auf Modulebene, zwei Regressionstests in `tests/test_production.py`.
- [x] Inbetriebnahme-Werkzeuge: Diagnose-Seite `/diag` (Rohpegel, Wechselzaehler,
      Pin-Suche, invert umschalten), `GET /api/diagnostics`, `POST /api/diag/scan`,
      `POST /api/diag/assign/<id>` (nur mit `ANNA_DIAG=1`), CLI
      `scripts/gpio_check.py`. Doku: `docs/Sensor-Inbetriebnahme.md`.
- [x] Pin-Nummerierung: `settings.numbering` = `bcm` (Standard) oder `board`,
      Umrechnung und Plausibilitaetspruefung in `app/pins.py`. Damit ist die
      Verwechslung BCM/Header-Pin ohne Umverdrahten korrigierbar.
- [x] Beschaltung je Feld konfigurierbar: `pull_up` (true/false/null) und
      `active_state` - deckt Reed, NPN und PNP sowie Modulplatinen ab.
- [x] `GpioSensorBackend` auf echter Hardware verifiziert: 8 Sensoren aktiv,
      pin_factory=LGPIOFactory, Belegung wird korrekt erkannt (07.08.2026).
- [x] Achtes Parkfeld **H4** (Hauptstrasse, GPIO4 / Header-Pin 7) ergaenzt. Die
      Tests leiten Feldanzahl und Sensorpins aus der Konfiguration ab - ein
      weiteres Feld erfordert keine Testaenderung mehr.
- [x] Status-LEDs je Feld (`app/actuators/`): frei = gruen, belegt = rot,
      Sensor ohne Signal = beide dunkel. Eigener Hintergrund-Takt, damit die
      LEDs auch ohne geoeffnete Web-App stimmen. Aus Sicherheitsgruenden
      standardmaessig abgeschaltet (`leds_enabled`), weil ein falsch
      zugeordneter AUSGANG Hardware beschaedigen kann; LED-Pins auf Sensorpins
      werden beim Laden abgelehnt.
- [ ] LED-Verdrahtung mit Elektro bestaetigen, dann `leds_enabled: true`
      setzen. Pin-Plan: `config/parking_layout.json` und Architekturkonzept 4.2.
      Pin-Budget ist mit 24 von 26 nutzbaren GPIOs knapp.
- [x] Entprellung auf Fachebene (`app/stability.py`): Ein Zustandswechsel muss
      `settings.confirmations` Mal hintereinander gemessen werden (gewaehlt: 2,
      also rund 3 s bei 1,5 s Intervall). Verhindert Flackern, wenn ein Auto am
      Rand des Erfassungsbereichs steht. Wirkt nur auf echte Sensoren; die
      Diagnose bleibt bewusst ungefiltert.
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
