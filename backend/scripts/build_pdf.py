#!/usr/bin/env python3
"""Erzeugt aus einer Markdown-Datei ein PDF im ANNA-Layout.

Wird fuer die ausgedruckten Anleitungen verwendet (z. B. die Pi-Anleitung).
Laeuft offline, es wird kein pandoc oder LaTeX benoetigt.

Einmalig installieren:
    pip install markdown xhtml2pdf

Aufruf aus dem Ordner backend/:
    python scripts/build_pdf.py docs/Raspberry-Pi-Test.md
    python scripts/build_pdf.py docs/Sensor-Inbetriebnahme.md
"""

from __future__ import annotations

import sys
from pathlib import Path

CSS = """
@page { size: a4; margin: 1.8cm 1.6cm; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 10.5pt;
       color: #1b2b3a; line-height: 1.45; }
h1 { color: #16314f; font-size: 20pt; margin: 0 0 6pt; }
h2 { color: #16314f; font-size: 14pt; margin: 16pt 0 4pt;
     border-bottom: 1.5pt solid #3aaa35; padding-bottom: 2pt; }
h3 { color: #1d3f63; font-size: 11.5pt; margin: 12pt 0 3pt; }
p { margin: 4pt 0; }
ul { margin: 4pt 0 4pt 6pt; }
li { margin: 2pt 0; }
hr { border: 0; border-top: 0.6pt solid #cdd7e0; margin: 12pt 0; }
code { font-family: Courier, monospace; font-size: 9.5pt;
       background: #eef3f7; color: #16314f; }
pre { font-family: Courier, monospace; font-size: 9pt; background: #f3f6f9;
      color: #16314f; border: 0.6pt solid #dbe3ea; border-radius: 4pt;
      padding: 6pt 8pt; margin: 6pt 0; }
blockquote { color: #55636f; border-left: 2.5pt solid #3aaa35;
             margin: 6pt 0; padding: 2pt 0 2pt 8pt; }
strong { color: #16314f; }
table { border-collapse: collapse; margin: 6pt 0; }
th, td { border: 0.6pt solid #cdd7e0; padding: 3pt 6pt; font-size: 9.5pt; }
th { background: #16314f; color: #ffffff; }
"""


def build(src: Path, out: Path | None = None) -> Path:
    try:
        import markdown
        from xhtml2pdf import pisa
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            f"Fehlende Bibliothek ({exc}).\n"
            "Installieren mit: pip install markdown xhtml2pdf"
        ) from exc

    out = out or src.with_suffix(".pdf")
    body = markdown.markdown(
        src.read_text(encoding="utf-8"),
        extensions=["fenced_code", "tables", "sane_lists"],
    )
    html = (f"<html><head><meta charset='utf-8'><style>{CSS}</style></head>"
            f"<body>{body}</body></html>")

    with out.open("wb") as fh:
        result = pisa.CreatePDF(html, dest=fh, encoding="utf-8")
    if result.err:
        raise SystemExit(f"PDF-Erzeugung fehlgeschlagen: {src}")
    return out


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for arg in sys.argv[1:]:
        src = Path(arg)
        if not src.exists():
            raise SystemExit(f"Nicht gefunden: {src}")
        print("erstellt:", build(src))


if __name__ == "__main__":
    main()
