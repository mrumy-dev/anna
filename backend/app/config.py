"""Konfiguration laden und ein ParkingSystem aufbauen."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .models import Area, ParkingSystem, Space, SpaceType

# Projektwurzel (eine Ebene ueber dem app-Paket)
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LAYOUT = ROOT / "config" / "parking_layout.json"


def load_layout(path: str | Path | None = None) -> tuple[ParkingSystem, dict]:
    """Liest die Layout-JSON und gibt (ParkingSystem, settings) zurueck."""
    path = Path(path or os.environ.get("ANNA_LAYOUT", DEFAULT_LAYOUT))
    data = json.loads(path.read_text(encoding="utf-8"))

    settings = data.get("settings", {})
    default_invert = settings.get("default_invert", False)

    areas: list[Area] = []
    for a in data["areas"]:
        spaces = [
            Space(
                id=s["id"],
                type=SpaceType(s.get("type", "normal")),
                gpio_pin=s.get("gpio_pin"),
                invert=s.get("invert", default_invert),
            )
            for s in a["spaces"]
        ]
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
