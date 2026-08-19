# Sensoren anschliessen und pruefen

Anleitung fuer den Fall, dass ein Parkfeld **belegt** ist, die App es aber
**nicht anzeigt**. Sie fuehrt in wenigen Minuten zur Ursache, ohne dass jemand
Code aendern muss.

Werkzeug dafuer ist die Diagnose-Seite:

```
http://<IP-des-Pi>:5000/diag
```

---

## Raspberry Pi 5: gpiozero und lgpio NUR aus den Systempaketen

> **Wenn WEDER Sensoren NOCH LEDs funktionieren und im Log
> `pin_factory=NoneType` oder `Unable to load any default pin factory` steht,
> ist es fast immer das hier.**

Auf dem Raspberry Pi 5 haengen die Header-Pins am neuen RP1-Chip. Es gibt
**kein `/dev/gpiochip0` mehr** - auf unserem Geraet ist es `gpiochip15`. Die
PyPI-Version von `lgpio` sucht fest nach `gpiochip0` und scheitert mit
`can not open gpiochip`. `gpiozero` findet daraufhin gar keine Pin-Factory,
und der Pi kann weder Sensoren lesen noch LEDs schalten.

Das Tueckische: Das Backend startet trotzdem, die Web-App laeuft, alle Felder
stehen dauerhaft auf "frei". Von aussen sieht das exakt wie ein Hardwarefehler
aus. Genau das hat uns am 19.08.2026 einen halben Tag gekostet.

Pruefen:

```bash
.venv/bin/python -c "from gpiozero import Device; Device.ensure_pin_factory(); print(type(Device.pin_factory).__name__)"
```

Erwartet wird `LGPIOFactory` oder `RPiGPIOFactory` - niemals ein Fehler.

Reparieren:

```bash
sudo apt install -y python3-gpiozero python3-lgpio python3-rpi-lgpio
cd ~/anna/backend && rm -rf .venv
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt        # NUR die Basis, kein gpiozero/lgpio
sudo systemctl restart anna
```

`bash deploy/install.sh` macht das seit dieser Version von selbst richtig.

### SPI und I2C muessen ausgeschaltet bleiben

GPIO7-11 gehoeren zur SPI-, GPIO2/3 zur I2C-Schnittstelle. Sind diese
eingeschaltet, beanspruchen die Kerneltreiber die Pins und die daran
haengenden LEDs (H1-H4) lassen sich nicht ansteuern.

```bash
sudo raspi-config nonint get_spi     # 1 = aus, richtig
sudo raspi-config nonint get_i2c     # 1 = aus, richtig
```

Steht dort `0`, abschalten und **neu starten**:

```bash
sudo raspi-config nonint do_spi 1 && sudo raspi-config nonint do_i2c 1 && sudo reboot
```

---

## Zuerst: Sehe ich ueberhaupt echte Sensoren?

Bevor irgendetwas gemessen wird, muss zweifelsfrei feststehen, dass die
angezeigte Seite **nicht** die Simulation ist. Drei Merkmale, alle sofort
sichtbar:

| Merkmal | Echte Sensoren (gpio) | Simulation |
|---|---|---|
| Abzeichen oben rechts | gruenes **LIVE** | rotes **SIMULATION** |
| Banner oben auf der Seite | keines | grosser roter Kasten „Simulationsmodus – keine echten Sensoren" |
| Tippen auf eine Kachel | passiert nichts | Kachel schaltet um |

Zusaetzlich nennt das Banner den **Rechnernamen**, mit dem der Browser verbunden
ist. Steht dort der Name eures Laptops statt des Pi, ist die falsche Adresse
geoeffnet.

Hart nachpruefen laesst es sich hier:

```bash
curl http://<IP-des-Pi>:5000/api/health
```

```json
{ "status": "ok", "mode": "gpio", "live": true,
  "host": "raspberrypi", "sensors_ok": 7, "sensors_total": 7 }
```

- `"live": true` und `"mode": "gpio"` → echte Sensoren.
- `"live": false` → **Simulation**, es wird nichts gemessen.
- `"status": "degraded"` → einzelne Sensoren fehlen, siehe `sensors_failed`.
- `"status": "error"` → **kein einziger** Sensor liefert Daten.

### Damit das gar nicht erst passieren kann: ANNA_STRICT

Ist `ANNA_STRICT=1` gesetzt (im mitgelieferten systemd-Dienst standardmaessig),
**startet das Backend gar nicht**, wenn der gpio-Modus verlangt ist, aber kein
einziger Sensor geoeffnet werden konnte. Ein Dienst, der sichtbar nicht startet,
ist deutlich besser als eine Web-App, die ueberzeugend aussieht und in
Wirklichkeit nichts misst.

