# API-Schnittstelle – ANNA Backend

Dieses Dokument ist der **Vertrag zwischen Oberfläche und Backend**. Das in
Claude Design entworfene UI wird gegen genau diese Endpunkte verdrahtet; Claude
Code hält das Backend bei dieser Form. Solange beide Seiten sich an dieses
Dokument halten, passen Design und Logik zusammen.

Basis-URL in der Entwicklung: `http://localhost:5000`
Auf dem Raspberry Pi: `http://<IP-des-Pi>:5000`

## GET /api/state

Liefert den gesamten aktuellen Zustand. Die Oberfläche ruft diesen Endpunkt im
Intervall ab (Polling, Standard alle 1,5 s).

```json
{
  "mode": "simulated",
  "total": 7,
  "free": 4,
  "areas": [
    {
      "id": "blumenstrasse",
      "name": "Parkplatz Blumenstrasse",
      "maps_url": "https://www.google.com/maps/search/?api=1&query=Parkplatz+Blumenstrasse",
      "free": 2,
      "total": 4,
      "is_full": false,
      "counts_by_type": {
        "normal":   { "free": 0, "total": 1 },
        "family":   { "free": 0, "total": 1 },
        "women":    { "free": 1, "total": 1 },
        "disabled": { "free": 1, "total": 1 }
      },
      "spaces": [
        { "id": "B1", "type": "normal",   "type_label": "Normal",     "occupied": true  },
        { "id": "B2", "type": "family",   "type_label": "Familie",    "occupied": true  },
        { "id": "B3", "type": "women",    "type_label": "Frauen",     "occupied": false },
        { "id": "B4", "type": "disabled", "type_label": "Behinderte", "occupied": false }
      ]
    }
  ]
}
```

Feldbedeutung:

| Feld | Bedeutung |
|---|---|
| `mode` | `"simulated"` (Laptop) oder `"gpio"` (Pi mit echten Sensoren) |
| `total` / `free` | Anzahl Parkfelder gesamt bzw. frei über alle Areale |
| `areas[].id` | technische ID des Areals |
| `areas[].name` | Anzeigename |
| `areas[].maps_url` | Ziel des „Route"-Buttons (Google Maps) |
| `areas[].free` / `total` | frei/gesamt in diesem Areal |
| `areas[].is_full` | `true`, wenn kein Feld frei ist → „Areal voll"-Zustand zeigen |
| `areas[].counts_by_type` | frei/gesamt je Parkfeldtyp (für die Filter-Zähler) |
| `areas[].spaces[]` | einzelne Parkfelder mit Typ und Belegung |
| `spaces[].type` | `normal` \| `family` \| `women` \| `disabled` |
| `spaces[].occupied` | `true` = belegt, `false` = frei |

## GET /api/health

```json
{ "status": "ok", "mode": "simulated" }
```

## POST /api/sim/toggle/&lt;space_id&gt;

Nur im Simulationsmodus. Schaltet ein Parkfeld belegt/frei (für Demo und
Entwicklung ohne Sensoren). Antwort = derselbe Body wie `GET /api/state`.
Im `gpio`-Modus antwortet der Endpunkt mit HTTP 403.

## POST /api/sim/randomize

Nur im Simulationsmodus. Setzt alle Felder zufällig. Antwort = `GET /api/state`.

---

## Zusatz-Endpunkte (additiv, optional)

> Diese Endpunkte sind **Erweiterungen** (AP 5.3) und **verändern den obigen
> Vertrag nicht**. `GET /api/state` behält exakt die oben beschriebene Form;
> ein bestehendes UI muss diese Endpunkte nicht kennen. Sie stehen bereit,
> falls das UI später Live-Updates, Auslastung oder Reservierung anbietet.

### GET /api/stream (Server-Sent-Events)

Live-Variante zum Polling. Liefert `text/event-stream`; pro Aktualisierung ein
Event, dessen `data` exakt der Body von `GET /api/state` ist:

```
data: { ... gleicher Inhalt wie GET /api/state ... }

```

Das Intervall stammt aus `settings.poll_interval_ms`. Optionaler Query-Parameter
`limit=<n>` beendet den Stream nach `n` Events (für Tests/Demos). Ohne `limit`
läuft der Stream, bis der Client die Verbindung schließt.

### GET /api/stats

Auslastungsstatistik seit dem Start des Backends (im Speicher, ohne Datenbank):

```json
{
  "samples": 42,
  "peak_occupied": 6,
  "avg_occupied": 3.7,
  "areas": [
    { "id": "blumenstrasse", "name": "Parkplatz Blumenstrasse", "total": 4, "peak_occupied": 4, "avg_occupied": 2.1 }
  ]
}
```

| Feld | Bedeutung |
|---|---|
| `samples` | Anzahl ausgewerteter Messungen seit Start |
| `peak_occupied` | höchste gleichzeitige Belegung (gesamt bzw. je Areal) |
| `avg_occupied` | durchschnittliche Belegung (gesamt bzw. je Areal) |

### Reservierung

Eine Reservierung markiert ein **freies** Feld als vorgemerkt. Sie ist vom
Belegungszustand getrennt und erscheint daher **nicht** in `GET /api/state`.
Belegt ein Auto ein reserviertes Feld, wird die Reservierung automatisch
aufgehoben.

- `GET /api/reservations` → `{ "reservations": [ { "id", "area_id", "type", "type_label" } ] }`
- `POST /api/reserve/<space_id>` → reserviert; Antwort wie `GET /api/reservations`.
  `404` bei unbekanntem Feld, `409` wenn das Feld bereits belegt ist.
- `DELETE /api/reserve/<space_id>` → hebt die Reservierung auf; Antwort wie
  `GET /api/reservations`. `404` bei unbekanntem Feld.

Fehlerantworten der API haben durchgehend die Form `{ "error": "<Text>" }`.

---

## Hinweise für das UI-Design

- Die Oberfläche zeigt **frei/belegt je Feld** und **Filter** nach Typ
  (Alle / Normal / Familie / Frauen / Behinderte) – das ergibt sich aus
  `spaces[].type` bzw. `counts_by_type`.
- Der **„voll"-Zustand** (`is_full`) ist ein eigener, gestalteter Zustand: Hinweis
  anzeigen und auf ein anderes Areal verweisen.
- Die **Anfahrt** ist ein Link auf `maps_url` (keine eigene Navigation).
- Die Anzeige soll sich **live** aktualisieren (Polling-Intervall steckt im
  Backend in `config/parking_layout.json` → `settings.poll_interval_ms`).
