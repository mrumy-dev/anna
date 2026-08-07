"""Tests fuer die Entprellung auf Fachebene (app/stability.py).

Diese Tests sind der fertige Pruefstand fuer die noch offene Entscheidungsregel.
Sobald `ReadingStabilizer.apply()` implementiert ist, die Zeile
`pytestmark = pytest.mark.skip(...)` loeschen - dann pruefen sie das Verhalten.
"""

from __future__ import annotations

import pytest

from app.stability import ReadingStabilizer

pytestmark = pytest.mark.skip(
    reason="Entscheidungsregel in app/stability.py noch offen (TODO Team)"
)


def test_first_reading_is_taken_immediately():
    """Beim Start soll die Anzeige sofort stimmen, nicht erst nach n Messungen."""
    stab = ReadingStabilizer(confirmations=2)
    assert stab.apply({"B1": True}) == {"B1": True}


def test_single_outlier_is_ignored():
    stab = ReadingStabilizer(confirmations=2)
    stab.apply({"B1": False})
    # Ein einzelner Ausreisser darf die Anzeige nicht umschalten.
    assert stab.apply({"B1": True}) == {"B1": False}


def test_change_after_enough_confirmations():
    stab = ReadingStabilizer(confirmations=2)
    stab.apply({"B1": False})
    stab.apply({"B1": True})
    assert stab.apply({"B1": True}) == {"B1": True}


def test_flapping_does_not_switch():
    stab = ReadingStabilizer(confirmations=2)
    stab.apply({"B1": False})
    for _ in range(5):
        stab.apply({"B1": True})    # Ausreisser ...
        stab.apply({"B1": False})   # ... sofort widerrufen
    assert stab.apply({"B1": False}) == {"B1": False}


def test_confirmations_one_reacts_immediately():
    stab = ReadingStabilizer(confirmations=1)
    stab.apply({"B1": False})
    assert stab.apply({"B1": True}) == {"B1": True}


def test_fields_are_independent():
    stab = ReadingStabilizer(confirmations=2)
    stab.apply({"B1": False, "B2": False})
    result = stab.apply({"B1": True, "B2": False})
    assert result == {"B1": False, "B2": False}
    result = stab.apply({"B1": True, "B2": False})
    assert result["B1"] is True


def test_rejects_invalid_confirmations():
    with pytest.raises(ValueError):
        ReadingStabilizer(confirmations=0)
