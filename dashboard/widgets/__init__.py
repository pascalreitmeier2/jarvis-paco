"""Widget registry.

Importing this package registers all built-in widgets. Add new widgets by
creating a module here that subclasses ``Widget`` and decorating it with
``@register_widget``.
"""

from .base import Widget, register_widget, get_widget, all_widgets  # noqa: F401

# Import side-effect: registers the widgets.
from . import email_priority  # noqa: F401,E402

__all__ = ["Widget", "register_widget", "get_widget", "all_widgets"]
