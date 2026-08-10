#!/usr/bin/env python3
"""Erzeugt die Pin-Uebergabetabelle fuer das Teilprojekt Elektro.

Die Tabelle wird AUS `config/parking_layout.json` erzeugt - damit kann sie nicht
veralten. Die Konfiguration ist die einzige Quelle der Wahrheit; dieses Skript
uebersetzt sie nur in eine lesbare Form (inklusive der physischen Header-Pins,
die in der Konfiguration bewusst nicht doppelt gefuehrt werden).

    python scripts/pinplan.py            # Tabelle auf der Konsole
    python scripts/pinplan.py --write    # schreibt docs/Pinplan.md

`tests/test_pinplan.py` prueft, dass die eingecheckte docs/Pinplan.md dem
aktuellen Stand der Konfiguration entspricht.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import pins as pinmap  # noqa: E402
from app.config import load_layout, layout_path  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "docs" / "Pinplan.md"

STATUS_LABEL = {
    "bestaetigt": "**bestätigt**",
    "vorschlag": "Vorschlag",
}


def _raw_spaces() -> dict[str, dict]:
    """Rohdaten je Feld aus der JSON (fuer die Status-Angaben)."""
    import json
    data = json.loads(layout_path().read_text(encoding="utf-8"))
    return {
        s["id"]: s
        for area in data.get("areas", [])
        for s in area.get("spaces", [])
    }


def _cell(pin: int | None) -> tuple[str, str, str]:
    """(BCM, Header, Hinweis) als Tabellenzellen."""
    if pin is None:
        return ("–", "–", "nicht konfiguriert")
    header = pinmap.BCM_TO_BOARD.get(pin)
    note = pinmap.BCM_NOTES.get(pin, "")
    return (f"GPIO{pin}", str(header) if header else "?", note)


def build() -> str:
    system, settings = load_layout()
    raw = _raw_spaces()
    numbering = settings.get("numbering", "bcm")

    used: dict[int, str] = {}
    lines: list[str] = []
    add = lines.append

    add("# Pin-Belegung – Übergabe an Elektro")
    add("")
    add("> **Diese Datei wird erzeugt.** Quelle ist"
        " `config/parking_layout.json`;")
    add("> erstellt mit `python scripts/pinplan.py --write`. Nicht von Hand"
        " bearbeiten –")
    add("> Änderungen gehören in die JSON, sonst laufen Tabelle und Software"
        " auseinander.")
    add("")
    add("## Die zwei Zählweisen")
    add("")
    add("Jede Zeile nennt **beide** Nummern, weil genau ihre Verwechslung die"
        " häufigste")
    add("Fehlerquelle ist:")
    add("")
    add("- **BCM** ist die GPIO-Nummer, mit der die Software arbeitet"
        " (`GPIO17`).")
    add("- **Header** ist die abgezählte Position auf der 40-poligen"
        " Steckerleiste.")
    add("")
    add(f"Die Konfiguration ist zurzeit auf `numbering: \"{numbering}\"`"
        " gestellt – die Zahlen")
    add(f"in der JSON sind also **{'GPIO-Nummern (BCM)' if numbering == 'bcm' else 'physische Header-Pins'}**.")
    add("")
    add("> Als *physische* Pins wären die Zahlen 17 und 25 die"
        " 3,3-V-Versorgung bzw. Masse –")
    add("> dort kann nie ein Signal anliegen. Wird nach Header-Nummern"
        " verdrahtet, muss in")
    add("> der JSON `\"numbering\": \"board\"` gesetzt werden.")
    add("")

    # --- Sensoren ---------------------------------------------------------
    add("## Sensoren (ein Reed-/Magnetschalter je Parkfeld)")
    add("")
    add("Verdrahtung: **Schalter zwischen GPIO-Pin und GND**, interner Pull-up"
        " aktiv.")
    add("")
    add("| Parkfeld | Areal | Typ | BCM | Header | Status | Hinweis |")
    add("|---|---|---|---|---|---|---|")
    for area in system.areas:
        for s in area.spaces:
            bcm, header, note = _cell(s.gpio_pin)
            status = STATUS_LABEL.get(
                raw.get(s.id, {}).get("sensor_status", "vorschlag"), "Vorschlag")
            if s.gpio_pin is not None:
                used[s.gpio_pin] = f"{s.id} Sensor"
            add(f"| {s.id} | {area.name} | {s.type.value} | {bcm} | {header} "
                f"| {status} | {note} |")
    add("")

    # --- LEDs -------------------------------------------------------------
    add("## Status-LEDs (grün + rot je Parkfeld)")
    add("")
    add("**frei = grün, belegt = rot** (0 = grün, 1 = rot). Liefert ein Sensor"
        " gar nichts,")
    add("bleiben beide LEDs dunkel. Verdrahtung je LED:"
        " **GPIO → Vorwiderstand (z. B. 330 Ω) → LED → GND**.")
    add("")
    add("| Parkfeld | grün BCM | grün Header | rot BCM | rot Header | Status |"
        " Hinweis |")
    add("|---|---|---|---|---|---|---|")
    for area in system.areas:
        for s in area.spaces:
            g_bcm, g_hdr, g_note = _cell(s.led_green_pin)
            r_bcm, r_hdr, r_note = _cell(s.led_red_pin)
            status = STATUS_LABEL.get(
                raw.get(s.id, {}).get("led_status", "vorschlag"), "Vorschlag")
            for pin, role in ((s.led_green_pin, "LED grün"),
                              (s.led_red_pin, "LED rot")):
                if pin is not None:
                    used[pin] = f"{s.id} {role}"
            note = " / ".join(n for n in (g_note, r_note) if n)
            add(f"| {s.id} | {g_bcm} | {g_hdr} | {r_bcm} | {r_hdr} | {status} "
                f"| {note} |")
    add("")
    enabled = settings.get("leds_enabled", False)
    add(f"Die LED-Ansteuerung ist zurzeit **{'eingeschaltet' if enabled else 'abgeschaltet'}**"
        f" (`leds_enabled: {str(enabled).lower()}`).")
    if not enabled:
        add("Sie wird erst aktiv, wenn die Verdrahtung steht und der Wert in der"
            " JSON auf `true`")
        add("gesetzt wird – LEDs sind Ausgänge, ein falsch zugeordneter Ausgang"
            " kann Hardware")
        add("beschädigen.")
    add("")

    # --- Budget -----------------------------------------------------------
    free = sorted(set(range(2, 28)) - set(used))
    add("## Pin-Budget")
    add("")
    add(f"- Belegt: **{len(used)}** GPIOs "
        f"({len(system.space_ids)} Felder × 1 Sensor + 2 LEDs).")
    add("- Nutzbar sind GPIO2–27 (26 Stück); GPIO0/1 sind für das HAT-EEPROM"
        " reserviert.")
    if free:
        frei = ", ".join(f"GPIO{p} (Header {pinmap.BCM_TO_BOARD.get(p)})"
                         for p in free)
        add(f"- Noch frei: **{frei}**.")
    else:
        add("- **Keine freien GPIOs mehr.**")
    add("- GPIO14/15 sind für die serielle Konsole vorgesehen; GPIO2/3 tragen"
        " feste")
    add("  Pull-up-Widerstände (daran hängende LEDs glimmen beim Booten kurz).")
    add("- Weitere Aktoren (z. B. Schranke) benötigen einen Portexpander"
        " (MCP23017) oder")
    add("  ein Schieberegister.")
    add("")
    add("## Änderungen")
    add("")
    add("Pin ändern → in `config/parking_layout.json` eintragen →"
        " `python scripts/pinplan.py --write`")
    add("→ Dienst neu starten (`sudo systemctl restart anna`). Die Zuordnung"
        " lässt sich auch")
    add("im laufenden Betrieb über die Diagnose-Seite `/diag` korrigieren"
        " (`ANNA_DIAG=1`).")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Pin-Uebergabetabelle erzeugen")
    parser.add_argument("--write", action="store_true",
                        help=f"schreibt {TARGET.relative_to(ROOT)}")
    args = parser.parse_args()

    content = build()
    if args.write:
        TARGET.write_text(content, encoding="utf-8")
        print(f"geschrieben: {TARGET}")
    else:
        print(content)


if __name__ == "__main__":
    main()
