const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, LevelFormat, HeadingLevel, BorderStyle, WidthType,
  ShadingType, TableOfContents, Header, Footer, PageNumber, PageBreak,
} = require("docx");

// --- A4 Geometrie (DXA) ---------------------------------------------------
const PAGE_W = 11906, PAGE_H = 16838, MARGIN = 1440;
const CONTENT_W = PAGE_W - 2 * MARGIN; // 9026

const BRAND_BLUE = "16314F";
const BRAND_GREEN = "3AAA35";
const GREY = "CCCCCC";
const HEAD_FILL = "16314F";

// --- Helfer ---------------------------------------------------------------
const P = (text, opts = {}) =>
  new Paragraph({
    spacing: { after: opts.after ?? 120, line: 276 },
    alignment: opts.align,
    children: Array.isArray(text)
      ? text
      : [new TextRun({ text, bold: opts.bold, italics: opts.italics, color: opts.color })],
  });

const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });

const bullet = (text) =>
  new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    spacing: { after: 60, line: 276 },
    children: Array.isArray(text) ? text : [new TextRun(text)],
  });

const numItem = (text) =>
  new Paragraph({
    numbering: { reference: "nums", level: 0 },
    spacing: { after: 60, line: 276 },
    children: Array.isArray(text) ? text : [new TextRun(text)],
  });

const border = { style: BorderStyle.SINGLE, size: 1, color: GREY };
const borders = { top: border, bottom: border, left: border, right: border,
  insideHorizontal: border, insideVertical: border };

function table(headers, rows, widths) {
  const cell = (text, { head = false, w } = {}) =>
    new TableCell({
      borders,
      width: { size: w, type: WidthType.DXA },
      shading: head ? { fill: HEAD_FILL, type: ShadingType.CLEAR }
                    : { fill: "FFFFFF", type: ShadingType.CLEAR },
      margins: { top: 60, bottom: 60, left: 120, right: 120 },
      children: [new Paragraph({
        spacing: { after: 0, line: 252 },
        children: [new TextRun({ text: String(text), bold: head, color: head ? "FFFFFF" : "000000", size: 20 })],
      })],
    });

  const headRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) => cell(h, { head: true, w: widths[i] })),
  });
  const bodyRows = rows.map((r) =>
    new TableRow({ children: r.map((c, i) => cell(c, { w: widths[i] })) }));

  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: widths,
    rows: [headRow, ...bodyRows],
  });
}

// Box fuer "Diagramm"-Ersatz (zentrierter, getoenter Kasten)
const figBox = (lines) =>
  new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [CONTENT_W],
    rows: [new TableRow({ children: [new TableCell({
      borders,
      width: { size: CONTENT_W, type: WidthType.DXA },
      shading: { fill: "EEF3F7", type: ShadingType.CLEAR },
      margins: { top: 120, bottom: 120, left: 160, right: 160 },
      children: lines.map((l) => new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 60, line: 252 },
        children: [new TextRun({ text: l, font: "Consolas", size: 20, color: BRAND_BLUE, bold: true })],
      })),
    })]})],
  });

const caption = (t) => P([new TextRun({ text: t, italics: true, size: 18, color: "555555" })], { align: AlignmentType.CENTER, after: 200 });

// --- Inhalt ---------------------------------------------------------------
const children = [];

// Titelblock
children.push(new Paragraph({
  spacing: { after: 60 }, alignment: AlignmentType.LEFT,
  children: [new TextRun({ text: "Architekturkonzept", bold: true, size: 56, color: BRAND_BLUE })],
}));
children.push(new Paragraph({
  spacing: { after: 240 },
  children: [new TextRun({ text: "Teilprojekt Informatik", size: 28, color: BRAND_GREEN, bold: true })],
}));
children.push(table(
  ["Feld", "Angabe"],
  [
    ["Projekt", "ANNA - Smart-Parking-Demonstrator"],
    ["Teilprojekt", "Informatik (Teilprojekt 2)"],
    ["Autoren", "Faris Ridzal, Mohamed Rumy"],
    ["Bezug", "Projektstrukturplan AP 2.3, Meilenstein M2"],
    ["Status", "Freigegeben - Version 1.0 - 18.06.2026"],
  ],
  [2600, 6426],
));
children.push(P(""));
children.push(P([new TextRun({ text: "Dieses Dokument beschreibt die umgesetzte Software-Architektur des ANNA-Demonstrators und dient als Grundlage fuer den Abschlussbericht.", italics: true })], { after: 200 }));

