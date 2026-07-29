#!/usr/bin/env python3
"""Entry point for the Jarvis dashboard.

Starts a local Flask server and (optionally) opens it in the browser.

  python -m pip install -r requirements.txt
  python run_dashboard.py

Configuration (Gmail OAuth, Claude model, port, …) is read from environment
variables / the project's `.env` file — see dashboard/config.py and the README.
"""

from __future__ import annotations

import threading
import webbrowser

from dashboard import create_app
from dashboard import config


def _open_browser_later(url: str) -> None:
    # Give the server a moment to bind before opening the tab.
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()


def main() -> None:
    config.ensure_cache_dir()
    app = create_app()
    url = f"http://{config.HOST}:{config.PORT}/"
    print(f"Jarvis Dashboard läuft auf {url}")
    print("Beenden mit Strg+C.")

    if config.OPEN_BROWSER and not config.DEBUG:
        _open_browser_later(url)

    # threaded=True so widget refreshes (Gmail + Claude calls) don't block the UI.
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG, threaded=True)


if __name__ == "__main__":
    main()
