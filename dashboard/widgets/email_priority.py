"""Email priority widget: prioritised inbox + derived to-dos."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from .. import config, gmail_client, prioritizer, todo_store
from ..prioritizer import PRIORITY_ORDER
from .base import Widget, register_widget

log = logging.getLogger(__name__)


@register_widget
class EmailPriorityWidget(Widget):
    id = "email_priority"
    title = "Prio-Mails & To-dos"
    icon = "📬"
    render_type = "email_priority"
    refresh_seconds = 300
    span = 2

    def get_data(self) -> dict:
        try:
            messages = gmail_client.fetch_messages()
        except gmail_client.GmailNotConfigured as exc:
            return {"status": "not_configured", "message": str(exc)}
        except Exception as exc:  # noqa: BLE001
            log.exception("Gmail-Abruf fehlgeschlagen")
            return {
                "status": "error",
                "message": f"Gmail konnte nicht abgerufen werden: {exc}",
            }

        results, engine = prioritizer.prioritize(messages)

        # Collect all to-do ids first, then load their done-state in one shot.
        todo_ids = []
        for msg in messages:
            r = results.get(msg.id, {})
            for i in range(len(r.get("todos", []))):
                todo_ids.append(f"{msg.id}:{i}")
        done_state = todo_store.get_many(todo_ids)

        emails = []
        all_todos = []
        counts = {"high": 0, "medium": 0, "low": 0}

        for msg in messages:
            r = results.get(msg.id, {})
            priority = r.get("priority", "medium")
            counts[priority] = counts.get(priority, 0) + 1

            todos = []
            for i, text in enumerate(r.get("todos", [])):
                tid = f"{msg.id}:{i}"
                todo = {
                    "id": tid,
                    "text": text,
                    "done": done_state.get(tid, False),
                    "priority": priority,
                    "email_subject": msg.subject or "(kein Betreff)",
                    "gmail_link": msg.gmail_link,
                }
                todos.append(todo)
                all_todos.append(todo)

            item = msg.to_dict()
            item.update(
                {
                    "priority": priority,
                    "score": r.get("score", 0),
                    "reason": r.get("reason", ""),
                    "todos": todos,
                }
            )
            emails.append(item)

        # Sort emails by priority, then score.
        emails.sort(
            key=lambda e: (PRIORITY_ORDER.get(e["priority"], 1), -e["score"])
        )
        # Open (not-done) to-dos first, high priority first.
        all_todos.sort(
            key=lambda t: (t["done"], PRIORITY_ORDER.get(t["priority"], 1))
        )

        return {
            "status": "ok",
            "engine": engine,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "query": config.GMAIL_QUERY,
            "counts": counts,
            "total": len(emails),
            "open_todos": sum(1 for t in all_todos if not t["done"]),
            "emails": emails,
            "todos": all_todos,
        }
