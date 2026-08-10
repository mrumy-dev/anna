"""Prueft, dass die Pin-Uebergabe an Elektro aktuell und widerspruchsfrei ist.

Die Pin-Belegung stand bisher an mehreren Stellen (Konfiguration, Architektur-
konzept, Anleitungen) - solche Kopien laufen zwangslaeufig auseinander, und
genau eine falsche Pin-Angabe hat das Projekt bereits Tage gekostet.

Deshalb: `config/parking_layout.json` ist die einzige Quelle, `docs/Pinplan.md`
wird daraus erzeugt, und dieser Test schlaegt fehl, sobald beides nicht mehr
zusammenpasst.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from app import pins as pinmap
from app.config import layout_path, load_layout

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "docs" / "Pinplan.md"


def _pinplan_module():
    spec = importlib.util.spec_from_file_location(
        "pinplan", ROOT / "scripts" / "pinplan.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- Die erzeugte Uebergabetabelle ist aktuell ----------------------------
def test_pinplan_is_up_to_date():
    """docs/Pinplan.md muss dem aktuellen Stand der Konfiguration entsprechen.

    Schlaegt dieser Test fehl, wurde die Konfiguration geaendert, ohne die
    Uebergabe an Elektro neu zu erzeugen:

        python scripts/pinplan.py --write
    """
    assert PLAN.exists(), "docs/Pinplan.md fehlt - mit scripts/pinplan.py erzeugen."
    expected = _pinplan_module().build()
    actual = PLAN.read_text(encoding="utf-8")
    assert actual == expected, (
        "docs/Pinplan.md ist nicht mehr aktuell. Neu erzeugen mit:\n"
        "    python scripts/pinplan.py --write"
    )


def test_pinplan_lists_every_space():
    system, _ = load_layout()
    text = PLAN.read_text(encoding="utf-8")
    for space_id in system.space_ids:
        assert f"| {space_id} |" in text, f"{space_id} fehlt im Pinplan."


def test_pinplan_shows_both_numberings():
    """Jede Zeile muss BCM UND Header nennen - die Verwechslung war der Fehler."""
    system, _ = load_layout()
    text = PLAN.read_text(encoding="utf-8")
    for area in system.areas:
        for space in area.spaces:
            if space.gpio_pin is None:
                continue
            header = pinmap.BCM_TO_BOARD[space.gpio_pin]
            row = next(line for line in text.splitlines()
                       if line.startswith(f"| {space.id} |") and "GPIO" in line)
            assert f"GPIO{space.gpio_pin}" in row
            assert f"| {header} |" in row


# --- Die Konfiguration selbst ist widerspruchsfrei ------------------------
def test_no_pin_is_used_twice():
    system, _ = load_layout()
    used: dict[int, str] = {}
    for area in system.areas:
        for space in area.spaces:
            for pin, role in ((space.gpio_pin, "Sensor"),
                              (space.led_green_pin, "LED gruen"),
                              (space.led_red_pin, "LED rot")):
                if pin is None:
                    continue
                assert pin not in used, (
                    f"GPIO{pin} doppelt vergeben: {used[pin]} und "
                    f"{space.id} ({role})")
                used[pin] = f"{space.id} ({role})"


def test_all_pins_exist_on_the_header():
    system, _ = load_layout()
    for area in system.areas:
        for space in area.spaces:
            for pin in (space.gpio_pin, space.led_green_pin, space.led_red_pin):
                if pin is None:
                    continue
                assert pin in pinmap.BCM_TO_BOARD, f"GPIO{pin} gibt es nicht."
                assert pin not in (0, 1), (
                    f"GPIO{pin} ist fuer das HAT-EEPROM reserviert.")


def test_every_space_has_a_sensor_pin():
    system, _ = load_layout()
    ohne = [s.id for a in system.areas for s in a.spaces if s.gpio_pin is None]
    assert not ohne, f"Diese Felder haben keinen Sensor-Pin: {ohne}"


def test_every_space_has_both_leds():
    system, _ = load_layout()
    unvollstaendig = [
        s.id for a in system.areas for s in a.spaces
        if (s.led_green_pin is None) != (s.led_red_pin is None)
    ]
    assert not unvollstaendig, (
        f"Diese Felder haben nur eine der beiden LEDs: {unvollstaendig}")


# --- Status: was ist bestaetigt, was ist Vorschlag? -----------------------
def test_every_space_declares_its_status():
    """Elektro muss sehen, welche Pins bereits laufen und welche Vorschlag sind."""
    data = json.loads(layout_path().read_text(encoding="utf-8"))
    erlaubt = {"bestaetigt", "vorschlag"}
    for area in data["areas"]:
        for space in area["spaces"]:
            for key in ("sensor_status", "led_status"):
                assert key in space, f"{space['id']}: '{key}' fehlt."
                assert space[key] in erlaubt, (
                    f"{space['id']}.{key} = {space[key]!r} "
                    f"(erlaubt: {sorted(erlaubt)})")


def test_confirmed_sensor_pins_match_the_running_hardware():
    """Die am 07.08.2026 auf dem Pi nachweislich laufenden Pins.

    Startmeldung dort: 'GPIO-Backend bereit: 7 Sensor(en) aktiv'. Aendert
    jemand diese Pins, war das mit hoher Wahrscheinlichkeit ein Versehen -
    die Verdrahtung dazu existiert bereits.
    """
    laufend = {"B1": 17, "B2": 27, "B3": 22, "B4": 23,
               "H1": 24, "H2": 25, "H3": 5}
    system, _ = load_layout()
    for space_id, pin in laufend.items():
        space = system.space(space_id)
        assert space is not None, f"Parkfeld {space_id} fehlt."
        assert space.gpio_pin == pin, (
            f"{space_id} liegt jetzt auf GPIO{space.gpio_pin}, verdrahtet und "
            f"bestaetigt ist aber GPIO{pin}.")


def test_leds_stay_disabled_until_wiring_is_confirmed():
    """Ausgaenge erst treiben, wenn die Zuordnung bestaetigt ist."""
    _, settings = load_layout()
    data = json.loads(layout_path().read_text(encoding="utf-8"))
    alle_bestaetigt = all(
        s.get("led_status") == "bestaetigt"
        for a in data["areas"] for s in a["spaces"]
    )
    if not alle_bestaetigt:
        assert settings.get("leds_enabled") is False, (
            "leds_enabled ist eingeschaltet, obwohl die LED-Verdrahtung noch "
            "nicht bestaetigt ist (led_status = 'vorschlag').")


# --- Das Architekturkonzept darf nicht abweichen --------------------------
KONZEPT = ROOT / "docs" / "Architekturkonzept.md"


def _table_rows(prefix_ids: set[str], columns: int) -> dict[str, list[str]]:
    """Zeilen aus den Markdown-Tabellen des Architekturkonzepts lesen."""
    rows: dict[str, list[str]] = {}
    for line in KONZEPT.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) == columns and cells[0] in prefix_ids:
            rows.setdefault(cells[0], cells)
    return rows


def test_architekturkonzept_sensor_table_matches_config():
    """Die Uebergabetabelle im benoteten Dokument muss zur Konfiguration passen."""
    system, _ = load_layout()
    ids = set(system.space_ids)
    rows = _table_rows(ids, 6)          # Feld | Areal | Typ | BCM | Header | Signal
    assert rows, "Sensor-Tabelle im Architekturkonzept nicht gefunden."

    for area in system.areas:
        for space in area.spaces:
            if space.gpio_pin is None or space.id not in rows:
                continue
            cells = rows[space.id]
            header = pinmap.BCM_TO_BOARD[space.gpio_pin]
            assert cells[3] == str(space.gpio_pin), (
                f"Architekturkonzept nennt fuer {space.id} BCM {cells[3]}, "
                f"konfiguriert ist {space.gpio_pin}.")
            assert cells[4].strip("*") == str(header), (
                f"Architekturkonzept nennt fuer {space.id} Header {cells[4]}, "
                f"richtig waere {header}.")


def test_architekturkonzept_led_table_matches_config():
    system, _ = load_layout()
    ids = set(system.space_ids)
    rows = _table_rows(ids, 3)          # Feld | gruen BCM / Header | rot BCM / Header
    assert rows, "LED-Tabelle im Architekturkonzept nicht gefunden."

    for area in system.areas:
        for space in area.spaces:
            if space.id not in rows or space.led_green_pin is None:
                continue
            cells = rows[space.id]
            erwartet_gruen = (f"{space.led_green_pin} / "
                              f"{pinmap.BCM_TO_BOARD[space.led_green_pin]}")
            erwartet_rot = (f"{space.led_red_pin} / "
                            f"{pinmap.BCM_TO_BOARD[space.led_red_pin]}")
            assert cells[1] == erwartet_gruen, (
                f"{space.id} gruen: Dokument {cells[1]!r}, "
                f"Konfiguration {erwartet_gruen!r}")
            assert cells[2] == erwartet_rot, (
                f"{space.id} rot: Dokument {cells[2]!r}, "
                f"Konfiguration {erwartet_rot!r}")


# --- Budget ----------------------------------------------------------------
def test_pin_budget_is_not_exceeded():
    system, _ = load_layout()
    used = {
        pin
        for a in system.areas for s in a.spaces
        for pin in (s.gpio_pin, s.led_green_pin, s.led_red_pin)
        if pin is not None
    }
    nutzbar = set(range(2, 28))          # GPIO0/1 sind reserviert
    assert used <= nutzbar, f"Ausserhalb des nutzbaren Bereichs: {used - nutzbar}"
    assert len(used) <= len(nutzbar), "Mehr Pins belegt als vorhanden."