// Aenderungsverlauf
children.push(H2("Aenderungsverlauf"));
children.push(table(
  ["Version", "Datum", "Aenderung"],
  [
    ["0.1", "-", "Erster Entwurf (Schichtenmodell, Schnittstelle zu Elektro)."],
    ["1.0", "18.06.2026", "Architektur umgesetzt und verifiziert. Zusaetzlich realisiert: Live-Updates per Server-Sent-Events, Auslastungsstatistik und Feld-Reservierung - jeweils als additive Endpunkte ohne Aenderung am bestehenden API-Vertrag."],
  ],
  [1300, 1500, 6226],
));

children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("Inhaltsverzeichnis")] }));
children.push(new TableOfContents("Inhalt", { hyperlink: true, headingStyleRange: "1-2" }));
children.push(new Paragraph({ children: [new PageBreak()] }));

// 1
children.push(H1("1  Zweck und Abgrenzung"));
children.push(P("Dieses Konzept beschreibt die technische Architektur der Software fuer den ANNA-Demonstrator. Es legt fest, wie die Sensordaten vom Modellparkplatz bis in die Benutzeroberflaeche gelangen, welche Bausteine es dafuer gibt und wie die Schnittstelle zum Teilprojekt Elektro aussieht."));
children.push(P("Nicht Teil dieses Dokuments sind die mechanische Konstruktion, die Auswahl der Sensorbauteile und die elektrische Verdrahtung - diese liegen bei Mechanik bzw. Elektro. Das vorliegende Konzept definiert jedoch die Anforderungen an die Schnittstelle, damit die Software an die Hardware andocken kann."));

// 2
children.push(H1("2  Ausgangslage und Entscheidungsgrundlage"));
children.push(P("Die wichtigsten projektweiten Entscheidungen (Sitzungsprotokoll 04) sind fuer die Architektur bindend:"));
children.push(bullet([new TextRun({ text: "Gewaehlte Variante: Variante 2 'Komfort'. ", bold: true }), new TextRun("Anzeige frei/belegt je Parkfeld, zusaetzlich Filter nach Parkfeldtyp (Familie, Frauen, Behinderte). Die Anfahrt erfolgt als Weiterleitung an Google Maps; es wird keine eigene GPS-Navigation entwickelt.")]));
children.push(bullet([new TextRun({ text: "Rechner: Raspberry Pi 4. ", bold: true }), new TextRun("Programmiersprache Python.")]));
children.push(bullet([new TextRun({ text: "Sensorik: Magnetschalter ", bold: true }), new TextRun("(Reed-Kontakt) je Parkfeld fuer die Belegungserkennung.")]));
children.push(bullet([new TextRun({ text: "Modell: ", bold: true }), new TextRun("zwei Parkareale - Blumenstrasse (4 Parkfelder) und Hauptstrasse (3 Parkfelder), insgesamt 7 Felder. Belegt werden sie durch metallene Modellautos (Hot Wheels).")]));

