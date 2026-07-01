#!/usr/bin/env python3
"""Startet das ANNA-Backend (Web-App + JSON-API).

Entwicklung / Demonstrator (Simulator, Standard):
    python run.py

Auf dem Raspberry Pi mit echten Sensoren:
    ANNA_BACKEND=gpio python run.py

Umgebungsvariablen:
    ANNA_HOST     Bind-Adresse (Standard 0.0.0.0 -> im ganzen WLAN erreichbar)
    ANNA_PORT     Port (Standard 5000; auf macOS ist 5000 oft belegt -> 5050)
    ANNA_BACKEND  "simulated" (Standard) oder "gpio"
    ANNA_DEBUG    "1" schaltet den Debug-Modus ein (nur zur Entwicklung!)
    ANNA_SERVER   "werkzeug" (Standard) oder "waitress" (haerterer WSGI-Server)

Fuer den Dauerbetrieb siehe deploy/anna.service (systemd-Autostart).
"""

from __future__ import annotations

import logging
import os

from app import create_app

log = logging.getLogger("anna")


def _env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _serve_waitress(app, host: str, port: int) -> bool:
    """Serviert mit waitress, falls installiert. Gibt False zurueck, wenn nicht."""
    try:
        from waitress import serve
    except ImportError:
        log.warning("ANNA_SERVER=waitress gewuenscht, aber waitress ist nicht "
                    "installiert. Fallback auf den eingebauten Server.")
        return False
    threads = int(os.environ.get("ANNA_THREADS", "8"))
    log.info("Server: waitress (threads=%d)", threads)
    serve(app, host=host, port=port, threads=threads)
    return True


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = create_app()
    host = os.environ.get("ANNA_HOST", "0.0.0.0")
    port = int(os.environ.get("ANNA_PORT", "5000"))
    debug = _env_flag("ANNA_DEBUG")
    server = os.environ.get("ANNA_SERVER", "werkzeug").strip().lower()

    system = app.config["SYSTEM"]
    backend = app.config["BACKEND"]
    log.info("ANNA startet: backend=%s, areas=%d, spaces=%d",
             backend.name, len(system.areas), len(system.space_ids))
    log.info("Web-App erreichbar unter http://%s:%d", host, port)
    if debug:
        log.warning("DEBUG ist aktiv - nur zur Entwicklung, nicht im Dauerbetrieb.")

    # Produktions-Pfad: waitress nur, wenn ausdruecklich gewuenscht.
    if server == "waitress" and not debug:
        if _serve_waitress(app, host, port):
            return

    # Standard: eingebauter Server, aber mit threaded=True (mehrere Clients +
    # Server-Sent-Events) und Debug standardmaessig AUS.
    log.info("Server: werkzeug (threaded)")
    app.run(host=host, port=port, debug=debug, threaded=True,
            use_reloader=debug)


if __name__ == "__main__":
    main()