```bash
sudo systemctl status anna      # zeigt den Startfehler im Klartext
journalctl -u anna -b --no-pager | tail -20
```

---

## Das Prinzip: Rohpegel statt Auswertung

Die normale App zeigt nur das Ergebnis („frei" / „belegt"). Fuer die Fehlersuche
ist das zu wenig, denn zwei voellig verschiedene Fehler sehen dort gleich aus.
Die Diagnose-Seite zeigt deshalb zusaetzlich:

| Spalte | Bedeutung |
|---|---|
| **Rohpegel** | Was elektrisch am Pin anliegt: `HIGH` (3,3 V) oder `LOW` (GND) |
| **Auswertung** | Was die Software daraus macht (beruecksichtigt `pull_up` und `invert`) |
| **Wechsel** | **Wie oft sich der Pegel geaendert hat, seit das Backend laeuft** |

> **Diagnose zeigt ungefiltert, die App geglaettet.** Die Park-App entprellt die
> Sensorwerte (`settings.confirmations`, Standard 2): Ein Zustand wird erst
> uebernommen, wenn er zweimal hintereinander gemessen wurde. Die Diagnose-Seite
> umgeht das bewusst und zeigt den Sensor so, wie er wirklich ist. Weichen beide
> fuer ein bis zwei Sekunden voneinander ab, ist das **kein Fehler**, sondern
> genau diese Glaettung.

Die Spalte **Wechsel** ist der Schluessel. Stelle ein Auto auf ein Feld und nimm
es wieder weg:

- **Wechsel bleibt `0`** → Das Signal kommt **gar nicht am Pi an**. Der Fehler
  liegt in Verdrahtung, Pin-Nummer oder Sensortyp. Die Software ist unschuldig.
- **Wechsel zaehlt hoch, aber „Belegt"/„Frei" ist vertauscht** → Das Signal kommt
  an, nur die **Auswertung** stimmt nicht. Ein Klick auf `invert` genuegt.

---

## Schritt 1 – Laeuft ueberhaupt der GPIO-Modus?

Der Echtbetrieb ist der **Standard**: `python run.py` liest immer die echten
Sensoren. Eine Simulation entsteht nur, wenn jemand sie ausdruecklich anfordert
(`ANNA_BACKEND=simulated`). Trotzdem zuerst pruefen:

```bash
curl http://localhost:5000/api/health
```

- `"live": true` und `"mode":"gpio"` → richtig, echte Sensoren.
- `"live": false` → jemand hat den Simulator gesetzt, es wird nichts gemessen.

Wo die Einstellung herkommen kann:

```bash
systemctl show anna -p Environment      # Dienst-Umgebung pruefen
env | grep ANNA_                        # Umgebung der eigenen Shell
```

`ANNA_BACKEND=simulated` entfernen, dann `sudo systemctl restart anna`.

## Schritt 2 – Melden sich alle Sensoren?

Auf `/diag` muss in der Spalte ganz rechts jedes Feld `ok` sein. Steht dort ein
Fehler wie `GPIO17 is already in use`, konnte der Pin nicht geoeffnet werden.
Moegliche Gruende: ein zweiter ANNA-Prozess laeuft noch (`sudo systemctl stop anna`
vor dem manuellen Start!), oder der Pin ist von einer anderen Funktion belegt.

## Schritt 3 – Bewegt sich der Pegel?

Auto auf ein Feld stellen, wieder wegnehmen, dabei die Spalte **Wechsel**
beobachten (die Seite aktualisiert sich selbst).

- Zaehlt hoch → weiter bei Schritt 5.
- Bleibt `0` → weiter bei Schritt 4.

## Schritt 4 – Den richtigen Pin finden

Auf `/diag` **„Pin-Suche starten"** druecken und **waehrend der 6 Sekunden** das
Auto auf das gesuchte Feld stellen oder wegnehmen. Das Backend beobachtet dabei
alle brauchbaren GPIO-Pins und meldet, welcher sich bewegt hat.

Ohne Browser geht dasselbe am Pi:

```bash
python scripts/gpio_check.py --scan
```

**Ergebnis „ein Pin hat gewechselt":** Das ist der tatsaechlich verdrahtete Pin.
Ueber „zuweisen" direkt uebernehmen (Backend mit `ANNA_DIAG=1` gestartet) oder in
`config/parking_layout.json` eintragen.