children.push(H2("2.1  Warum ein Raspberry Pi die Architektur vereinfacht"));
children.push(P("In den urspruenglichen Arbeitspaketen war noch von einem Arduino die Rede. Mit dem Wechsel auf den Raspberry Pi 4 aendert sich die Architektur grundlegend zum Vorteil des Projekts:"));
children.push(table(
  ["", "Arduino (alt)", "Raspberry Pi 4 (aktuell)"],
  [
    ["Sensoren auslesen", "Mikrocontroller, C/C++", "Python ueber GPIO"],
    ["Webserver / UI", "separates Geraet noetig", "gleiches Geraet"],
    ["Verbindung Sensorik / Web", "serielles/Netzwerk-Protokoll zwischen zwei Geraeten", "interner Funktionsaufruf in Python"],
  ],
  [2600, 3000, 3426],
));
children.push(P(""));
children.push(P("Der als 'existenziell' markierte Punkt - die Datenschnittstelle zwischen Hardware und Software - wird damit deutlich entschaerft: Sensorauslesung und Webserver laufen im selben Python-Prozess auf einem Geraet. Die Schnittstelle zu Elektro reduziert sich im Wesentlichen auf die physische Pin-Belegung (welcher Sensor an welchem GPIO)."));
children.push(P([new TextRun({ text: "Aenderungsmanagement: ", bold: true }), new TextRun("Der Wechsel 'Arduino -> Raspberry Pi 4 / Python' ist als Aenderung in der Aenderungsmanagement-Liste zu erfassen (in SiPro 04 verlangt).")]));

// 3
children.push(H1("3  Systemueberblick"));
children.push(P("Der Datenfluss in einem Satz: Reed-Schalter -> GPIO -> Sensor-Backend -> Domaenenmodell -> JSON-API -> Web-UI im Browser."));
children.push(figBox([
  "Reed-Schalter (Feld B1..H3)",
  "v   (Magnet schliesst Kontakt)",
  "GPIO-Pins  ->  Sensor-Backend (read_all)",
  "v",
  "Domaenenmodell (ParkingSystem)  ->  Flask JSON-API",
  "v   (/api/state, Polling/SSE)",
  "Web-UI (HTML/CSS/JS)  ->  Browser (Handy/Laptop)",
  "v   (Route-Button)",
  "Google Maps",
]));
children.push(caption("Abbildung 1: Datenfluss vom Reed-Schalter bis in den Browser."));

// 4
children.push(H1("4  Hardwarearchitektur"));
children.push(bullet([new TextRun({ text: "Raspberry Pi 4 ", bold: true }), new TextRun("als zentrale Steuerung: versorgt die Logik, hostet den Webserver und liest die Sensoren ueber die GPIO-Leiste.")]));
children.push(bullet([new TextRun({ text: "Je Parkfeld ein Reed-Schalter, ", bold: true }), new TextRun("angeschlossen zwischen einem GPIO-Pin und GND. Ueber den internen Pull-up liest der Pin im Ruhezustand HIGH; schliesst der Magnet den Kontakt, wird der Pin auf GND gezogen (LOW) -> Feld belegt.")]));
children.push(bullet([new TextRun({ text: "Optional (Erweiterung): ", bold: true }), new TextRun("Aktoren wie eine Schranke (Servo) oder Status-LEDs je Feld. In der Software vorgesehen, aber nicht Teil der Grundfunktion.")]));
children.push(bullet([new TextRun({ text: "Stromversorgung ", bold: true }), new TextRun("wird durch Elektro definiert; aus Software-Sicht genuegt eine zuverlaessige Versorgung von Pi und Sensoren.")]));
children.push(H2("4.1  Hinweis zur Sensorwahl (mit Elektro zu klaeren)"));
children.push(P("Die Konzeptskizze spricht von Sensoren, die auf Metall ansprechen, das Protokoll SiPro 04 von Magnetschaltern. Das ist nicht dasselbe:"));
children.push(bullet("Ein Reed-Schalter schliesst bei einem Magnetfeld, nicht bei Metall an sich. Ein Hot-Wheels-Auto ist aus Stahl (ferromagnetisch), aber selbst kein Magnet. Damit der Reed-Schalter zuverlaessig reagiert, muss entweder ein kleiner Magnet unter jedes Auto geklebt werden, oder"));
children.push(bullet("es wird ein induktiver Naeherungssensor verwendet, der echtes Metall erkennt."));
children.push(P("Fuer die Software ist nur eines entscheidend: liefert der Sensor ein digitales Signal (an/aus) oder ein analoges? Der Raspberry Pi hat keinen analogen Eingang. Ein digitaler Sensor haengt direkt am GPIO; ein analoger braeuchte zusaetzlich einen A/D-Wandler (z. B. MCP3008). Diese Frage gehoert in das gemeinsame Schnittstellen-Arbeitspaket mit Elektro."));

