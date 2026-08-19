#!/usr/bin/env bash
#
# Richtet ANNA auf einem Raspberry Pi als Autostart-Dienst ein.
# Aufruf (aus dem geklonten Repo, auf dem Pi):
#
#     bash backend/deploy/install.sh
#
# Legt ein venv an, installiert die Abhaengigkeiten (inkl. GPIO) und
# registriert den systemd-Dienst 'anna', der beim Booten startet.

set -euo pipefail

# Verzeichnis backend/ (eine Ebene ueber deploy/)
BACKEND_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_USER="$(id -un)"
PYTHON="${PYTHON:-python3}"

echo "== ANNA-Installation =="
echo "Backend-Verzeichnis: $BACKEND_DIR"
echo "Dienst-Benutzer:     $SERVICE_USER"

echo "-- 1/4 GPIO-Bibliotheken aus den Systempaketen --"
# WICHTIG: gpiozero und lgpio kommen von APT, NICHT von PyPI.
#
# Grund: Auf dem Raspberry Pi 5 haengen die Header-Pins am neuen RP1-Chip;
# es gibt kein /dev/gpiochip0 mehr (bei uns ist es gpiochip15). Die
# PyPI-Version von lgpio sucht fest nach gpiochip0 und scheitert mit
# "can not open gpiochip". gpiozero findet dann GAR KEINE Pin-Factory
# (pin_factory=NoneType) - weder Sensoren noch LEDs funktionieren, und zwar
# ohne dass es nach einem Hardwarefehler aussieht.
#
# Die Pakete von Raspberry Pi OS (python3-lgpio, python3-rpi-lgpio) kennen
# die neue Nummerierung. Damit das venv sie sieht, wird es mit
# --system-site-packages angelegt.
sudo apt-get update -qq
sudo apt-get install -y python3-gpiozero python3-lgpio python3-rpi-lgpio

echo "-- 2/4 venv (mit Zugriff auf die Systempakete) --"
"$PYTHON" -m venv --system-site-packages "$BACKEND_DIR/.venv"
"$BACKEND_DIR/.venv/bin/pip" install --upgrade pip
# Nur die reinen Python-Abhaengigkeiten - KEIN gpiozero/lgpio aus PyPI,
# sonst verdeckt es wieder die funktionierenden Systempakete.
"$BACKEND_DIR/.venv/bin/pip" install -r "$BACKEND_DIR/requirements.txt"

echo "-- Kontrolle: laesst sich eine Pin-Factory laden? --"
"$BACKEND_DIR/.venv/bin/python" - <<'PYEOF'
import sys
try:
    from gpiozero import Device
    Device.ensure_pin_factory()
    print(f"   OK - pin_factory = {type(Device.pin_factory).__name__}")
except Exception as exc:
    print(f"   FEHLER: keine Pin-Factory nutzbar ({exc})")
    print("   Ohne sie kann der Pi weder Sensoren lesen noch LEDs schalten.")
    print("   Pruefen: ls /dev/gpiochip*   und   groups | grep gpio")
    sys.exit(1)
PYEOF

echo "-- 3/4 systemd-Dienst erzeugen --"
UNIT="/etc/systemd/system/anna.service"
sudo tee "$UNIT" >/dev/null <<UNITEOF
[Unit]
Description=ANNA Smart-Parking Backend (Web-App + API)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$BACKEND_DIR
Environment=ANNA_BACKEND=gpio
Environment=ANNA_HOST=0.0.0.0
Environment=ANNA_PORT=5000
Environment=ANNA_DIAG=1
ExecStart=$BACKEND_DIR/.venv/bin/python run.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNITEOF

echo "-- 4/4 Dienst aktivieren --"
sudo systemctl daemon-reload
sudo systemctl enable --now anna

echo
echo "Fertig. Die Web-App laeuft auf http://<IP-des-Pi>:5000"
echo "Status:   sudo systemctl status anna"
echo "Logs:     journalctl -u anna -f"
echo "Diagnose: http://<IP-des-Pi>:5000/diag   (Sensoren pruefen)"
echo "Terminal: $BACKEND_DIR/.venv/bin/python scripts/gpio_check.py"
