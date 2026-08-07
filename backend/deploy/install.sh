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

echo "-- 1/3 venv + Abhaengigkeiten --"
"$PYTHON" -m venv "$BACKEND_DIR/.venv"
"$BACKEND_DIR/.venv/bin/pip" install --upgrade pip
"$BACKEND_DIR/.venv/bin/pip" install -r "$BACKEND_DIR/requirements.txt"
"$BACKEND_DIR/.venv/bin/pip" install -r "$BACKEND_DIR/requirements-pi.txt"

echo "-- 2/3 systemd-Dienst erzeugen --"
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
Environment=ANNA_STRICT=1
Environment=ANNA_DIAG=1
ExecStart=$BACKEND_DIR/.venv/bin/python run.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNITEOF

echo "-- 3/3 Dienst aktivieren --"
sudo systemctl daemon-reload
sudo systemctl enable --now anna

echo
echo "Fertig. Die Web-App laeuft auf http://<IP-des-Pi>:5000"
echo "Status:   sudo systemctl status anna"
echo "Logs:     journalctl -u anna -f"
echo "Diagnose: http://<IP-des-Pi>:5000/diag   (Sensoren pruefen)"
echo "Terminal: $BACKEND_DIR/.venv/bin/python scripts/gpio_check.py"
