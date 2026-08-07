# ANNA auf dem Raspberry Pi 4 testen – Schritt fuer Schritt

Diese Anleitung bringt die ANNA-Web-App auf einem Raspberry Pi 4 zum Laufen und
zeigt sie am Handy/Laptop an – **ohne jede Hardware**. Es sind **noch keine Pins
oder Sensoren angeschlossen**, und das ist voellig in Ordnung: Wir starten im
**Simulator-Modus**. Die echten Reed-Schalter kommen spaeter (Teil E, Ausblick).

Alles ist zum Kopieren gedacht. Zeilen, die mit `$` oder ohne Zeichen beginnen,
sind Terminal-Befehle. Nach jedem Schritt steht kurz, was passieren soll.

---

## Was du brauchst

- **Raspberry Pi 4** mit installiertem **Raspberry Pi OS (Bookworm)** auf der
  microSD-Karte, Netzteil.
- Der Pi und dein **Handy/Laptop** haengen im **gleichen WLAN** (oder LAN).
- Zugriff auf das Terminal des Pi – entweder:
  - direkt: Monitor + Tastatur am Pi, oder
  - per **SSH** vom Laptop (siehe Teil A, Schritt 3).
- **Keine** Sensoren, keine Verkabelung noetig.

> Falls auf der SD-Karte noch kein Betriebssystem ist: mit dem Programm
> **Raspberry Pi Imager** (auf einem PC) "Raspberry Pi OS (64-bit)" auf die Karte
> schreiben, WLAN und SSH dabei gleich mit aktivieren, Karte in den Pi stecken.

---

## Teil A – Pi startklar machen

### A1. Pi einschalten
SD-Karte einstecken, Netzteil anschliessen. Der Pi bootet bis zum Desktop bzw.
zur Terminal-Anmeldung.

### A2. Terminal oeffnen
Am Pi-Desktop oben das schwarze Terminal-Symbol anklicken. Du landest in einer
Eingabezeile wie `pi@raspberrypi:~ $`.

### A3. (Optional) Vom Laptop per SSH verbinden
Bequemer als Monitor+Tastatur. Am Pi einmalig die IP herausfinden:

```
hostname -I
```

Gibt z. B. `192.168.1.42` aus (die **erste** Zahlenfolge ist die IP). Am Laptop:

```
ssh pi@192.168.1.42
```

Passwort eingeben – du bist im Pi-Terminal. (Falls SSH nicht aktiv ist: am Pi
`sudo raspi-config` -> Interface Options -> SSH -> aktivieren.)

### A4. Internet pruefen und System aktualisieren

```
ping -c 3 github.com
sudo apt update
```

`ping` sollte Antworten zeigen (Internet vorhanden). `apt update` laedt die
Paketlisten.

---

## Teil B – ANNA installieren (Simulator, ohne Hardware)

### B1. Werkzeuge installieren

```
sudo apt install -y git python3-venv
```

Installiert `git` (Code holen) und `python3-venv` (isolierte Python-Umgebung).

### B2. Den Code holen

```
cd ~
git clone https://github.com/farisridzal-hftm/anna.git
cd anna/backend
```

Legt den Ordner `~/anna` an. Wir arbeiten ab jetzt im Ordner `~/anna/backend`.

### B3. Python-Umgebung und Abhaengigkeiten

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- `python3 -m venv .venv` erstellt die Umgebung.
- `source .venv/bin/activate` schaltet sie ein (die Zeile beginnt danach mit
  `(.venv)`).
- `pip install ...` installiert Flask und den Server. **Wichtig:** Das ist die
  **Basis** ohne Sensor-Pakete – genau richtig, solange keine Hardware dran ist.

### B4. Starten

```
python run.py
```

### B5. Startmeldung verstehen
Es sollte in etwa erscheinen:

```
INFO anna: ANNA startet: backend=simulated, areas=2, spaces=7
INFO anna: Web-App erreichbar unter http://0.0.0.0:5000
INFO anna: Server: werkzeug (threaded)
```

`backend=simulated` = Simulator-Modus (keine Hardware noetig). Der Server laeuft
jetzt. **Lass dieses Terminal offen.**

---

## Teil C – Web-App oeffnen und testen

### C1. Die IP des Pi herausfinden
In einem **zweiten** Terminal (oder kurz mit `hostname -I`, falls du sie nicht
mehr weisst):

```
hostname -I
```

Merke dir die erste Adresse, z. B. `192.168.1.42`.

### C2. Am Handy/Laptop oeffnen
Im Browser (gleiches WLAN!) aufrufen:

```
http://192.168.1.42:5000
```

(Deine IP statt `192.168.1.42`.) Die ANNA-App erscheint mit den zwei Arealen
*Blumenstrasse* und *Hauptstrasse*.

### C3. Schnelltest direkt am Pi (optional)
Falls die App am Handy nicht auftaucht, erst am Pi pruefen, ob das Backend
antwortet:

```
curl http://localhost:5000/api/health
```

Erwartet: `{"status":"ok","mode":"simulated"}`.

### C4. Was du ausprobieren kannst
Weil kein Sensor angeschlossen ist, steuerst du die Belegung im **Simulator**
selbst:

