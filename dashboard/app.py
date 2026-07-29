"""Flask app: serves the dashboard shell and the widget JSON API."""

from __future__ import annotations

import logging

from flask import Flask, abort, jsonify, render_template, request

from . import config, todo_store
from .widgets import all_widgets, get_widget

log = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index():
        widgets = [w.meta() for w in all_widgets()]
        return render_template("dashboard.html", widgets=widgets)

    @app.route("/api/widgets")
    def widgets_list():
        return jsonify([w.meta() for w in all_widgets()])

    @app.route("/api/widgets/<widget_id>/data")
    def widget_data(widget_id: str):
        widget = get_widget(widget_id)
        if widget is None:
            abort(404, description=f"Unbekanntes Widget: {widget_id}")
        try:
            return jsonify(widget.get_data())
        except Exception as exc:  # noqa: BLE001
            log.exception("Widget %s ist fehlgeschlagen", widget_id)
            return jsonify({"status": "error", "message": str(exc)}), 500

    @app.route("/api/todos/<path:todo_id>", methods=["POST"])
    def toggle_todo(todo_id: str):
        payload = request.get_json(silent=True) or {}
        done = bool(payload.get("done", False))
        todo_store.set_done(todo_id, done)
        return jsonify({"id": todo_id, "done": done})

    return app
