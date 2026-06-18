"""ANNA Backend - Flask-Anwendung.

Stellt eine kleine JSON-API bereit und liefert die Web-UI aus. Der Datenfluss:

    Sensor -> SensorBackend.read_all() -> ParkingSystem -> JSON-API -> Web-UI

Die Web-UI fragt die API im Intervall ab (Polling) und zeichnet die beiden
Parkareale mit frei/belegt sowie den Filtern (Familie/Frauen/Behinderte).

Der Kernvertrag (siehe docs/API.md) bleibt stabil. Zusatzfunktionen werden
ausschliesslich ueber NEUE Endpunkte angeboten (Live-Stream, Statistik,
Reservierung), damit das bestehende UI weiter passt.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterator

from flask import Flask, Response, jsonify, render_template, request

from .config import load_layout
from .models import ParkingSystem, StatsCollector
from .sensors import create_backend
from .sensors.base import SensorBackend

# Eine Fabrik (system, settings) -> SensorBackend. Erlaubt das Einschleusen
# eines Test- oder Fake-Backends, ohne Umgebungsvariablen oder Hardware.
BackendFactory = Callable[[ParkingSystem, dict], SensorBackend]


def _default_backend(system: ParkingSystem, settings: dict) -> SensorBackend:
    """Backend anhand der Umgebungsvariable ANNA_BACKEND (Default: Simulator)."""
    name = os.environ.get("ANNA_BACKEND", "simulated")
    return create_backend(
        name, system, bounce_time=settings.get("bounce_time_s", 0.05)
    )


def create_app(backend_factory: BackendFactory | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder="web/templates",
        static_folder="web/static",
        static_url_path="/static",
    )

    system, settings = load_layout()
    backend = (backend_factory or _default_backend)(system, settings)
    stats = StatsCollector()

    app.config["SYSTEM"] = system
    app.config["BACKEND"] = backend
    app.config["SETTINGS"] = settings
    app.config["STATS"] = stats

    def current_state() -> dict:
        """Sensoren lesen, Modell aktualisieren, serialisieren, Statistik fuehren."""
        system.apply_readings(backend.read_all())
        state = system.to_dict()
        state["mode"] = backend.name
        stats.record(state)
        return state

    # --- Web-UI -----------------------------------------------------------
    @app.get("/")
    def index():
        return render_template(
            "index.html",
            poll_interval_ms=settings.get("poll_interval_ms", 1500),
        )

    # --- API: Kernvertrag (docs/API.md) -----------------------------------
    @app.get("/api/state")
    def api_state():
        return jsonify(current_state())

    @app.get("/api/health")
    def api_health():
        return jsonify({"status": "ok", "mode": backend.name})

    # --- API: Live-Updates per Server-Sent-Events (additiv) ---------------
    @app.get("/api/stream")
    def api_stream():
        """Schiebt den State als SSE. 'limit' begrenzt die Anzahl Events."""
        interval = settings.get("poll_interval_ms", 1500) / 1000.0
        limit = request.args.get("limit", type=int)
        return Response(
            _state_events(current_state, interval, limit),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # --- API: Statistik / Auslastung (additiv) ----------------------------
    @app.get("/api/stats")
    def api_stats():
        current_state()  # mindestens eine aktuelle Messung sicherstellen
        return jsonify(stats.to_dict())

    # --- API: Reservierung (additiv, AP 5.3) ------------------------------
    @app.get("/api/reservations")
    def api_reservations():
        return jsonify({"reservations": system.reservations()})

    @app.post("/api/reserve/<space_id>")
    def api_reserve(space_id: str):
        if system.space(space_id) is None:
            return jsonify({"error": "Unbekanntes Parkfeld."}), 404
        current_state()  # aktuellen Belegungsstand uebernehmen
        result = system.reserve(space_id)
        if not result["ok"]:
            return jsonify({"error": result["reason"]}), 409
        return jsonify({"reservations": system.reservations()})

    @app.delete("/api/reserve/<space_id>")
    def api_cancel_reservation(space_id: str):
        if system.space(space_id) is None:
            return jsonify({"error": "Unbekanntes Parkfeld."}), 404
        system.cancel_reservation(space_id)
        return jsonify({"reservations": system.reservations()})

    # --- API: Simulationssteuerung (nur im Simulator aktiv) ---------------
    @app.post("/api/sim/toggle/<space_id>")
    def api_sim_toggle(space_id: str):
        if backend.name != "simulated":
            return jsonify({"error": "Nur im Simulationsmodus verfuegbar."}), 403
        if system.space(space_id) is None:
            return jsonify({"error": "Unbekanntes Parkfeld."}), 404
        backend.toggle(space_id)  # type: ignore[attr-defined]
        return jsonify(current_state())

    @app.post("/api/sim/randomize")
    def api_sim_randomize():
        if backend.name != "simulated":
            return jsonify({"error": "Nur im Simulationsmodus verfuegbar."}), 403
        backend.randomize()  # type: ignore[attr-defined]
        return jsonify(current_state())

    # --- Einheitliche JSON-Fehlerantworten fuer die API -------------------
    @app.errorhandler(404)
    def _not_found(_e):
        return jsonify({"error": "Nicht gefunden."}), 404

    @app.errorhandler(405)
    def _method_not_allowed(_e):
        return jsonify({"error": "Methode nicht erlaubt."}), 405

    return app


def _state_events(
    state_fn: Callable[[], dict],
    interval: float,
    limit: int | None = None,
) -> Iterator[str]:
    """Generator fuer den SSE-Stream. Das erste Event kommt sofort."""
    count = 0
    while True:
        yield f"data: {json.dumps(state_fn())}\n\n"
        count += 1
        if limit is not None and count >= limit:
            break
        time.sleep(interval)


# Erlaubt: flask --app app.main run
app = create_app()
