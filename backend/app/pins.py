"""Pin-Nummerierung und Pin-Pruefung fuer den Raspberry Pi 40-Pin-Header.

Dieses Modul ist bewusst FREI von Hardware-Abhaengigkeiten (kein gpiozero-Import),
damit die Zuordnung auch auf dem Laptop getestet werden kann.

Hintergrund - die haeufigste Fehlerquelle im Projekt:
`gpiozero` versteht Pin-Nummern IMMER als BCM-Nummern (GPIO17, GPIO27, ...).
Auf dem Steckerleisten-Aufdruck und in vielen Schaltplaenen stehen aber die
PHYSISCHEN Pin-Nummern (1..40). Wer "Pin 17" verdrahtet, meint je nach Sichtweise
zwei voellig verschiedene Kontakte:

    BCM 17     = physischer Pin 11
    physisch 17 = 3V3-Versorgung (gar kein GPIO!)

Damit beide Welten zusammenpassen, kann in der Layout-Konfiguration
`settings.numbering` auf "bcm" (Standard) oder "board" gesetzt werden.
"""

from __future__ import annotations

# Physischer Header-Pin -> BCM-Nummer. Nicht aufgefuehrte Pins sind
# Versorgung (3V3/5V) oder GND und koennen kein Sensorsignal liefern.
BOARD_TO_BCM: dict[int, int] = {
    3: 2, 5: 3, 7: 4, 8: 14, 10: 15, 11: 17, 12: 18, 13: 27, 15: 22,
    16: 23, 18: 24, 19: 10, 21: 9, 22: 25, 23: 11, 24: 8, 26: 7,
    27: 0, 28: 1, 29: 5, 31: 6, 32: 12, 33: 13, 35: 19, 36: 16,
    37: 26, 38: 20, 40: 21,
}

# Umkehrung: BCM -> physischer Pin (fuer die Anzeige in der Diagnose).
BCM_TO_BOARD: dict[int, int] = {bcm: board for board, bcm in BOARD_TO_BCM.items()}

# Physische Pins, die KEIN GPIO sind - dort kann nie ein Sensor gelesen werden.
BOARD_POWER_PINS: dict[int, str] = {
    1: "3V3", 2: "5V", 4: "5V", 17: "3V3",
    6: "GND", 9: "GND", 14: "GND", 20: "GND", 25: "GND",
    30: "GND", 34: "GND", 39: "GND",
}

# BCM-Pins mit Sonderfunktion - nutzbar, aber mit Vorbehalt.
BCM_NOTES: dict[int, str] = {
    0: "ID_SD (HAT-EEPROM) - nicht als Sensoreingang verwenden",
    1: "ID_SC (HAT-EEPROM) - nicht als Sensoreingang verwenden",
    2: "I2C SDA - hat feste 1k8-Pull-ups auf der Platine",
    3: "I2C SCL - hat feste 1k8-Pull-ups auf der Platine",
    14: "UART TXD - belegt, wenn die serielle Konsole aktiv ist",
    15: "UART RXD - belegt, wenn die serielle Konsole aktiv ist",
}

# BCM-Pins, die sich problemlos als Sensoreingang eignen (Empfehlung).
SAFE_BCM_PINS: tuple[int, ...] = (
    4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 16, 17, 18, 19, 20, 21, 22, 23,
    24, 25, 26, 27,
)

# ALLE GPIOs des Headers - inklusive der Sonderpins 0, 1, 2, 3, 14, 15.
# Wichtig fuer die Pin-Suche: Bei einer Verwechslung von BCM- und
# Header-Nummerierung landen Draehte gerade dort (Header 27 -> GPIO0,
# Header 5 -> GPIO3). Eine Suche, die nur SAFE_BCM_PINS abdeckt, waere blind
# fuer genau den Fehler, den sie finden soll.
ALL_BCM_PINS: tuple[int, ...] = tuple(sorted(BCM_TO_BOARD))

VALID_BCM_PINS: tuple[int, ...] = ALL_BCM_PINS


class PinError(ValueError):
    """Eine Pin-Angabe ist unbrauchbar (z. B. Versorgungspin)."""


def resolve_pin(value: int, numbering: str = "bcm") -> int:
    """Rechnet eine konfigurierte Pin-Nummer in eine BCM-Nummer um.

    numbering="bcm"   -> Wert wird unveraendert uebernommen.
    numbering="board" -> Wert ist ein physischer Header-Pin und wird umgerechnet.
    """
    numbering = (numbering or "bcm").strip().lower()

    if numbering == "bcm":
        if value not in VALID_BCM_PINS:
            raise PinError(
                f"GPIO{value} gibt es auf dem 40-Pin-Header nicht "
                f"(gueltig: {VALID_BCM_PINS[0]}..{VALID_BCM_PINS[-1]})."
            )
        return value

    if numbering == "board":
        if value in BOARD_POWER_PINS:
            raise PinError(
                f"Physischer Pin {value} ist {BOARD_POWER_PINS[value]} und kein "
                f"GPIO - dort kann kein Sensor gelesen werden."
            )
        if value not in BOARD_TO_BCM:
            raise PinError(f"Physischer Pin {value} existiert nicht (1..40).")
        return BOARD_TO_BCM[value]

    raise PinError(f"Unbekannte Nummerierung '{numbering}' (erlaubt: bcm, board).")


def describe_pin(bcm: int) -> str:
    """Kurzbeschreibung eines BCM-Pins inkl. physischer Position."""
    board = BCM_TO_BOARD.get(bcm)
    where = f"Header-Pin {board}" if board else "unbekannte Position"
    note = BCM_NOTES.get(bcm)
    return f"GPIO{bcm} ({where})" + (f" - {note}" if note else "")


def pin_warning(bcm: int) -> str | None:
    """Warnung, falls der Pin fuer einen Sensoreingang heikel ist."""
    return BCM_NOTES.get(bcm)


def board_confusion_hint(value: int) -> str | None:
    """Erklaert, was passiert waere, wenn die Zahl als Header-Pin gemeint war.

    Damit laesst sich die haeufigste Fehlerquelle (BCM- vs. Board-Nummerierung)
    direkt in der Diagnose anzeigen, ohne dass jemand eine Pinout-Tabelle sucht.
    """
    if value in BOARD_POWER_PINS:
        return (
            f"Achtung: Als physischer Header-Pin waere {value} "
            f"{BOARD_POWER_PINS[value]} - dort kommt nie ein Signal an. "
            f"Der Code liest GPIO{value} (Header-Pin {BCM_TO_BOARD.get(value, '?')})."
        )
    if value in BOARD_TO_BCM and BOARD_TO_BCM[value] != value:
        return (
            f"Hinweis: Als physischer Header-Pin waere {value} in Wirklichkeit "
            f"GPIO{BOARD_TO_BCM[value]}. Der Code liest GPIO{value}. "
            f"Bei falscher Verdrahtung 'numbering': 'board' setzen."
        )
    return None
