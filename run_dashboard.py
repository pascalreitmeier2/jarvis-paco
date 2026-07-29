#!/usr/bin/env python3
"""Entry point for the Jarvis dashboard.

Starts a local Flask server and (optionally) opens it in the browser.

  python -m pip install -r requirements.txt
  python run_dashboard.py

Configuration (Gmail OAuth, Claude model, port, …) is read from environment
variables / the project's `.env` file — see dashboard/config.py and the README.

If the configured port is already taken, the launcher is forgiving: if a Jarvis
dashboard is already running there it just opens that tab, and otherwise it
falls back to the next free port instead of crashing with "Address already in
use".
"""

from __future__ import annotations

import os
import socket
import threading
import urllib.request
import webbrowser

from dashboard import create_app
from dashboard import config


def _open_browser_later(url: str) -> None:
    # Give the server a moment to bind before opening the tab.
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()


def _port_in_use(host: str, port: int) -> bool:
    """True if something is already listening on host:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _is_jarvis_dashboard(url: str) -> bool:
    """True if the URL already serves this dashboard (so we can reuse it)."""
    try:
        with urllib.request.urlopen(url, timeout=1.5) as resp:
            body = resp.read(4000).decode("utf-8", "ignore")
        return "Jarvis Dashboard" in body
    except OSError:
        return False


def _find_free_port(host: str, preferred: int) -> int:
    """Return a bindable port, trying ``preferred`` and a few after it."""
    for candidate in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, candidate))
                return candidate
            except OSError:
                continue
    # Last resort: let the OS pick any free ephemeral port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def _should_open_browser() -> bool:
    """Open the tab once — including under the debug reloader (child only)."""
    if not config.OPEN_BROWSER:
        return False
    # With debug=True Werkzeug spawns a reloader parent + worker. Only the
    # worker has WERKZEUG_RUN_MAIN set; opening there gives exactly one tab.
    if config.DEBUG:
        return os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    return True


def main() -> None:
    config.ensure_cache_dir()
    host, port = config.HOST, config.PORT
    url = f"http://{host}:{port}/"

    # Port already taken? Reuse an existing Jarvis dashboard, or step aside.
    if _port_in_use(host, port):
        if _is_jarvis_dashboard(url):
            print(f"Jarvis Dashboard läuft bereits auf {url} — öffne den bestehenden Tab.")
            print("Für einen Neustart zuerst die laufende Instanz beenden (Strg+C in ihrem Fenster).")
            if config.OPEN_BROWSER:
                webbrowser.open(url)
            return
        new_port = _find_free_port(host, port + 1)
        print(f"Port {port} ist belegt (anderer Prozess). Nutze stattdessen Port {new_port}.")
        port = new_port
        url = f"http://{host}:{port}/"

    app = create_app()
    print(f"Jarvis Dashboard läuft auf {url}")
    print("Beenden mit Strg+C.")

    if _should_open_browser():
        _open_browser_later(url)

    try:
        # threaded=True so widget refreshes (Gmail + Claude calls) don't block the UI.
        app.run(host=host, port=port, debug=config.DEBUG, threaded=True)
    except OSError as exc:
        # Racing another launch that grabbed the port between our check and bind.
        print(f"Server konnte nicht auf {host}:{port} starten: {exc}")
        print("Läuft das Dashboard vielleicht schon in einem anderen Fenster?")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
