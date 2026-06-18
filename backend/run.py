#!/usr/bin/env python3
"""Startet das ANNA-Backend.

Entwicklung (Simulator, Standard):
    python run.py

Auf dem Raspberry Pi (echte Sensoren):
    ANNA_BACKEND=gpio python run.py
"""

import os

from app import create_app

if __name__ == "__main__":
    app = create_app()
    host = os.environ.get("ANNA_HOST", "0.0.0.0")
    port = int(os.environ.get("ANNA_PORT", "5000"))
    app.run(host=host, port=port, debug=True)
