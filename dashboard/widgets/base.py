"""Widget base class and a tiny registry.

A *widget* is a self-contained dashboard tile. It exposes metadata (id, title,
icon, the frontend renderer to use) and a ``get_data()`` method that returns a
JSON-serialisable dict. The frontend fetches the widget list from
``/api/widgets`` and then each tile's payload from
``/api/widgets/<id>/data``.
"""

from __future__ import annotations

from typing import Dict, List

# id -> Widget instance
_REGISTRY: "Dict[str, Widget]" = {}


class Widget:
    """Base class for dashboard widgets.

    Subclasses set the class attributes and implement ``get_data``.
    """

    # Unique, URL-safe id.
    id: str = ""
    # Human-readable title shown on the tile header.
    title: str = ""
    # Emoji or short glyph for the header.
    icon: str = "▪"
    # Which frontend renderer to use (see dashboard.js). New renderers can be
    # added there; unknown types fall back to a generic JSON view.
    render_type: str = "generic"
    # Suggested auto-refresh interval in seconds (0 = manual only).
    refresh_seconds: int = 0
    # Column span hint for the grid (1 = normal, 2 = wide).
    span: int = 1

    def meta(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "icon": self.icon,
            "render_type": self.render_type,
            "refresh_seconds": self.refresh_seconds,
            "span": self.span,
        }

    def get_data(self) -> dict:  # pragma: no cover - interface method
        """Return the widget payload. Override in subclasses."""
        raise NotImplementedError


def register_widget(cls):
    """Class decorator that instantiates and registers a widget."""
    instance = cls()
    if not instance.id:
        raise ValueError(f"Widget {cls.__name__} is missing an id")
    _REGISTRY[instance.id] = instance
    return cls


def get_widget(widget_id: str) -> "Widget | None":
    return _REGISTRY.get(widget_id)


def all_widgets() -> "List[Widget]":
    return list(_REGISTRY.values())
