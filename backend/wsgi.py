"""WSGI-Einstiegspunkt fuer produktive Server (waitress, gunicorn).

Beispiele (auf dem Raspberry Pi, aus dem Ordner backend/):

    waitress-serve --host=0.0.0.0 --port=5000 --threads=8 wsgi:application

    gunicorn --workers 1 --threads 8 --bind 0.0.0.0:5000 wsgi:application

Es laeuft der Echtbetrieb (echte Sensoren) - das ist der Standard. Nur zum
Entwickeln ohne Hardware:

    ANNA_BACKEND=simulated waitress-serve --port=5000 wsgi:application
"""

from __future__ import annotations

import atexit

from app import create_app

application = create_app()


@atexit.register
def _cleanup() -> None:
    """Gibt beim Prozessende Ressourcen frei (z. B. GPIO-Pins)."""
    backend = application.config.get("BACKEND")
    if backend is not None:
        backend.close()
