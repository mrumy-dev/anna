#!/usr/bin/env bash
#
# Sammelt in EINEM Durchlauf alles, was zur Fehlersuche noetig ist.
#
#     bash ~/anna/backend/deploy/../scripts/diagnose.sh
#
# Die komplette Ausgabe kopieren und zurueckschicken. Es werden nur
# Zustandsinformationen gelesen - nichts veraendert, nichts geschaltet.

BACKEND_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${ANNA_PORT:-5000}"
BASE="http://localhost:${PORT}"

echo "==================== ANNA DIAGNOSE ===================="
date
echo

echo "---------- 1. CODE-STAND ----------"
git -C "$BACKEND_DIR/.." log --oneline -3 2>&1
echo "Aenderungen im Arbeitsbaum:"
git -C "$BACKEND_DIR/.." status --short 2>&1 | head -20
echo

echo "---------- 2. DIENST ----------"
if command -v systemctl >/dev/null 2>&1; then
  echo "Status: $(systemctl is-active anna 2>&1)"
  systemctl show anna -p Environment -p ExecStart -p WorkingDirectory -p MainPID 2>&1
else
  echo "(systemctl nicht verfuegbar - kein systemd-System)"
fi
echo

echo "---------- 3. LAUFENDE PROZESSE ----------"
pgrep -af "run.py|waitress|flask" 2>&1 || echo "(kein ANNA-Prozess gefunden)"
echo "Port ${PORT}:"
if command -v ss >/dev/null 2>&1; then
  sudo ss -lptn "sport = :${PORT}" 2>/dev/null || ss -lptn "sport = :${PORT}" 2>&1
else
  echo "(ss nicht verfuegbar)"
fi
echo

echo "---------- 4. KONFIGURATION ----------"
if [ -f "$BACKEND_DIR/config/parking_layout.json" ]; then
  python3 - "$BACKEND_DIR/config/parking_layout.json" <<'PY' 2>&1
import json, sys
d = json.load(open(sys.argv[1]))
s = d["settings"]
for k in ("leds_enabled", "led_active_high", "led_boot_test_s",
          "numbering", "confirmations", "poll_interval_ms"):
    print(f"  {k}: {s.get(k)}")
print("  Felder:")
for a in d["areas"]:
    for sp in a["spaces"]:
        print(f"    {sp['id']}: sensor=GPIO{sp.get('gpio_pin')} "
              f"gruen=GPIO{sp.get('led_green_pin')} rot=GPIO{sp.get('led_red_pin')}")
PY
else
  echo "  parking_layout.json NICHT GEFUNDEN unter $BACKEND_DIR/config/"
fi
echo

echo "---------- 5. /api/health ----------"
curl -s --max-time 5 "${BASE}/api/health" 2>&1 || echo "(keine Antwort - laeuft das Backend?)"
echo; echo

echo "---------- 6. LED- UND SENSORZUSTAND ----------"
curl -s --max-time 5 "${BASE}/api/diagnostics" 2>/dev/null | python3 - <<'PY' 2>&1 || echo "(keine Antwort)"
import json, sys
try:
    d = json.load(sys.stdin)
except Exception as exc:
    print("  konnte Antwort nicht lesen:", exc); raise SystemExit
print(f"  mode={d.get('mode')}  leds_mode={d.get('leds_mode')}  "
      f"leds_enabled={d.get('leds_enabled')}")
print(f"  leds_reason={d.get('leds_reason')}")
print(f"  led_test={d.get('led_test')}")
print(f"  layout_file={d.get('layout_file')}")
print(f"  {'Feld':<5}{'Sensor':<9}{'roh':<6}{'belegt':<8}{'LED gruen':<11}"
      f"{'LED rot':<9}{'Fehler'}")
for r in d.get("spaces", []):
    led = r.get("led") or {}
    print(f"  {r['space_id']:<5}GPIO{str(r.get('pin')):<5}"
          f"{str(r.get('raw')):<6}{str(r.get('occupied')):<8}"
          f"{str(led.get('green')):<11}{str(led.get('red')):<9}"
          f"{led.get('error') or r.get('error') or ''}")
PY
echo

echo "---------- 7. STARTLOG ----------"
journalctl -u anna -b --no-pager 2>/dev/null | grep -iE \
  "ANNA startet|Sensor\(en\) aktiv|LED-Ausgabe|nicht nutzbar|ABGESCHALTET|Hintergrund-Takt|Traceback|Error" \
  | tail -25 || echo "(kein Journal - laeuft ANNA als Dienst?)"
echo

echo "---------- 8. GPIO-BELEGUNG ----------"
echo "SPI aktiv (0 = ja, das waere ein Problem fuer H1-H3):"
sudo raspi-config nonint get_spi 2>/dev/null || echo "  (raspi-config nicht verfuegbar)"
echo "I2C aktiv (0 = ja, das waere ein Problem fuer H4):"
sudo raspi-config nonint get_i2c 2>/dev/null || echo "  (raspi-config nicht verfuegbar)"
echo "Zustand der LED-Pins (op = Ausgang, gut; a0/a3 = von SPI/I2C belegt):"
pinctrl get 2,3,6,7,8,9,10,11,12,13,16,18,19,20,21,26 2>/dev/null \
  || echo "  (pinctrl nicht verfuegbar)"
echo

echo "---------- 9. PYTHON-UMGEBUNG ----------"
"$BACKEND_DIR/.venv/bin/python" -c "
import gpiozero, sys
from gpiozero import Device
print('  gpiozero', gpiozero.__version__, '| python', sys.version.split()[0])
try:
    print('  pin_factory:', type(Device.pin_factory).__name__)
except Exception as e:
    print('  pin_factory FEHLER:', e)
" 2>&1 || echo "  (venv oder gpiozero fehlt)"

echo
echo "==================== ENDE ===================="
echo "Bitte die KOMPLETTE Ausgabe zurueckschicken."