// 5
children.push(H1("5  Softwarearchitektur"));
children.push(P("Die Software ist in vier Schichten aufgebaut. Jede Schicht kennt nur die direkt darunterliegende; dadurch sind die Teile einzeln testbar und austauschbar."));
children.push(table(
  ["Schicht", "Inhalt"],
  [
    ["4 - Web-UI (Frontend)", "HTML/CSS/JS, Polling bzw. SSE, Filter, Maps-Link"],
    ["3 - Backend / API", "Flask, JSON-Endpunkte, liefert die Web-UI aus"],
    ["2 - Domaenenmodell", "Areal, Parkfeld, Typ, Belegung, Freizaehlung"],
    ["1 - Sensor-Backend (HAL)", "read_all() -> {Feld: belegt}"],
    ["Hardware", "GPIO / Reed-Schalter"],
  ],
  [3000, 6026],
));
children.push(caption("Abbildung 2: Schichtenmodell (oben Frontend, unten Hardware)."));
children.push(numItem([new TextRun({ text: "Sensor-Backend (Hardware-Abstraktion). ", bold: true }), new TextRun("Gemeinsame Schnittstelle SensorBackend.read_all(), die {Parkfeld-ID: belegt} liefert. Implementierungen: SimulatedSensorBackend (im Speicher, ohne Pi) und GpioSensorBackend (echte Reed-Schalter ueber gpiozero). Die Umgebungsvariable ANNA_BACKEND entscheidet, welche laeuft.")]));
children.push(numItem([new TextRun({ text: "Domaenenmodell. ", bold: true }), new TextRun("Die Objekte Area, Space, SpaceType und ParkingSystem. Hier liegen Belegungslogik und Freizaehlung (gesamt und je Typ). Hardware- und web-unabhaengig, daher mit Unit-Tests abgedeckt.")]));
children.push(numItem([new TextRun({ text: "Backend / API. ", bold: true }), new TextRun("Ein Flask-Server stellt JSON-Endpunkte bereit (/api/state u. a.) und liefert die Web-UI aus.")]));
children.push(numItem([new TextRun({ text: "Web-UI. ", bold: true }), new TextRun("Eine responsive Seite, die /api/state im Intervall abfragt und die zwei Areale mit frei/belegt sowie den Filtern zeichnet. Ein 'Route'-Button oeffnet Google Maps.")]));
children.push(H2("5.1  Technologiewahl und Begruendung"));
children.push(table(
  ["Baustein", "Wahl", "Begruendung"],
  [
    ["Sprache", "Python 3", "In SiPro 04 festgelegt; im Team vorhanden."],
    ["GPIO-Zugriff", "gpiozero (Backend lgpio)", "Auf aktuellem Raspberry Pi OS empfohlen; Klasse Button passt zum Reed-Schalter (Pull-up + Entprellung). Mock-Variante fuer Tests."],
    ["Webserver", "Flask", "Schlank, gut dokumentiert, liefert statische Dateien + JSON aus einem Prozess."],
    ["Frontend", "HTML/CSS/Vanilla-JS", "Keine Build-Kette noetig, direkt vom Pi auslieferbar, leicht verstaendlich."],
    ["Live-Aktualisierung", "Polling (1,5 s), optional SSE", "Polling als robuste Grundloesung; zusaetzlich /api/stream fuer sofortige Updates."],
  ],
  [1800, 2400, 4826],
));
children.push(P(""));
children.push(P([new TextRun({ text: "Alternative: ", italics: true }), new TextRun({ text: "FastAPI + Uvicorn statt Flask, falls asynchrone Live-Updates und automatische API-Dokumentation gewuenscht sind. Fuer den Funktionsumfang dieses Projekts ist Flask die pragmatischere Wahl.", italics: true })]));

