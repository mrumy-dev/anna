# Marke – ANNA

Verbindliche Identität für die Oberfläche. Das Logo (`brand/anna-logo.jpeg`) ist
die Referenz: Wortmarke „ANNA" in kräftigem Dunkelblau, die beiden mittleren
Buchstaben als grüne Spitzen, daneben ein Auto und ein Standort-Pin mit „P".
Claim: **Deine Parking App**.

## Farben

| Rolle | Hex | Verwendung |
|---|---|---|
| Navy (Primär) | `#16314f` | Kopfzeile, Text, Struktur |
| Navy 700 | `#1d3f63` | Akzente, Hover |
| Grün (Sekundär) | `#3aaa35` | „frei", Aktions-Buttons, Logo-Akzent |
| Grün soft | `#e4f4e1` | Hintergrund freier Felder |
| Belegt | `#c0563f` | Zustand „belegt" |
| Belegt soft | `#f6e3dd` | Hintergrund belegter Felder |
| Tinte | `#16314f` | Fliesstext |
| Gedämpft | `#6b7c8c` | Sekundärtext |
| Linie | `#dde4ea` | Rahmen, Trenner |
| Hintergrund | `#f3f6f9` | Seitenhintergrund |
| Karte | `#ffffff` | Karten/Flächen |

Grundregel: **Grün = frei / gut / Aktion**, **gedämpftes Rot = belegt**, **Navy =
Struktur**. Sparsam einsetzen, eine Akzentfarbe pro Fläche.

## Typografie

Die Wortmarke ist geometrisch, kräftig und weit gesperrt. Daran anknüpfen:

- **Display / Überschriften:** eine selbstbewusste, geometrische Sans
  (Vorschlag: *Space Grotesk*, *Sora* oder *Archivo*), kräftiges Gewicht,
  leicht erhöhte Laufweite bei Versalien.
- **Fliesstext / UI:** eine neutrale, gut lesbare Sans (Vorschlag: *Inter* oder
  *IBM Plex Sans*).
- **Daten/Zahlen** (z. B. „freie Felder"): dasselbe Display-Gewicht, gross und
  ruhig gesetzt.

Wenn keine Webfonts geladen werden sollen (Betrieb direkt vom Pi), ist ein
System-Stack in Ordnung: `ui-sans-serif, system-ui, Segoe UI, Roboto, Arial`.

## Ton der Texte

Deutsch, Satzanfang gross, kurze aktive Verben. Beschriftungen benennen, was die
Person sieht oder tut: „Frei", „Belegt", „Route", „Areal voll – wähle ein
anderes". Keine Floskeln, keine Entschuldigungen in Fehlermeldungen.

## Maße / Form

Abgerundete Ecken (~12–14 px), grosszügige Abstände, klare Karten. Ein Parkfeld
ist eine kompakte Kachel mit grosser Feld-ID, Zustand und Typ-Markierung.
Mobil zuerst (die App wird primär am Handy genutzt).
