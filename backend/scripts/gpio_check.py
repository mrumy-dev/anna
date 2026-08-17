#!/usr/bin/env python3
"""Sensor-Diagnose fuer die Kommandozeile (Raspberry Pi).

Prueft die Verdrahtung unabhaengig vom Webserver. Aufruf aus dem Ordner
backend/ mit aktiviertem venv:

    python scripts/gpio_check.py            # Live-Tabelle der konfigurierten Felder
    python scripts/gpio_check.py --scan     # ALLE brauchbaren Pins beobachten
    python scripts/gpio_check.py --pinout   # Header-Tabelle BCM <-> physischer Pin

Leitfrage: Aendert sich der Rohpegel, wenn ein Auto auf das Feld gestellt wird?
  - Spalte "Wechsel" bleibt 0  -> Signal kommt nicht an (Verdrahtung/Pin/Sensor)
  - Wechsel zaehlt, Auswertung verkehrt -> nur 'invert' in der Konfiguration drehen
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Projektwurzel in den Suchpfad, damit 'app' importierbar ist.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import pins as pinmap  # noqa: E402
from app.config import load_layout  # noqa: E402
from app.actuators.base import test_pattern as base_test_pattern  # noqa: E402
from app.sensors import wiring_specs  # noqa: E402


def print_pinout() -> None:
    print("BCM  Header  Hinweis")
    print("---  ------  ------------------------------------------------")
    for bcm, board in sorted(pinmap.BCM_TO_BOARD.items()):
        note = pinmap.BCM_NOTES.get(bcm, "")
        safe = "" if bcm in pinmap.SAFE_BCM_PINS else "  (fuer Sensoren meiden)"
        print(f"{bcm:>3}  {board:>6}  {note}{safe}")
    print("\nNicht aufgefuehrte Header-Pins sind 3V3, 5V oder GND.")


def live_table(interval: float) -> None:
    system, settings = load_layout()
    specs = wiring_specs(system)
    numbering = settings.get("numbering", "bcm")

    try:
        from app.sensors.gpio import GpioSensorBackend
    except ImportError as exc:  # pragma: no cover - nur ohne gpiozero
        print(f"gpiozero fehlt: {exc}")
        print("Installieren mit: pip install -r requirements-pi.txt")
        return

    print(f"Layout-Nummerierung: {numbering}")
    for spec in specs:
        if spec["pin"] is None:
            print(f"  {spec['id']}: kein Pin konfiguriert")
            continue
        hint = pinmap.board_confusion_hint(spec.get("configured_pin"))
        print(f"  {spec['id']}: konfiguriert {spec.get('configured_pin')} "
              f"-> {pinmap.describe_pin(spec['pin'])}")
        if hint:
            print(f"      {hint}")

    backend = GpioSensorBackend(specs, bounce_time=settings.get("bounce_time_s", 0.05))
    print("\nJetzt ein Auto auf ein Feld stellen und wieder wegnehmen.")
    print("Beenden mit Ctrl+C.\n")

    try:
        while True:
            rows = backend.diagnostics()
            print("\033[H\033[J", end="")  # Bildschirm loeschen
            print(f"{'Feld':<6}{'Pin':<10}{'Roh':<8}{'Auswertung':<12}"
                  f"{'Wechsel':<9}{'Status'}")
            print("-" * 64)
            for row in rows:
                pin = f"GPIO{row['pin']}" if row["pin"] is not None else "-"
                raw = {1: "HIGH", 0: "LOW"}.get(row["raw"], "-")
                verdict = "BELEGT" if row["occupied"] else "frei"
                status = "ok" if row["ok"] else f"FEHLER: {row['error']}"
                print(f"{row['space_id']:<6}{pin:<10}{raw:<8}{verdict:<12}"
                      f"{row['changes']:<9}{status}")
            print("\n(Wechsel bleibt 0 -> Signal kommt nicht am Pi an)")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        backend.close()


def scan(seconds: float) -> None:
    system, settings = load_layout()
    try:
        from app.sensors.gpio import GpioSensorBackend
    except ImportError as exc:  # pragma: no cover
        print(f"gpiozero fehlt: {exc}")
        return

    backend = GpioSensorBackend(wiring_specs(system),
                                bounce_time=settings.get("bounce_time_s", 0.05))
    print(f"Beobachte alle brauchbaren GPIO-Pins fuer {seconds:.0f} s.")
    print("JETZT ein Auto auf das gesuchte Feld stellen oder wegnehmen ...\n")
    try:
        rows = backend.scan(seconds)
    finally:
        backend.close()

    moved = [r for r in rows if r["changes"]]
    if not moved:
        print("Kein Pin hat sich bewegt.")
        print("-> Verdrahtung, gemeinsame Masse (GND) oder Sensortyp pruefen.")
        return

    print(f"{'Pin':<10}{'Header':<9}{'Wechsel':<9}{'Von->Nach':<12}{'Feld'}")
    print("-" * 52)
    for row in moved:
        print(f"GPIO{row['pin']:<6}{row['board_pin'] or '?':<9}{row['changes']:<9}"
              f"{row['start']}->{row['end']:<9}{row['assigned_to'] or '(frei)'}")
    print("\nDiesen Pin in config/parking_layout.json beim passenden Feld eintragen.")


def led_test(seconds: float) -> None:
    """Treibt nacheinander Testmuster auf die LEDs - Selbsttest fuer Ausgaenge.

    Laeuft unabhaengig vom Webserver. WICHTIG: vorher `sudo systemctl stop anna`,
    sonst haelt der Dienst die Pins.
    """
    system, settings = load_layout()
    from app.actuators import led_specs

    specs = led_specs(system)
    verdrahtet = [s for s in specs
                  if s["green_pin"] is not None or s["red_pin"] is not None]
    if not verdrahtet:
        print("Kein Parkfeld hat LED-Pins konfiguriert.")
        return

    try:
        from app.actuators.gpio import GpioLedBackend
    except ImportError as exc:  # pragma: no cover
        print(f"gpiozero fehlt: {exc}")
        return

    active_high = bool(settings.get("led_active_high", True))
    print(f"LED-Selbsttest, active_high={active_high}. Beenden mit Ctrl+C.\n")
    if not settings.get("leds_enabled", False):
        print("Hinweis: settings.leds_enabled ist false - im NORMALBETRIEB wird")
        print("         damit keine LED geschaltet. Dieser Test treibt sie")
        print("         trotzdem, damit die Verdrahtung pruefbar ist.\n")

    leds = GpioLedBackend(specs, active_high=active_high)
    ids = [s["id"] for s in specs]
    try:
        for mode, text in (("beide", "ALLE LEDs an - leuchtet ueberhaupt etwas?"),
                           ("gruen", "alle GRUENEN an"),
                           ("rot", "alle ROTEN an"),
                           ("aus", "alles aus")):
            print(f"  {text}")
            leds.set_override(base_test_pattern(ids, mode), seconds=seconds,
                              label=mode)
            time.sleep(seconds)

        print("\n  Jetzt Feld fuer Feld - stimmt die Zuordnung?")
        for space_id in ids:
            spec = next(s for s in specs if s["id"] == space_id)
            print(f"    {space_id}  (gruen GPIO{spec['green_pin']}, "
                  f"rot GPIO{spec['red_pin']})")
            leds.set_override(base_test_pattern(ids, "feld", space_id),
                              seconds=seconds, label=space_id)
            time.sleep(seconds)
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
    finally:
        leds.close()
        print("\nLEDs ausgeschaltet.")
    print("Leuchtete nichts -> Verdrahtung/Polung pruefen, oder "
          "led_active_high umstellen.")
    print("Leuchtete das falsche Feld -> Pin-Zuordnung in "
          "config/parking_layout.json korrigieren.")


def find_leds(seconds: float) -> None:
    """Treibt JEDEN brauchbaren GPIO nacheinander an und sagt, welcher dran ist.

    Das ist das Gegenstueck zur Pin-Suche bei den Sensoren. Ein Ausgang gibt
    keine Rueckmeldung - die Software kann also nicht erkennen, wo eine LED
    haengt. Also andersherum: Das Programm schaltet Pin fuer Pin ein und nennt
    ihn; wer aufs Modell schaut, sieht welche LED aufleuchtet und notiert es.

    Damit findet man die echte Verdrahtung, ohne den Schaltplan zu kennen.

    Sensorpins werden ausgelassen: Ein Ausgang gegen einen geschlossenen
    Reed-Schalter waere ein Kurzschluss gegen GND.
    """
    system, settings = load_layout()

    try:
        from gpiozero import LED
    except ImportError as exc:  # pragma: no cover
        print(f"gpiozero fehlt: {exc}")
        print("Installieren mit: pip install -r requirements-pi.txt")
        return

    sensorpins = {s.gpio_pin for a in system.areas for s in a.spaces
                  if s.gpio_pin is not None}
    geplant = {}
    for a in system.areas:
        for s in a.spaces:
            if s.led_green_pin is not None:
                geplant[s.led_green_pin] = f"{s.id} gruen"
            if s.led_red_pin is not None:
                geplant[s.led_red_pin] = f"{s.id} rot"

    kandidaten = [p for p in pinmap.ALL_BCM_PINS
                  if p not in sensorpins and p not in (0, 1)]

    print("LED-Suche: jeder Pin wird einzeln eingeschaltet.")
    print(f"{len(kandidaten)} Pins x {seconds:.1f} s = rund "
          f"{len(kandidaten) * seconds / 60:.0f} Minuten.")
    print("Schau auf das Modell und notiere, welche LED bei welchem Pin angeht.")
    print("Sensorpins werden ausgelassen. Abbrechen mit Ctrl+C.\n")
    print(f"{'BCM':<8}{'Header':<9}{'geplant fuer':<16}{'Hinweis'}")
    print("-" * 60)

    gefunden: list[str] = []
    try:
        for pin in kandidaten:
            header = pinmap.BCM_TO_BOARD.get(pin, "?")
            plan = geplant.get(pin, "-")
            note = pinmap.BCM_NOTES.get(pin, "")
            print(f"{pin:<8}{header:<9}{plan:<16}{note}", flush=True)
            try:
                led = LED(pin, initial_value=True)
            except Exception as exc:  # noqa: BLE001
                print(f"         -> nicht nutzbar: {exc}")
                continue
            try:
                time.sleep(seconds)
            finally:
                led.off()
                led.close()
    except KeyboardInterrupt:
        print("\nAbgebrochen.")

    print("\nFertig. Trage die gefundenen Pins in config/parking_layout.json ein")
    print("(led_green_pin / led_red_pin je Parkfeld) und starte den Dienst neu:")
    print("  sudo systemctl restart anna")


def drive_pin(pin: int, seconds: float) -> None:
    """Schaltet EINEN Pin ein - der einfachste denkbare Hardwaretest."""
    try:
        from gpiozero import LED
    except ImportError as exc:  # pragma: no cover
        print(f"gpiozero fehlt: {exc}")
        return

    system, _ = load_layout()
    sensorpins = {s.gpio_pin for a in system.areas for s in a.spaces
                  if s.gpio_pin is not None}
    if pin in sensorpins:
        print(f"GPIO{pin} ist ein SENSOR-Pin. Als Ausgang zu treiben waere ein "
              f"Kurzschluss, sobald der Schalter schliesst. Abgebrochen.")
        return

    print(f"GPIO{pin} ({pinmap.describe_pin(pin)}) wird fuer {seconds:.0f} s "
          f"eingeschaltet ...")
    led = LED(pin, initial_value=True)
    try:
        time.sleep(seconds)
    except KeyboardInterrupt:
        pass
    finally:
        led.off()
        led.close()
    print("Aus. Hat eine LED geleuchtet? Dann haengt sie an diesem Pin.")


def main() -> None:
    parser = argparse.ArgumentParser(description="ANNA Sensor-Diagnose")
    parser.add_argument("--scan", action="store_true",
                        help="alle brauchbaren Pins beobachten (Pin-Suche)")
    parser.add_argument("--pinout", action="store_true",
                        help="Header-Tabelle BCM <-> physischer Pin ausgeben")
    parser.add_argument("--led-test", action="store_true",
                        help="Testmuster auf die Status-LEDs treiben")
    parser.add_argument("--find-leds", action="store_true",
                        help="jeden GPIO einzeln einschalten - findet die "
                             "tatsaechliche LED-Verdrahtung")
    parser.add_argument("--pin", type=int, default=None,
                        help="genau diesen GPIO einschalten (einfachster Test)")
    parser.add_argument("--seconds", type=float, default=8.0,
                        help="Dauer der Pin-Suche (Standard 8)")
    parser.add_argument("--interval", type=float, default=0.5,
                        help="Aktualisierung der Live-Tabelle (Standard 0.5 s)")
    args = parser.parse_args()

    if args.pinout:
        print_pinout()
    elif args.pin is not None:
        drive_pin(args.pin, args.seconds)
    elif args.find_leds:
        find_leds(max(0.5, min(10.0, args.interval * 3)))
    elif args.led_test:
        led_test(max(0.5, min(10.0, args.interval * 4)))
    elif args.scan:
        scan(args.seconds)
    else:
        live_table(args.interval)


if __name__ == "__main__":
    main()