// 6
children.push(H1("6  Kommunikations- und Schnittstellenkonzept"));
children.push(H2("6.1  Interne Kommunikation"));
children.push(P("Innerhalb des Pi gibt es kein Netzwerkprotokoll zwischen Hardware und Software - das Sensor-Backend wird direkt als Python-Objekt aufgerufen. Zwischen Backend und Web-UI laeuft die Kommunikation ueber HTTP/JSON (die API), was die Anzeige auch auf einem zweiten Geraet (Handy) im selben Netz ermoeglicht."));
children.push(H2("6.2  Externe Schnittstelle zu Elektro (die zentrale Abmachung)"));
children.push(P("Die Schnittstelle zwischen Informatik und Elektro ist die GPIO-Pin-Belegung. Sie wird in config/parking_layout.json festgehalten - diese Datei ist das 'Vertragsdokument' zwischen den beiden Teams. Elektro traegt ein, welcher Sensor an welchem Pin haengt; Informatik liest genau diese Felder ein."));
children.push(table(
  ["Parkfeld", "Areal", "Typ", "GPIO (BCM)", "Signal"],
  [
    ["B1", "Blumenstrasse", "normal", "17", "digital"],
    ["B2", "Blumenstrasse", "family", "27", "digital"],
    ["B3", "Blumenstrasse", "women", "22", "digital"],
    ["B4", "Blumenstrasse", "disabled", "23", "digital"],
    ["H1", "Hauptstrasse", "normal", "24", "digital"],
    ["H2", "Hauptstrasse", "normal", "25", "digital"],
    ["H3", "Hauptstrasse", "family", "5", "digital"],
  ],
  [1400, 2600, 1800, 1726, 1500],
));
children.push(P(""));
children.push(P("Die Pins sind Vorschlaege und von Elektro zu bestaetigen. Verdrahtung je Sensor: Reed-Schalter zwischen GPIO und GND, interner Pull-up aktiv. Ist ein Sensor verkehrt verdrahtet, kann pro Feld 'invert': true gesetzt werden, ohne den Code zu aendern."));
children.push(H2("6.3  Schnittstelle zum Benutzer"));
children.push(P("Die Anfahrt erfolgt ueber einen Link auf Google Maps (maps_url je Areal in der Konfiguration). Es wird bewusst keine eigene Navigation umgesetzt (Variante 2)."));

// 7
children.push(H1("7  Datenmodell"));
children.push(P("Das Modell ist konfigurationsgetrieben: Anzahl Areale, Anzahl Felder, Typen und Pins stehen in parking_layout.json. Eine Aenderung am Modellparkplatz (mehr Felder, andere Pins) ist damit eine reine Konfigurationsaenderung, kein Code-Eingriff."));
children.push(table(
  ["Klasse", "Wichtige Attribute / Methoden"],
  [
    ["ParkingSystem", "areas[]; apply_readings(dict); reserve(id); reservations(); to_dict()"],
    ["Area", "id; name; maps_url; spaces[]; free(type); total(type); is_full()"],
    ["Space", "id; type; gpio_pin; invert; occupied; reserved"],
    ["SpaceType (enum)", "normal | family | women | disabled"],
  ],
  [2600, 6426],
));
children.push(caption("Abbildung 3: Datenmodell (Klassen und ihre Beziehungen)."));

