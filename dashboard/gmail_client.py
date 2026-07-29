"""Minimal Gmail read-only client with cached OAuth.

Mirrors the Spotify approach already used in the project: a one-time browser
consent, then a token cached under ``.cache/`` for subsequent runs. Only the
read-only scope is requested.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime
from typing import List, Optional

from . import config

# Read-only: the dashboard never modifies your mailbox.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailNotConfigured(RuntimeError):
    """Raised when no OAuth client credentials are available."""


@dataclass
class EmailMessage:
    id: str
    thread_id: str
    subject: str
    sender_name: str
    sender_email: str
    date: Optional[datetime]
    snippet: str
    unread: bool
    labels: List[str] = field(default_factory=list)

    @property
    def gmail_link(self) -> str:
        # Opens the specific thread in the Gmail web UI.
        return f"https://mail.google.com/mail/u/0/#inbox/{self.thread_id}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "subject": self.subject or "(kein Betreff)",
            "sender_name": self.sender_name or self.sender_email,
            "sender_email": self.sender_email,
            "date": self.date.isoformat() if self.date else None,
            "date_display": _humanise_date(self.date),
            "snippet": self.snippet,
            "unread": self.unread,
            "labels": self.labels,
            "gmail_link": self.gmail_link,
        }


def _humanise_date(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    now = datetime.now(timezone.utc)
    delta = now - dt.astimezone(timezone.utc)
    secs = delta.total_seconds()
    if secs < 0:
        return dt.strftime("%d.%m. %H:%M")
    if secs < 3600:
        mins = int(secs // 60)
        return f"vor {mins} Min" if mins else "gerade eben"
    if secs < 86400:
        return f"vor {int(secs // 3600)} Std"
    days = int(secs // 86400)
    if days < 7:
        return f"vor {days} Tg" if days != 1 else "gestern"
    return dt.strftime("%d.%m.%Y")


def has_credentials() -> bool:
    """True if OAuth client credentials are configured, or a token is cached."""
    if config.GMAIL_TOKEN_FILE.exists():
        return True
    if config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET:
        return True
    return bool(config.GOOGLE_CREDENTIALS_FILE)


def _build_client_config() -> dict:
    """Return an installed-app client config dict from env, or raise."""
    if config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET:
        return {
            "installed": {
                "client_id": config.GOOGLE_CLIENT_ID,
                "client_secret": config.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
    raise GmailNotConfigured(
        "Keine Gmail-Zugangsdaten gefunden. Setze GOOGLE_CLIENT_ID und "
        "GOOGLE_CLIENT_SECRET (oder GOOGLE_CREDENTIALS_FILE) in der .env."
    )


def _load_credentials():
    """Load cached credentials or run the OAuth consent flow."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    config.ensure_cache_dir()
    creds = None
    token_path = config.GMAIL_TOKEN_FILE

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if config.GOOGLE_CREDENTIALS_FILE:
                flow = InstalledAppFlow.from_client_secrets_file(
                    config.GOOGLE_CREDENTIALS_FILE, SCOPES
                )
            else:
                flow = InstalledAppFlow.from_client_config(
                    _build_client_config(), SCOPES
                )
            creds = flow.run_local_server(port=config.GMAIL_OAUTH_PORT)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds


def _service():
    from googleapiclient.discovery import build

    creds = _load_credentials()
    # cache_discovery=False avoids a noisy warning and a file-cache dependency.
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _header(headers: List[dict], name: str) -> str:
    name_l = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name_l:
            return h.get("value", "")
    return ""


def _parse_message(raw: dict) -> EmailMessage:
    payload = raw.get("payload", {})
    headers = payload.get("headers", [])

    from_raw = _header(headers, "From")
    sender_name, sender_email = parseaddr(from_raw)
    if not sender_name:
        sender_name = sender_email.split("@")[0] if sender_email else from_raw

    date_raw = _header(headers, "Date")
    parsed_date: Optional[datetime] = None
    if date_raw:
        try:
            parsed_date = parsedate_to_datetime(date_raw)
            if parsed_date and parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            parsed_date = None

    labels = raw.get("labelIds", [])
    snippet = raw.get("snippet", "")
    # Gmail HTML-escapes a few entities in snippets.
    snippet = (
        snippet.replace("&#39;", "'")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
    )
    snippet = re.sub(r"\s+", " ", snippet).strip()

    return EmailMessage(
        id=raw.get("id", ""),
        thread_id=raw.get("threadId", ""),
        subject=_header(headers, "Subject"),
        sender_name=sender_name,
        sender_email=sender_email,
        date=parsed_date,
        snippet=snippet,
        unread="UNREAD" in labels,
        labels=labels,
    )


def fetch_messages(
    query: Optional[str] = None, max_results: Optional[int] = None
) -> List[EmailMessage]:
    """Fetch recent messages matching ``query`` (Gmail search syntax)."""
    query = query or config.GMAIL_QUERY
    max_results = max_results or config.GMAIL_MAX_RESULTS

    if not has_credentials():
        raise GmailNotConfigured(
            "Keine Gmail-Zugangsdaten gefunden. Setze GOOGLE_CLIENT_ID und "
            "GOOGLE_CLIENT_SECRET (oder GOOGLE_CREDENTIALS_FILE) in der .env."
        )

    service = _service()
    listing = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    ids = [m["id"] for m in listing.get("messages", [])]

    messages: List[EmailMessage] = []
    for msg_id in ids:
        raw = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=msg_id,
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            )
            .execute()
        )
        messages.append(_parse_message(raw))

    # Newest first.
    messages.sort(key=lambda m: m.date or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return messages
