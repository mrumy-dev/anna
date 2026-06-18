# Design-Briefing – ANNA App

> **So nutzt du das:** Diesen Text in Claude Design einfügen und das Logo
> (`brand/anna-logo.jpeg`) anhängen. Farben/Typo stehen in `Brand.md`, die Daten,
> die das UI anzeigt, in `../backend/docs/API.md`. Ziel ist die Oberfläche der
> ANNA-App; das Backend liefert die Daten später über die dort beschriebene API.

## Worum es geht

ANNA ist eine **Parkplatz-App**, die in Echtzeit zeigt, welche Parkfelder frei
sind. Hinter der App steckt ein Modellparkplatz mit Sensoren (Schulprojekt), aber
die Oberfläche soll wie eine **echte, fertige Consumer-App** wirken – „Deine
Parking App".

**Zielgruppe:** Autofahrer, die einen freien Platz suchen – meist **unterwegs am
Handy**. Mobil-zuerst gestalten, Desktop als grössere Variante.

**Die eine Aufgabe der Hauptansicht:** „Zeig mir auf einen Blick, wo gerade ein
freier Platz ist – und zwar von der Art, die ich brauche."

## Das Herzstück (Signature)

Das prägende, wiedererkennbare Element ist das **Raster der Parkfelder, das sich
live füllt und leert**: grüne Kacheln = frei, gedämpft rote = belegt. Dieses
Raster ist der Held der Detailansicht – ruhig, klar, sofort verständlich. Die
Bewegung (ein Feld wird frei/belegt) ist der Moment, der die App lebendig macht.
Drumherum alles diszipliniert halten.

## Gewählte Variante (verbindlicher Funktionsumfang)

Das Team hat sich für **Variante 2 „Komfort"** entschieden:

- Anzeige **frei/belegt je Parkfeld**.
- **Filter nach Parkfeldtyp:** Alle · Normal · Familie · Frauen · Behinderte.
- Anfahrt als **Weiterleitung an Google Maps** (Button „Route"). **Keine eigene
  Navigation/Karte in der App.**

Konkretes Modell (für realistische Inhalte): eine Stadt mit **zwei Parkarealen** –
*Blumenstrasse* (4 Felder) und *Hauptstrasse* (3 Felder). Felder heissen B1–B4 und
H1–H3.

## Ansichten / Screens

**1 – Übersicht (Start).**
Stadt/Standort oben, darunter die **Parkareale als Karten** mit Name und grosser
**Frei-Zahl** („2 von 4 frei"). Filterleiste (Alle/Normal/Familie/Frauen/
Behinderte), die die Frei-Zahlen je Karte beeinflusst. Tippen auf eine Karte führt
zur Detailansicht. Ein Areal ohne freie Plätze ist klar als **voll** markiert.

**2 – Areal-Detail.**
Kopf mit Arealname, Frei-Zahl und **„Route"-Button** (öffnet Google Maps).
Darunter das **Parkfeld-Raster** (das Herzstück): jede Kachel zeigt Feld-ID
(z. B. „B3"), Zustand (Frei/Belegt) und eine **Typ-Markierung** (Normal/Familie/
Frauen/Behinderte). Der aktive Filter hebt passende Felder hervor bzw. blendet die
anderen optisch zurück.

**3 – Zustand „Areal voll".**
Wenn ein Areal voll ist: deutlicher, ruhig gestalteter Hinweis **„Areal voll"** und
ein Verweis auf das **andere Areal** als Alternative (das entspricht der Idee „ist
das gewählte Areal voll, schlage das andere vor"). Kein Alarm-Look, sondern
hilfreiche Führung.

**4 – Zustände allgemein.**
- **Frei-Kachel** und **Belegt-Kachel** als klar unterscheidbare, gestaltete
  Zustände (nicht nur Farbe – auch Beschriftung, damit es barrierefrei ist).
- **Laden / keine Daten:** kurzer, sachlicher Platzhalter.
- **Verbindungsfehler:** ruhiger Hinweis „Keine Verbindung – versuche es erneut",
  keine Entschuldigung, kein Drama.

*Optionale Ansichten (nur falls Zeit, nicht Teil der Grundfunktion):* Reservierung
eines Feldes, Auslastungs-Statistik.

## Marke & Ton

Farben und Typografie strikt nach `Brand.md`: **Grün = frei/Aktion**, **gedämpftes
Rot = belegt**, **Navy = Struktur**. Das Logo gibt die Richtung der Schrift vor
(geometrisch, kräftig, weit gesperrt). Texte deutsch, Satzanfang gross, kurze
aktive Verben („Frei", „Belegt", „Route", „Areal voll – wähle ein anderes").

## Qualitätslatte

Mobil-zuerst und responsiv bis zum kleinen Handy. Sichtbarer Tastatur-Fokus,
ausreichende Kontraste, Zustände nicht nur über Farbe (auch Text/Form). Bewegung
sparsam und gezielt (das Füllen/Leeren der Kacheln) – keine verstreuten Effekte.

## Übergabe ans Backend

Was die Oberfläche anzeigt, kommt aus `GET /api/state` (siehe
`../backend/docs/API.md`): pro Areal `name`, `free`, `total`, `is_full`,
`maps_url`, `counts_by_type` und die Liste `spaces` mit `type` und `occupied`.
Bitte die Screens so gestalten, dass sie genau auf diese Daten passen – dann lässt
sich das Design in Claude Code 1:1 ans Backend hängen.
