"""Prioritise emails and derive to-dos.

Primary path: a single Claude API call that scores every email and proposes
concrete to-dos, in German. If no API key is configured or the call fails, a
transparent rule-based heuristic keeps the dashboard working.
"""

from __future__ import annotations

import json
import logging
from typing import List

from . import config
from .gmail_client import EmailMessage

log = logging.getLogger(__name__)

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

# JSON schema the model must fill in — one entry per input email, keyed by the
# email's Gmail id so we can match results back reliably.
_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "priority": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                    "score": {"type": "integer"},
                    "reason": {"type": "string"},
                    "todos": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["id", "priority", "score", "reason", "todos"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = (
    "Du bist ein Assistent, der die Posteingang-E-Mails einer vielbeschäftigten "
    "Person nach Wichtigkeit sortiert und daraus konkrete To-dos ableitet. "
    "Bewerte jede E-Mail:\n"
    "- priority: 'high' (dringend / benötigt heute eine Reaktion, z.B. Deadlines, "
    "Rechnungen, persönliche Anfragen, Chef/Kunde), 'medium' (sollte diese Woche "
    "erledigt werden), 'low' (Newsletter, Werbung, FYI, kann warten).\n"
    "- score: 0-100, wobei 100 maximal dringend ist.\n"
    "- reason: EIN kurzer deutscher Satz, warum diese Priorität.\n"
    "- todos: 0-3 konkrete, umsetzbare Aufgaben in deutscher Sprache und "
    "Imperativ (z.B. 'Angebot bis Freitag beantworten'). Bei Newslettern/Werbung "
    "meist keine To-dos (leere Liste).\n"
    "Antworte ausschließlich über das vorgegebene JSON-Format."
)


def _email_block(msg: EmailMessage) -> str:
    date = msg.date.strftime("%d.%m.%Y %H:%M") if msg.date else "unbekannt"
    return (
        f"id: {msg.id}\n"
        f"Von: {msg.sender_name} <{msg.sender_email}>\n"
        f"Betreff: {msg.subject or '(kein Betreff)'}\n"
        f"Datum: {date}\n"
        f"Ungelesen: {'ja' if msg.unread else 'nein'}\n"
        f"Auszug: {msg.snippet[:400]}"
    )


def prioritize_with_claude(messages: List[EmailMessage]) -> dict:
    """Return {id: {priority, score, reason, todos}} via the Claude API."""
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY or None)

    user_content = (
        "Hier sind die aktuellen E-Mails. Bewerte jede und gib pro E-Mail ein "
        "Ergebnis mit derselben id zurück.\n\n"
        + "\n\n---\n\n".join(_email_block(m) for m in messages)
    )

    response = client.messages.create(
        model=config.DASHBOARD_MODEL,
        max_tokens=4000,
        system=_SYSTEM_PROMPT,
        output_config={
            "effort": config.DASHBOARD_EFFORT,
            "format": {"type": "json_schema", "schema": _RESULT_SCHEMA},
        },
        messages=[{"role": "user", "content": user_content}],
    )

    text = next((b.text for b in response.content if b.type == "text"), "")
    data = json.loads(text)
    return {r["id"]: r for r in data.get("results", [])}


# --- Rule-based fallback ----------------------------------------------------

_HIGH_KEYWORDS = [
    "dringend", "urgent", "asap", "sofort", "wichtig", "important",
    "deadline", "frist", "rechnung", "invoice", "mahnung", "zahlung",
    "payment", "vertrag", "contract", "termin", "meeting", "bewerbung",
    "angebot", "kündigung", "überfällig", "action required", "antwort",
]
_LOW_KEYWORDS = [
    "newsletter", "sale", "rabatt", "angebote", "% off", "unsubscribe",
    "abmelden", "werbung", "promotion", "deal", "gewinnspiel", "no-reply",
    "noreply", "digest", "notification", "benachrichtigung",
]


def prioritize_with_rules(messages: List[EmailMessage]) -> dict:
    out = {}
    for m in messages:
        haystack = f"{m.subject} {m.snippet} {m.sender_email}".lower()
        score = 45
        if m.unread:
            score += 10
        high_hits = [k for k in _HIGH_KEYWORDS if k in haystack]
        low_hits = [k for k in _LOW_KEYWORDS if k in haystack]
        score += 18 * len(high_hits)
        score -= 22 * len(low_hits)
        score = max(0, min(100, score))

        if score >= 70:
            priority = "high"
        elif score >= 45:
            priority = "medium"
        else:
            priority = "low"

        todos: List[str] = []
        reason_parts = []
        if high_hits:
            reason_parts.append(f"Stichwörter: {', '.join(high_hits[:3])}")
        if low_hits:
            reason_parts.append("wirkt wie Newsletter/Werbung")
        if m.unread:
            reason_parts.append("ungelesen")
        reason = "; ".join(reason_parts) or "Standardbewertung"

        if priority != "low":
            subject = m.subject or "E-Mail"
            todos.append(f"{subject[:60]} von {m.sender_name} bearbeiten")

        out[m.id] = {
            "id": m.id,
            "priority": priority,
            "score": score,
            "reason": reason,
            "todos": todos,
        }
    return out


def prioritize(messages: List[EmailMessage]) -> tuple[dict, str]:
    """Prioritise ``messages``. Returns (results_by_id, engine_name)."""
    if not messages:
        return {}, "none"

    if config.ANTHROPIC_API_KEY:
        try:
            return prioritize_with_claude(messages), "claude"
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            log.warning("Claude-Priorisierung fehlgeschlagen, nutze Heuristik: %s", exc)

    return prioritize_with_rules(messages), "rules"