// 8
children.push(H1("8  Belegungslogik"));
children.push(numItem("Im Polling-Takt ruft das Backend sensor.read_all() auf."));
children.push(numItem("Das Ergebnis {Feld: belegt} wird ueber ParkingSystem.apply_readings() in das Modell uebernommen."));
children.push(numItem("Pro Areal werden freie/belegte Felder gezaehlt - gesamt und je Typ. Ein Areal gilt als 'voll', wenn kein Feld mehr frei ist."));
children.push(numItem("Entprellung: Der Reed-Schalter kann beim Schliessen prellen; gpiozero glaettet dies ueber bounce_time. Das stuetzt das SMART-Ziel 'in >= 90 % der Faelle korrekte Erkennung'."));

// 9
children.push(H1("9  Betrieb und Deployment"));
children.push(bullet([new TextRun({ text: "Entwicklung (Laptop): ", bold: true }), new TextRun("python run.py -> Simulator, Web-UI unter http://localhost:5000. Auf macOS belegt der AirPlay-Empfaenger Port 5000; dort mit ANNA_PORT=5050 python run.py ausweichen.")]));
children.push(bullet([new TextRun({ text: "Prototyp (Raspberry Pi): ", bold: true }), new TextRun("ANNA_BACKEND=gpio python run.py. Fuer den Dauerbetrieb empfiehlt sich ein Autostart als systemd-Dienst.")]));
children.push(bullet("Das Handy ruft die Seite ueber die IP des Pi im selben WLAN auf."));

// 10
children.push(H1("10  Annahmen, Risiken und offene Punkte"));
children.push(table(
  ["Nr.", "Punkt", "Status / Massnahme"],
  [
    ["1", "Sensor reagiert auf Magnet, nicht auf blankes Metall", "Mit Elektro klaeren: Magnet ans Auto oder induktiver Sensor (4.1)."],
    ["2", "Digitales vs. analoges Sensorsignal", "Bei analog ist ein A/D-Wandler (MCP3008) noetig. Vor Beschaffung festlegen."],
    ["3", "Endgueltige GPIO-Pins", "Von Elektro zu bestaetigen, dann in parking_layout.json eintragen."],
    ["4", "Anzahl Parkfelder", "Aktuell 7 (4 + 3). Durch GPIO-Anzahl nach oben offen."],
    ["5", "Live-Update-Verfahren", "Polling reicht; SSE ist zusaetzlich umgesetzt (/api/stream)."],
  ],
  [700, 3600, 4726],
));

// 11
children.push(H1("11  Ausblick / moegliche Erweiterungen"));
children.push(P("Bereits umgesetzt (additiv, ohne Aenderung am API-Vertrag): Live-Updates per Server-Sent-Events (/api/stream), Auslastungsstatistik (/api/stats) und Reservierung einzelner Felder (/api/reserve/...)."));
children.push(P("Weiterhin offen (nur bei Zeitreserve): Schranke als Aktor, mehrere Stockwerke, Persistenz der Statistik ueber Neustarts hinweg."));

// --- Dokument -------------------------------------------------------------
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: "Arial", color: BRAND_BLUE },
        paragraph: { spacing: { before: 280, after: 140 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 25, bold: true, font: "Arial", color: BRAND_BLUE },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 520, hanging: 260 } } } }] },
      { reference: "nums", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 520, hanging: 260 } } } }] },
    ],
  },
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: PAGE_H }, margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN } } },
    headers: { default: new Header({ children: [new Paragraph({
      alignment: AlignmentType.RIGHT,
      border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: BRAND_GREEN, space: 2 } },
      children: [new TextRun({ text: "ANNA - Architekturkonzept (Teilprojekt Informatik)", size: 16, color: "777777" })],
    })] }) },
    footers: { default: new Footer({ children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "Seite ", size: 16, color: "777777" }),
        new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "777777" }),
        new TextRun({ text: " / ", size: 16, color: "777777" }),
        new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: "777777" })],
    })] }) },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("Architekturkonzept.docx", buf);
  console.log("written Architekturkonzept.docx (" + buf.length + " bytes)");
});
