"""Konfiguration laden und ein ParkingSystem aufbauen."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from .models import Area, ParkingSystem, Space, SpaceType

log = logging.getLogger("anna.config")

# Projektwurzel (eine Ebene ueber dem app-Paket)
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LAYOUT = ROOT / "config" / "parking_layout.json"


def load_layout(path: str | Path | None = None) -> tuple[ParkingSystem, dict]:
    """Liest die Layout-JSON und gibt (ParkingSystem, settings) zurueck.

    Wirft FileNotFoundError bzw. ValueError mit klarer Meldung, wenn die
    Konfiguration fehlt oder unbrauchbar ist.
    """
    path = Path(path or os.environ.get("ANNA_LAYOUT", DEFAULT_LAYOUT))
    if not path.exists():
        raise FileNotFoundError(f"Layout-Datei nicht gefunden: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))

    settings = data.get("settings", {})
    default_invert = settings.get("default_invert", False)

    if not data.get("areas"):
        raise ValueError(f"Layout {path} enthaelt keine Areale.")

    areas: list[Area] = []
    seen_ids: set[str] = set()
    seen_pins: dict[int, str] = {}
    for a in data["areas"]:
        spaces = []
        for s in a["spaces"]:
            space_id = s["id"]
            if space_id in seen_ids:
                raise ValueError(
                    f"Doppelte Parkfeld-ID '{space_id}' im Layout {path}.")
            seen_ids.add(space_id)

            pin = s.get("gpio_pin")
            if pin is not None and pin in seen_pins:
                log.warning("GPIO-Pin %s doppelt vergeben (%s und %s).",
                            pin, seen_pins[pin], space_id)
            elif pin is not None:
                seen_pins[pin] = space_id

            spaces.append(Space(
                id=space_id,
                type=SpaceType(s.get("type", "normal")),
                gpio_pin=pin,
                invert=s.get("invert", default_invert),
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
