"""Jarvis Dashboard — a small, widget-based local web dashboard.

The first widget shows a prioritized list of your current Gmail messages and
turns each one into concrete to-dos (via the Claude API). The architecture is
deliberately widget-oriented so more widgets (calendar, Spotify, tasks, …) can
be added later without touching the core.

Run it with:  python run_dashboard.py
"""

__all__ = ["create_app"]

from .app import create_app
