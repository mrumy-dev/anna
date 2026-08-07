"""Konfiguration laden und ein ParkingSystem aufbauen."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from . import pins as pinmap
from .models import Area, ParkingSystem, Space, SpaceType

log = logging.getLogger("anna.config")

# Projektwurzel (eine Ebene ueber dem app-Paket)
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LAYOUT = ROOT / "config" / "parking_layout.json"


def layout_path(path: str | Path | None = None) -> Path:
    """Der tatsaechlich verwendete Pfad der Layout-Datei."""
    return Path(path or os.environ.get("ANNA_LAYOUT", DEFAULT_LAYOUT))


def _parse_pull_up(value) -> bool | None:
    """Akzeptiert true/false/null bzw. "up"/"down"/"none"."""
    if value is None or value is True or value is False:
        return value
    text = str(value).strip().lower()
    if text in {"up", "pullup", "pull_up", "true"}:
        return True
    if text in {"down", "pulldown", "pull_down", "false"}:
        return False
    if text in {"none", "off", "extern", "external"}:
        return None
    raise ValueError(f"Unbrauchbarer Wert fuer 'pull_up': {value!r}")


def load_layout(path: str | Path | None = None) -> tuple[ParkingSystem, dict]:
    """Liest die Layout-JSON und gibt (ParkingSystem, settings) zurueck.

    Wirft FileNotFoundError bzw. ValueError mit klarer Meldung, wenn die
    Konfiguration fehlt oder unbrauchbar ist. Pin-Nummern werden gemaess
    settings.numbering ("bcm" oder "board") in BCM-Nummern aufgeloest.
    """
    path = layout_path(path)
    if not path.exists():
        raise FileNotFoundError(f"Layout-Datei nicht gefunden: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))

    settings = dict(data.get("settings", {}))
    default_invert = settings.get("default_invert", False)
    default_pull_up = _parse_pull_up(settings.get("default_pull_up", True))
    numbering = str(settings.get("numbering", "bcm")).strip().lower()
    if numbering not in {"bcm", "board"}:
        raise ValueError(
            f"settings.numbering muss 'bcm' oder 'board' sein, nicht {numbering!r}."
        )
    settings["numbering"] = numbering

    if not data.get("areas"):
        raise ValueError(f"Layout {path} enthaelt keine Areale.")

    areas: list[Area] = []
    seen_ids: set[str] = set()
    seen_pins: dict[int, str] = {}

    for a in data["areas"]:
        spaces: list[Space] = []
        for s in a["spaces"]:
            space_id = s["id"]
            if space_id in seen_ids:
                raise ValueError(
                    f"Doppelte Parkfeld-ID '{space_id}' im Layout {path}.")
            seen_ids.add(space_id)

            configured = s.get("gpio_pin")
            bcm: int | None = None
            if configured is not None:
                try:
                    bcm = pinmap.resolve_pin(int(configured), numbering)
                except pinmap.PinError as exc:
                    raise ValueError(f"Parkfeld {space_id}: {exc}") from exc

                if bcm in seen_pins:
                    log.warning("GPIO%s ist doppelt vergeben (%s und %s).",
                                bcm, seen_pins[bcm], space_id)
                else:
                    seen_pins[bcm] = space_id

                note = pinmap.pin_warning(bcm)
                if note:
                    log.warning("Parkfeld %s nutzt %s.", space_id,
                                pinmap.describe_pin(bcm))

            spaces.append(Space(
                id=space_id,
                type=SpaceType(s.get("type", "normal")),
                gpio_pin=bcm,
                configured_pin=configured,
                invert=s.get("invert", default_invert),
                pull_up=_parse_pull_up(s.get("pull_up", default_pull_up)),
                active_state=s.get("active_state"),
            ))
        areas.append(
            Area(
                id=a["id"],
                name=a["name"],
                maps_url=a.get("maps_url", ""),
                spaces=spaces,
            )
        )

    return ParkingSystem(areas), settings


def get_settings() -> dict:
    """Bequemer Zugriff nur auf die Settings (z. B. fuer das Frontend)."""
    _, settings = load_layout()
    return settings


def update_space_wiring(space_id: str, *, gpio_pin: int | None = None,
                        invert: bool | None = None,
                        pull_up: bool | None = None,
                        path: str | Path | None = None) -> dict:
    """Schreibt die Sensor-Zuordnung eines Feldes zurueck in die Layout-Datei.

    Wird von der Diagnose-Oberflaeche benutzt, damit die Pin-Zuordnung beim
    Einrichten der Hardware ohne Editor korrigiert werden kann. Legt vor dem
    Schreiben eine Sicherungskopie (.bak) an.
    """
    path = layout_path(path)
    data = json.loads(path.read_text(encoding="utf-8"))

    for area in data.get("areas", []):
        for space in area.get("spaces", []):
            if space.get("id") != space_id:
                continue
            if gpio_pin is not None:
                space["gpio_pin"] = int(gpio_pin)
            if invert is not None:
                space["invert"] = bool(invert)
            if pull_up is not None:
                space["pull_up"] = pull_up

            path.with_suffix(path.suffix + ".bak").write_text(
                json.dumps(json.loads(path.read_text(encoding="utf-8")),
                           indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            log.info("Layout aktualisiert: %s -> %s", space_id, space)
            return dict(space)

    raise ValueError(f"Unbekanntes Parkfeld '{space_id}'.")
