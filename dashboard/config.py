"""Configuration for the dashboard, loaded from environment / a `.env` file.

Reuses the same convention as ``jarvis.py``: variables are read from a `.env`
file next to the project root (via python-dotenv) or from the shell.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = one level above this package.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / ".cache"

# Load the same .env the main jarvis script uses.
load_dotenv(PROJECT_ROOT / ".env")


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# --- Web server -------------------------------------------------------------
HOST = os.getenv("DASHBOARD_HOST", "127.0.0.1")
PORT = int(os.getenv("DASHBOARD_PORT", "8765"))
DEBUG = _get_bool("DASHBOARD_DEBUG", False)
# Open the browser automatically when the server starts.
OPEN_BROWSER = _get_bool("DASHBOARD_OPEN_BROWSER", True)

# --- Gmail ------------------------------------------------------------------
# OAuth client credentials (Google Cloud console → OAuth client, type "Desktop").
# Either provide GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET, or point
# GOOGLE_CREDENTIALS_FILE at a downloaded client-secret JSON.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "")
GMAIL_TOKEN_FILE = Path(
    os.getenv("GMAIL_TOKEN_FILE", str(CACHE_DIR / "gmail_token.json"))
)
GMAIL_OAUTH_PORT = int(os.getenv("GMAIL_OAUTH_PORT", "8899"))
# Gmail search query for the messages to prioritise. Default: unread inbox mail
# from the last 14 days. Override to taste, e.g. "in:inbox newer_than:3d".
GMAIL_QUERY = os.getenv("GMAIL_QUERY", "in:inbox is:unread newer_than:14d")
# How many messages to pull at most per refresh.
GMAIL_MAX_RESULTS = int(os.getenv("GMAIL_MAX_RESULTS", "20"))

# --- Claude (prioritisation) ------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# Default to the current Opus. Override with e.g. "claude-sonnet-5" for lower
# cost per refresh.
DASHBOARD_MODEL = os.getenv("DASHBOARD_MODEL", "claude-opus-5")
# Effort for the classification call — "low" keeps refreshes fast and cheap.
DASHBOARD_EFFORT = os.getenv("DASHBOARD_EFFORT", "low")

# --- To-do persistence ------------------------------------------------------
TODO_STATE_FILE = Path(
    os.getenv("DASHBOARD_TODO_FILE", str(CACHE_DIR / "dashboard_todos.json"))
)


def ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