**Ergebnis „kein einziger Pin hat sich bewegt":** Dann liegt es an der Hardware:

1. **Gemeinsame Masse?** Sensor-GND und Pi-GND muessen verbunden sein. Ohne
   gemeinsames Bezugspotenzial misst der Pi nichts Sinnvolles.
2. **Reagiert der Sensor ueberhaupt?** Ein **Reed-Kontakt** schaltet nur bei einem
   **Magnetfeld** – ein Modellauto aus Stahl ist *kein* Magnet. Es braucht einen
   kleinen Magneten unter dem Auto (siehe `Architekturkonzept.md`, Abschnitt 4.1).
   Zum Test: Magnet direkt an den Reed halten – wechselt der Pegel jetzt?
3. **Sensor mit Elektronik statt Kontakt?** Dann muss die Beschaltung passen,
   siehe unten „Sensortypen".

## Schritt 5 – Auswertung korrigieren

Wechselt der Pegel, aber „Belegt"/„Frei" ist vertauscht: auf `/diag` beim Feld
`invert an` klicken. Das wird direkt in `config/parking_layout.json` gespeichert
und sofort uebernommen – kein Neustart noetig.

---

## Die haeufigste Falle: BCM oder Header-Pin?

Dieselbe Zahl bedeutet zwei verschiedene Kontakte:

- **BCM** ist die GPIO-Nummer (`GPIO17`). So versteht `gpiozero` alle Zahlen.
- **Board** ist die durchgezaehlte Position auf der 40-poligen Steckerleiste.

Fuer unser Layout ergibt das:

| Feld | Zahl | Als BCM (Software liest) | Als Header-Pin (evtl. verdrahtet) |
|---|---|---|---|
| B1 | 17 | GPIO17 (Header 11) | **3V3-Versorgung – nie ein Signal** |
| B2 | 27 | GPIO27 (Header 13) | ID_SD / EEPROM – reserviert |
| B3 | 22 | GPIO22 (Header 15) | GPIO25 |
| B4 | 23 | GPIO23 (Header 16) | GPIO11 (SPI SCLK) |
| H1 | 24 | GPIO24 (Header 18) | GPIO8 (SPI CE0) |
| H2 | 25 | GPIO25 (Header 22) | **GND – nie ein Signal** |
| H3 | 5 | GPIO5 (Header 29) | GPIO3 (I2C, feste Pull-ups) |

Wurde nach **Header-Nummern** verdrahtet, koennen B1 und H2 grundsaetzlich nie
etwas melden, und die uebrigen Felder liegen auf falschen Pins.

> **Eindeutiges Erkennungsmerkmal.** Rechnet man beide Listen gegeneinander,
> gibt es genau eine Ueberschneidung: Header-Pin 22 ist GPIO25 – und GPIO25 ist
> im Layout das Feld **H2**. Wenn also ein Auto auf **B3** dazu fuehrt, dass in
> der App **H2** als belegt erscheint, ist die Verwechslung damit bewiesen.

> **Vorsicht beim Testen.** Haengt ein Reed-Kontakt tatsaechlich an Header-Pin 17
> (3V3) und schaltet gegen GND, wird beim Auflegen des Autos die
> 3,3-V-Versorgung kurzgeschlossen – der Pi kann abstuerzen oder neu starten.
> Wer das vermutet, misst **vorher stromlos** mit dem Multimeter durch, statt es
> auszuprobieren.

Loesung ohne Umverdrahten – in `config/parking_layout.json`:

```json
"settings": { "numbering": "board" }
```

Danach sind alle `gpio_pin`-Werte als physische Header-Pins zu lesen; die
Software rechnet selbst um. Vollstaendige Tabelle:

```bash
python scripts/gpio_check.py --pinout
```

---

## Sensortypen und Beschaltung

Einstellbar pro Feld in `config/parking_layout.json`:

| Sensor | Verhalten bei Belegung | Einstellung |
|---|---|---|
| Reed-/Magnetschalter gegen GND | zieht den Pin auf **LOW** | `"pull_up": true` (Standard) |
| Induktiver Sensor **NPN** (Open Collector) | zieht auf **LOW** | `"pull_up": true` |
| Induktiver Sensor **PNP** | legt aktiv **HIGH** an | `"pull_up": false` |
| Modul-Platine mit eigenem Ausgang | treibt HIGH **und** LOW | `"pull_up": null` + `"active_state": true/false` |