- Auf ein **Parkfeld tippen** -> es wechselt zwischen **Frei** (gruen) und
  **Belegt** (rot). Die Anzeige aktualisiert sich live.
- **Filter** oben (Alle / Normal / Familie / Frauen / Behinderte) antippen.
- Beim **`+`** an einem freien Feld -> **Reservierung** (Feld wird gestrichelt,
  "Reserviert"), **`x`** hebt sie wieder auf.
- Alle Felder eines Areals belegen -> der **"voll"-Hinweis** erscheint und
  verweist auf das andere Areal.
- **"Route"** oeffnet Google Maps. Unten die **Auslastung**.

### C5. Server beenden
Im ersten Terminal **Ctrl + C** druecken. Der Server stoppt.

---

## Teil D – Autostart einrichten (optional, fuer die Vorfuehrung)

Damit die App **automatisch beim Einschalten** des Pi startet – weiterhin im
Simulator-Modus, ohne Hardware. Diesen Block **einmal** komplett ins Terminal
kopieren (er traegt Benutzer und Pfad automatisch ein):

```
sudo tee /etc/systemd/system/anna.service >/dev/null <<EOF
[Unit]
Description=ANNA Smart-Parking (Simulator)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/anna/backend
Environment=ANNA_BACKEND=simulated
Environment=ANNA_HOST=0.0.0.0
Environment=ANNA_PORT=5000
ExecStart=$HOME/anna/backend/.venv/bin/python run.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now anna
```

Verwalten:

```
sudo systemctl status anna     # laeuft es?
journalctl -u anna -f          # Live-Logs (mit Ctrl+C verlassen)
sudo systemctl restart anna    # neu starten
sudo systemctl stop anna       # anhalten
sudo systemctl disable anna    # Autostart wieder abschalten
```

Ab jetzt ist die App nach jedem Booten unter `http://<Pi-IP>:5000` erreichbar.

---

## Teil E – Spaeter: echte Sensoren anschliessen (Ausblick)

**Erst relevant, wenn das Team die Reed-Schalter verdrahtet hat.** Kurzfassung:

1. Reed-Schalter je Parkfeld zwischen dem passenden **GPIO-Pin und GND**
   anschliessen. Welches Feld an welchem Pin haengt, steht in
   `config/parking_layout.json` (B1=17, B2=27, B3=22, B4=23, H1=24, H2=25, H3=5;
   von Elektro bestaetigen lassen).
2. Sensor-Pakete installieren und im GPIO-Modus starten:
   ```
   cd ~/anna/backend
   source .venv/bin/activate
   pip install -r requirements-pi.txt
   ANNA_BACKEND=gpio python run.py
   ```
   Startmeldung dann `backend=gpio` und `GPIO-Backend bereit: N Sensor(en) aktiv`.
3. Fuer den Autostart im echten Betrieb gibt es ein fertiges Skript, das alles
   (venv, Pakete, systemd-Dienst mit `ANNA_BACKEND=gpio`) einrichtet:
   ```
   bash ~/anna/backend/deploy/install.sh
   ```
4. Reagiert ein Feld verkehrt (belegt/frei vertauscht)? In
   `config/parking_layout.json` beim Feld `"invert": true` setzen, dann Dienst
   neu starten.

> Hinweis: Ein Reed-Schalter reagiert auf ein **Magnetfeld**, nicht auf blankes
> Metall – dafuer kommt ein kleiner Magnet unter jedes Modellauto (Details im
> `docs/Architekturkonzept.md`, Abschnitt 4.1).

---

## Teil F – Troubleshooting

- **Handy findet die Seite nicht:** gleiches WLAN wie der Pi? IP mit
  `hostname -I` gegenpruefen. Erst am Pi testen:
  `curl http://localhost:5000/api/health`. Antwortet das, liegt es am Netzwerk
  (WLAN-Trennung/Gastnetz/Firewall), nicht an ANNA.
- **`Address already in use` / Port 5000 belegt:** anderen Port nehmen, z. B.
  `ANNA_PORT=8080 python run.py`, dann `http://<Pi-IP>:8080` oeffnen.
- **`(.venv)` fehlt vor der Eingabezeile:** Umgebung nicht aktiv –
  `source ~/anna/backend/.venv/bin/activate` erneut ausfuehren.
- **`pip install` schlaegt fehl:** Internet pruefen (`ping -c 3 github.com`),
  danach `pip install --upgrade pip` und den Install-Befehl wiederholen.
- **Dienst-Logs ansehen (bei Autostart):** `journalctl -u anna -f`.

---

## Anhang – Befehle auf einen Blick

```
# Installieren (einmalig)
cd ~ && git clone https://github.com/farisridzal-hftm/anna.git
cd anna/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Starten (Simulator)
python run.py                     # -> http://<Pi-IP>:5000 ; beenden mit Ctrl+C

# IP des Pi
hostname -I

# Backend-Selbsttest
curl http://localhost:5000/api/health

# Autostart-Dienst verwalten
sudo systemctl status anna
journalctl -u anna -f
sudo systemctl restart anna
```
