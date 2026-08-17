"""ANNA Backend - Flask-Anwendung.

Stellt eine kleine JSON-API bereit und liefert die Web-UI aus. Der Datenfluss:

    Sensor -> SensorBackend.read_all() -> ParkingSystem -> JSON-API -> Web-UI

Die Web-UI fragt die API im Intervall ab (Polling) und zeichnet die beiden
Parkareale mit frei/belegt sowie den Filtern (Familie/Frauen/Behinderte).

Der Kernvertrag (siehe docs/API.md) bleibt stabil. Zusatzfunktionen werden
ausschliesslich ueber NEUE Endpunkte angeboten (Live-Stream, Statistik,
Reservierung, Diagnose), damit das bestehende UI weiter passt.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import threading
import time
from collections.abc import Callable, Iterator

from flask import Flask, Response, jsonify, render_template, request

from . import pins as pinmap
from .actuators import create_led_backend, test_pattern
from .config import layout_path, load_layout, update_space_wiring
from .models import ParkingSystem, StatsCollector
from .sensors import create_backend
from .sensors.base import SensorBackend
from .stability import ReadingStabilizer

log = logging.getLogger("anna.api")

# Eine Fabrik (system, settings) -> SensorBackend. Erlaubt das Einschleusen
# eines Test- oder Fake-Backends, ohne Umgebungsvariablen oder Hardware.
BackendFactory = Callable[[ParkingSystem, dict], SensorBackend]


def _default_backend(system: ParkingSystem, settings: dict) -> SensorBackend:
    """Backend anhand der Umgebungsvariable ANNA_BACKEND.

    STANDARD IST DER ECHTBETRIEB (gpio). Wer die Seite aufruft, sieht damit
    immer die echten Sensoren - eine Simulation kann nicht versehentlich als
    Produktion durchgehen. Der Simulator ist ausdruecklich anzufordern:

        ANNA_BACKEND=simulated python run.py

    Mit ANNA_STRICT=1 wird der Start zusaetzlich abgebrochen, wenn der
    gpio-Modus laeuft, aber kein einziger Sensor geoeffnet werden konnte.
    """
    name = os.environ.get("ANNA_BACKEND", "gpio")
    backend = create_backend(
        name, system, bounce_time=settings.get("bounce_time_s", 0.05)
    )

    strict = os.environ.get("ANNA_STRICT", "0").strip().lower() in {
        "1", "true", "yes", "on"}
    if strict and name.lower() == "gpio":
        health = backend.health()
        if health["total"] and health["ok"] == 0:
            backend.close()
            raise RuntimeError(
                "ANNA_BACKEND=gpio verlangt, aber kein einziger Sensor konnte "
                "geoeffnet werden. Start abgebrochen, damit keine falschen Daten "
                "angezeigt werden. Pruefen: laeuft bereits ein zweiter "
                "ANNA-Prozess (sudo systemctl stop anna)? Ist gpiozero/lgpio "
                "installiert? Siehe docs/Sensor-Inbetriebnahme.md."
            )
    return backend


def _diag_write_enabled() -> bool:
    """Schreibender Diagnosezugriff nur, wenn ausdruecklich freigeschaltet.

    Das Backend ist im WLAN erreichbar; das Aendern der Verdrahtungs-
    konfiguration soll daher nicht versehentlich offenstehen. Waehrend der
    Inbetriebnahme ANNA_DIAG=1 setzen, fuer die Vorfuehrung wieder entfernen.
    """
    return os.environ.get("ANNA_DIAG", "0").strip().lower() in {"1", "true", "yes", "on"}


class Runtime:
    """Haelt Layout, Sensor-Backend und Einstellungen - neu ladbar.

    Die Neuladbarkeit ist der Kern der Inbetriebnahme-Hilfe: Wird eine
    Pin-Zuordnung korrigiert, muss der Dienst nicht neu gestartet werden.
    """

    def __init__(self, app: Flask, backend_factory: BackendFactory):
        self._app = app
        self._factory = backend_factory
        self.stats = StatsCollector()
        # Ein Lock, weil ab jetzt zwei Quellen messen: die HTTP-Aufrufe und
        # der Hintergrund-Takt fuer die LEDs.
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._ticker: threading.Thread | None = None
        self.system: ParkingSystem
        self.settings: dict
        self.backend: SensorBackend
        self._load()
        self._start_ticker()

    # --- Messen und Ausgeben ---------------------------------------------
    def update(self) -> dict:
        """Sensoren lesen, Modell aktualisieren, LEDs nachfuehren.

        Einziger Ort, an dem gemessen wird - egal ob der Anstoss von einem
        HTTP-Aufruf oder vom Hintergrund-Takt kommt.
        """
        with self._lock:
            readings = self.backend.read_all()
            if self.stabilizer is not None:
                readings = self.stabilizer.apply(readings)
            self.system.apply_readings(readings)

            # Status-LEDs: frei -> gruen, belegt -> rot. Felder, deren Sensor
            # gar nichts liefert, fehlen in `readings` und werden bewusst als
            # "unbekannt" (None) weitergereicht - dort bleiben beide LEDs
            # dunkel, statt faelschlich "frei" zu leuchten.
            self.leds.apply({
                s.id: readings.get(s.id)
                for a in self.system.areas for s in a.spaces
            })

            state = self.system.to_dict()
            state["mode"] = self.backend.name
            self.stats.record(state)
            return state

    def _start_ticker(self) -> None:
        """Misst im Hintergrund weiter, auch ohne geoeffnete Webseite.

        Ohne diesen Takt wuerden die Status-LEDs am Modell nur dann stimmen,
        solange jemand die Web-App offen hat - denn sonst ruft niemand
        /api/state auf. Nur noetig, wenn es ueberhaupt LEDs gibt; in der
        Testsuite ueber ANNA_BACKGROUND=0 abgeschaltet.
        """
        if self.leds.name == "none":
            return
        if os.environ.get("ANNA_BACKGROUND", "1").strip().lower() in {"0", "false", "no", "off"}:
            return

        interval = max(0.1, self.settings.get("poll_interval_ms", 1500) / 1000.0)

        def loop() -> None:
            while not self._stop.is_set():
                try:
                    self.update()
                except Exception as exc:  # noqa: BLE001 - Takt darf nie sterben
                    log.warning("Hintergrund-Messung fehlgeschlagen: %s", exc)
                self._stop.wait(interval)

        self._ticker = threading.Thread(target=loop, daemon=True,
                                        name="anna-leds")
        self._ticker.start()
        log.info("Hintergrund-Takt fuer die Status-LEDs laeuft (%.1f s).",
                 interval)

    def _stop_ticker(self) -> None:
        if self._ticker is not None:
            self._stop.set()
            self._ticker.join(timeout=2.0)
            self._ticker = None
            self._stop.clear()

    def _load(self) -> None:
        self.system, self.settings = load_layout()
        self.backend = self._factory(self.system, self.settings)
        self.stabilizer = self._make_stabilizer()
        self.leds = create_led_backend(
            self.system, self.settings, sensor_mode=self.backend.name
        )
        self._app.config.update(
            SYSTEM=self.system,
            BACKEND=self.backend,
            SETTINGS=self.settings,
            STATS=self.stats,
            STABILIZER=self.stabilizer,
            LEDS=self.leds,
        )

    def _make_stabilizer(self) -> ReadingStabilizer | None:
        """Entprellung - nur fuer echte Sensoren.

        Der Simulator hat kein elektrisches Rauschen; dort wuerde die Glaettung
        lediglich dafuer sorgen, dass eine angetippte Kachel erst beim zweiten
        Abruf umschaltet.
        """
        if self.backend.name == "simulated":
            return None
        confirmations = int(self.settings.get("confirmations", 2))
        if confirmations < 1:
            log.warning("settings.confirmations=%s ist unbrauchbar, nutze 1.",
                        confirmations)
            confirmations = 1
        return ReadingStabilizer(confirmations)

    def reload(self) -> None:
        """Layout neu einlesen und Sensoren neu initialisieren.

        Die GPIO-Pins muessen VOR dem Neuaufbau freigegeben werden, sonst
        meldet gpiozero den Pin als belegt.
        """
        reserved = {r["id"] for r in self.system.reservations()}
        self._stop_ticker()
        for what, closer in (("Sensor-Backend", self.backend),
                             ("LED-Ausgabe", getattr(self, "leds", None))):
            if closer is None:
                continue
            try:
                closer.close()
            except Exception as exc:  # noqa: BLE001
                log.warning("%s konnte nicht sauber geschlossen werden: %s",
                            what, exc)
        self._load()
        for space_id in reserved:
            self.system.reserve(space_id)
        self._start_ticker()


def create_app(backend_factory: BackendFactory | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder="web/templates",
        static_folder="web/static",
        static_url_path="/static",
    )

    rt = Runtime(app, backend_factory or _default_backend)
    app.config["RUNTIME"] = rt

    def current_state() -> dict:
        """Aktueller Zustand fuer die API.

        Bei echten Sensoren laeuft die Messung durch die Entprellung, damit ein
        Auto am Rand des Erfassungsbereichs die Anzeige nicht flackern laesst.
        Die Diagnose (/api/diagnostics) umgeht das bewusst und zeigt weiterhin
        den ungefilterten Sensorwert.
        """
        return rt.update()

    # --- Web-UI -----------------------------------------------------------
    @app.get("/")
    def index():
        # Die Reservierungs-Knoepfe sind im Echtbetrieb standardmaessig aus:
        # Die Seite ist dann eine reine Anzeige, an der sich von Hand nichts
        # veraendern laesst. Einschalten ueber settings.show_reservations.
        return render_template(
            "index.html",
            poll_interval_ms=rt.settings.get("poll_interval_ms", 1500),
            show_reservations=bool(rt.settings.get("show_reservations", False)),
        )

    @app.get("/diag")
    def diag_page():
        """Inbetriebnahme-Seite: Rohpegel, Pin-Suche, Zuordnung korrigieren."""
        return render_template("diag.html", diag_write=_diag_write_enabled())

    # --- API: Kernvertrag (docs/API.md) -----------------------------------
    @app.get("/api/state")
    def api_state():
        return jsonify(current_state())

    @app.get("/api/health")
    def api_health():
        """Betriebszustand - inklusive der Frage, ob Sensoren wirklich liefern.

        Frueher meldete dieser Endpunkt immer "ok", sobald der Prozess lief -
        auch dann, wenn im gpio-Modus KEIN einziger Pin geoeffnet werden konnte.
        Genau deshalb blieb der Sensorausfall unbemerkt. Die Zusatzfelder sind
        additiv, 'status' wird nur im Fehlerfall abgewertet.
        """
        sensors = rt.backend.health()
        if sensors["total"] and sensors["ok"] == 0:
            status = "error"
        elif sensors["failed"]:
            status = "degraded"
        else:
            status = "ok"
        return jsonify({
            "status": status,
            "mode": rt.backend.name,
            "live": rt.backend.name == "gpio",
            "host": socket.gethostname(),
            "sensors_ok": sensors["ok"],
            "sensors_total": sensors["total"],
            "sensors_failed": sensors["failed"],
        })

    # --- API: Live-Updates per Server-Sent-Events (additiv) ---------------
    @app.get("/api/stream")
    def api_stream():
        """Schiebt den State als SSE. 'limit' begrenzt die Anzahl Events."""
        interval = rt.settings.get("poll_interval_ms", 1500) / 1000.0
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
        return jsonify(rt.stats.to_dict())

    # --- API: Reservierung (additiv, AP 5.3) ------------------------------
    @app.get("/api/reservations")
    def api_reservations():
        return jsonify({"reservations": rt.system.reservations()})

    @app.post("/api/reserve/<space_id>")
    def api_reserve(space_id: str):
        if rt.system.space(space_id) is None:
            return jsonify({"error": "Unbekanntes Parkfeld."}), 404
        current_state()  # aktuellen Belegungsstand uebernehmen
        result = rt.system.reserve(space_id)
        if not result["ok"]:
            return jsonify({"error": result["reason"]}), 409
        return jsonify({"reservations": rt.system.reservations()})

    @app.delete("/api/reserve/<space_id>")
    def api_cancel_reservation(space_id: str):
        if rt.system.space(space_id) is None:
            return jsonify({"error": "Unbekanntes Parkfeld."}), 404
        rt.system.cancel_reservation(space_id)
        return jsonify({"reservations": rt.system.reservations()})

    # --- API: Diagnose / Inbetriebnahme (additiv) -------------------------
    @app.get("/api/diagnostics")
    def api_diagnostics():
        """Rohpegel und Beschaltung je Parkfeld.

        Das ist das Werkzeug fuer die Hardware-Inbetriebnahme: 'raw' zeigt den
        elektrischen Pegel am Pin, 'changes' wie oft er sich seit dem Start
        geaendert hat. Bleibt 'changes' bei 0, waehrend ein Auto auf- und
        abgestellt wird, ist die Verdrahtung schuld - nicht die Software.
        """
        rows = rt.backend.diagnostics()
        spaces = {s.id: s for a in rt.system.areas for s in a.spaces}
        led_states = rt.leds.states()
        for row in rows:
            space = spaces.get(row["space_id"])
            if space is not None:
                row.setdefault("configured_pin", space.configured_pin)
                row["type"] = space.type.value
                row["led_green_pin"] = space.led_green_pin
                row["led_red_pin"] = space.led_red_pin
            row["led"] = led_states.get(row["space_id"])
        return jsonify({
            "mode": rt.backend.name,
            "numbering": rt.settings.get("numbering", "bcm"),
            "layout_file": str(layout_path()),
            "write_enabled": _diag_write_enabled(),
            "poll_interval_ms": rt.settings.get("poll_interval_ms", 1500),
            "bounce_time_s": rt.settings.get("bounce_time_s", 0.05),
            "leds_enabled": bool(rt.settings.get("leds_enabled", False)),
            "leds_mode": rt.leds.name,
            "leds_health": rt.leds.health(),
            "led_test": rt.leds.override_info(),
            "leds_reason": getattr(rt.leds, "reason", None),
            "spaces": rows,
        })

    @app.get("/api/diag/pins")
    def api_diag_pins():
        """Referenz: welche BCM-Nummer sitzt auf welchem Header-Pin."""
        return jsonify({
            "numbering": rt.settings.get("numbering", "bcm"),
            "safe_pins": list(pinmap.SAFE_BCM_PINS),
            "pins": [
                {
                    "bcm": bcm,
                    "board": board,
                    "note": pinmap.BCM_NOTES.get(bcm),
                    "safe": bcm in pinmap.SAFE_BCM_PINS,
                }
                for bcm, board in sorted(pinmap.BCM_TO_BOARD.items())
            ],
        })

    @app.post("/api/diag/scan")
    def api_diag_scan():
        """Sucht den Pin, der sich bewegt (Auto waehrend des Scans umstellen)."""
        scan = getattr(rt.backend, "scan", None)
        if scan is None:
            return jsonify({
                "error": "Pin-Suche gibt es nur im gpio-Modus.",
                "mode": rt.backend.name,
            }), 400
        seconds = request.args.get("seconds", default=6.0, type=float)
        seconds = max(1.0, min(30.0, seconds))
        return jsonify({"seconds": seconds, "pins": scan(seconds)})

    @app.post("/api/diag/assign/<space_id>")
    def api_diag_assign(space_id: str):
        """Schreibt Pin/invert/pull_up in die Layout-Datei und laedt neu."""
        if not _diag_write_enabled():
            return jsonify({
                "error": "Schreibzugriff gesperrt. Zum Einrichten ANNA_DIAG=1 setzen."
            }), 403
        if rt.system.space(space_id) is None:
            return jsonify({"error": "Unbekanntes Parkfeld."}), 404

        payload = request.get_json(silent=True) or {}
        pin = payload.get("gpio_pin", payload.get("pin"))
        try:
            if pin is not None:
                pinmap.resolve_pin(int(pin), rt.settings.get("numbering", "bcm"))
            update_space_wiring(
                space_id,
                gpio_pin=None if pin is None else int(pin),
                invert=payload.get("invert"),
                pull_up=payload.get("pull_up"),
            )
            rt.reload()
        except (pinmap.PinError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify({"ok": True, "spaces": rt.backend.diagnostics()})

    @app.post("/api/diag/led-test")
    def api_diag_led_test():
        """Treibt ein Testmuster auf die LEDs - der Selbsttest fuer Ausgaenge.

        Fuer Eingaenge kann man Pegel beobachten (Pin-Suche). Bei AUSGAENGEN
        geht das prinzipiell nicht: man muss sie einschalten und hinsehen.
        Muster: gruen | rot | beide | aus | feld (mit ?space=B1).

        Das Muster uebernimmt die LEDs fuer 'seconds' Sekunden, danach laeuft
        der Normalbetrieb von selbst weiter - der Hintergrund-Takt uebernimmt.
        """
        if rt.leds.name == "none":
            return jsonify({
                "error": "LED-Ansteuerung ist abgeschaltet. In "
                         "config/parking_layout.json \"leds_enabled\": true "
                         "setzen und den Dienst neu starten.",
                "leds_enabled": bool(rt.settings.get("leds_enabled", False)),
            }), 400

        mode = request.args.get("mode", "beide")
        space = request.args.get("space")
        seconds = max(1.0, min(60.0, request.args.get(
            "seconds", default=10.0, type=float)))
        try:
            pattern = test_pattern(rt.system.space_ids, mode, space)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        rt.leds.set_override(pattern, seconds=seconds, label=mode)
        return jsonify({
            "ok": True, "mode": mode, "space": space, "seconds": seconds,
            "leds": rt.leds.states(),
        })

    @app.delete("/api/diag/led-test")
    def api_diag_led_test_stop():
        """Testmuster sofort beenden, Normalbetrieb wieder aufnehmen."""
        rt.leds.set_override(None)
        rt.update()
        return jsonify({"ok": True})

    @app.post("/api/diag/reload")
    def api_diag_reload():
        """Layout neu einlesen, ohne den Dienst neu zu starten."""
        if not _diag_write_enabled():
            return jsonify({
                "error": "Neuladen gesperrt. Zum Einrichten ANNA_DIAG=1 setzen."
            }), 403
        try:
            rt.reload()
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": f"Neuladen fehlgeschlagen: {exc}"}), 500
        return jsonify({"ok": True, "mode": rt.backend.name})

    # --- Simulationssteuerung (nur im Simulator aktiv) --------------------
    @app.post("/api/sim/toggle/<space_id>")
    def api_sim_toggle(space_id: str):
        if rt.backend.name != "simulated":
            return jsonify({"error": "Nur im Simulationsmodus verfuegbar."}), 403
        if rt.system.space(space_id) is None:
            return jsonify({"error": "Unbekanntes Parkfeld."}), 404
        rt.backend.toggle(space_id)  # type: ignore[attr-defined]
        return jsonify(current_state())

    @app.post("/api/sim/randomize")
    def api_sim_randomize():
        if rt.backend.name != "simulated":
            return jsonify({"error": "Nur im Simulationsmodus verfuegbar."}), 403
        rt.backend.randomize()  # type: ignore[attr-defined]
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


# WICHTIG: Hier wird BEWUSST keine App auf Modulebene erzeugt.
#
# Frueher stand hier `app = create_app()`. Das wurde bereits beim blossen
# Importieren des Moduls ausgefuehrt - also auch durch `from app import
# create_app` in run.py. Auf dem Raspberry Pi hat damit der Import alle
# GPIO-Pins geoeffnet, und die anschliessend regulaer erzeugte App bekam
# keinen einzigen Pin mehr ("GPIO17 is already in use"). Ergebnis: Alle
# Parkfelder blieben dauerhaft "frei", ohne sichtbaren Fehler.
#
# Der Flask-CLI-Aufruf verwendet daher die Fabrik direkt:
#     flask --app "app.main:create_app" run
# Fuer produktive Server siehe wsgi.py.