> **Spannung beachten:** Die GPIO-Eingaenge des Pi vertragen **maximal 3,3 V**.
> Industrielle Naeherungsschalter arbeiten oft mit 12–24 V und geben diese am
> Ausgang aus – ohne Pegelwandler oder Spannungsteiler zerstoert das den Pi.

---

## Status-LEDs anschliessen

Je Parkfeld eine gruene und eine rote LED: **frei = gruen, belegt = rot**
(0 = gruen, 1 = rot). Liefert ein Sensor gar nichts, bleiben **beide LEDs
dunkel** - eine dunkle Stelle ist ehrlicher als ein gruenes Licht, das
faelschlich einen freien Platz verspricht.

Ueblicher Anschluss je LED:

```
GPIO-Pin --- Vorwiderstand (z. B. 330 Ohm) --- LED --- GND
```

### 1. Verdrahten nach Pin-Plan

Der vorgeschlagene Plan steht in `config/parking_layout.json` bei jedem Feld
(`led_green_pin` / `led_red_pin`) und in `docs/Architekturkonzept.md`,
Abschnitt 4.2 - dort mit **beiden** Nummern (BCM und Header-Pin).

### 2. Einschalten - der haeufigste Stolperstein

> **Reagiert keine einzige LED, weder rot noch gruen?** Dann steht mit hoher
> Wahrscheinlichkeit `"leds_enabled": false`. Das Backend steuert dann
> ueberhaupt keine LED an - unabhaengig davon, wie sauber verdrahtet ist.
> Erkennbar an der Startmeldung
> `LED-Ansteuerung ist ABGESCHALTET (settings.leds_enabled = false)`, am roten
> Hinweis oben auf `/diag` und an `"leds_mode": "none"` in `/api/diagnostics`.

Die Ansteuerung ist **absichtlich abgeschaltet**, bis die Verdrahtung steht:
LEDs sind Ausgaenge, und ein falsch zugeordneter Ausgang kann Hardware
beschaedigen. Nach dem Verdrahten in `config/parking_layout.json`:

```json
"settings": { "leds_enabled": true }
```

Dann `sudo systemctl restart anna`. Im Startlog erscheint:

```
INFO anna.leds: LED-Ausgabe bereit: 16 LED(s) an 8 Feld(ern), active_high=True.
INFO anna.api: Hintergrund-Takt fuer die Status-LEDs laeuft (1.5 s).
```

### 3. Der schnellste Test: Neustart

Bei jedem Start leuchten **3 Sekunden lang ALLE LEDs**. Ein Blick aufs Modell
beantwortet damit ohne einen einzigen Befehl die wichtigste Frage:

```bash
sudo systemctl restart anna
```

- **Es leuchtet kurz alles** -> Verdrahtung, Polung und Pin-Zuordnung stimmen.
  Ab hier kann nur noch die Belegungslogik schuld sein.
- **Es leuchtet nichts** -> das Problem liegt in der Hardware oder bei den
  Pin-Nummern. Weiter bei Schritt 4.

(Abschaltbar mit `"led_boot_test_s": 0` in den `settings`.)

### 4. Die echte Verdrahtung finden

Leuchtet beim Start nichts, kennt die Software offenbar die falschen Pins. Ein
Ausgang gibt keine Rueckmeldung - die Software kann also nicht selbst
herausfinden, wo eine LED haengt. Deshalb andersherum: **das Programm schaltet
jeden GPIO einzeln ein und sagt, welcher gerade dran ist.**

```bash
sudo systemctl stop anna
```

```bash
cd ~/anna/backend && source .venv/bin/activate && python scripts/gpio_check.py --find-leds
```

Auf das Modell schauen und notieren, bei welchem Pin welche LED angeht. Danach
die gefundenen Nummern in `config/parking_layout.json` bei
`led_green_pin` / `led_red_pin` eintragen und den Dienst neu starten.
Sensorpins werden dabei ausgelassen (ein Ausgang gegen einen geschlossenen
Reed-Schalter waere ein Kurzschluss).

Nur einen einzelnen Pin pruefen - der einfachste denkbare Hardwaretest:

```bash
python scripts/gpio_check.py --pin 6 --seconds 5
```

### 5. Pruefen - der LED-Selbsttest

Bei Sensoren kann man Pegel beobachten. Bei **Ausgaengen geht das nicht** - man
muss sie einschalten und hinsehen. Dafuer gibt es den Selbsttest.

Auf `/diag` im Abschnitt **LED-Selbsttest**:

| Knopf | Was er beantwortet |
|---|---|
| **Alle an** | Leuchtet ueberhaupt etwas? Nein -> Verdrahtung/Polung, nicht die Software. |
| **Alle gruen** / **Alle rot** | Sitzt jede Farbe am richtigen Pin? |
| **Nur dieses Feld** | Stimmt die Zuordnung Feld ↔ LED? |
| **Alle aus** | Gehen wirklich alle aus? |

Das Muster uebernimmt die LEDs fuer 15 Sekunden, danach laeuft der
Normalbetrieb von selbst weiter. Ohne Browser geht dasselbe am Pi:

```bash
sudo systemctl stop anna
cd ~/anna/backend && source .venv/bin/activate
python scripts/gpio_check.py --led-test
```

Auswertung:

- **Nichts leuchtet** -> LEDs falsch gepolt (Anode/Kathode vertauscht),
  Vorwiderstand fehlt, oder sie haengen gegen 3V3 statt gegen GND. In dem Fall
  `"led_active_high": false` probieren.
- **Ein ganzer Block bleibt dunkel (H1-H4)** -> sehr wahrscheinlich sind SPI
  oder I2C eingeschaltet. Dann haelt der Kerneltreiber diese Pins und die LEDs
  lassen sich nicht oeffnen:

  ```bash
  sudo raspi-config nonint get_spi     # 0 = eingeschaltet -> Problem
  sudo raspi-config nonint get_i2c     # 0 = eingeschaltet -> Problem
  pinctrl get 2,3,7,8,9,10,11          # muss "op" (Ausgang) zeigen, nicht "a0"/"a3"
  ```

  H1 (GPIO7/8), H2 (GPIO9/10) und H3-gruen (GPIO11) liegen auf **SPI0**,
  H4 (GPIO2/3) auf **I2C**. Abhilfe: SPI/I2C in `sudo raspi-config` unter
  Interface Options abschalten, oder diese LEDs auf freie Pins legen.
- **Falsches Feld leuchtet** -> Pin-Zuordnung in `config/parking_layout.json`
  korrigieren (der Test nennt die Pins je Feld).
- **Nur eine Farbe leuchtet** -> die andere LED ist defekt oder verkehrt gepolt.

Im Normalbetrieb zeigt die Spalte **LED** auf `/diag` je Feld zwei Punkte
(gruen/rot) und die zugehoerigen Pins - genau das, was das Backend ansteuert.
Ein Auto auf- und abstellen: der Punkt muss mitwechseln.

> Die LED folgt der **entprellten** Belegung (`confirmations`), die Spalte
> "Auswertung" zeigt den **rohen** Sensorwert. Direkt nach dem Umstellen
> koennen sich beide daher fuer ein bis zwei Messungen unterscheiden - das ist
> beabsichtigt und kein Fehler.

Leuchtet eine LED **genau verkehrt herum** (an statt aus), haengt sie gegen
3V3 oder an einem invertierenden Treiber - dann in den `settings`:

```json
"led_active_high": false
```

Der Hintergrund-Takt sorgt dafuer, dass die LEDs auch stimmen, wenn **niemand
die Web-App geoeffnet hat**. Ohne ihn wuerden sie einfrieren, sobald der letzte
Browser geschlossen wird.

> **Pin-Budget:** 8 Felder x (1 Sensor + 2 LEDs) = 24 Pins. Nutzbar sind
> GPIO2-27, also 26. Frei bleiben nur GPIO14/15 (serielle Konsole). Weitere
> Aktoren brauchen einen Portexpander (MCP23017) oder ein Schieberegister.

---

## Behobener Softwarefehler (Stand dieser Version)

Bis einschliesslich Commit `bbcb1d4` erzeugte `app/main.py` beim blossen
**Importieren** bereits eine komplette Anwendung (`app = create_app()` auf
Modulebene). Da `run.py` das Modul importiert *und* danach regulaer eine App
erzeugt, wurden die GPIO-Pins **zweimal** geoeffnet. Der zweite Versuch scheiterte
mit „GPIO.. is already in use" – und zwar fuer **jeden** Pin.

Weil das Backend einzelne Pin-Fehler bewusst abfaengt (damit ein defekter Sensor
nicht den ganzen Dienst lahmlegt), passierte das **ohne sichtbare Fehlermeldung**:
`read_all()` lieferte gar keine Werte, alle Felder blieben dauerhaft „frei".

Das ist behoben (kein App-Objekt mehr auf Modulebene) und durch zwei Tests
abgesichert. Falls ihr auf einem aelteren Stand testet, ist das die erste
Ursache, die ihr ausschliessen solltet – erkennbar an:

```bash
journalctl -u anna -f | grep "nicht nutzbar"
```
