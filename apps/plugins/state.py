"""Which installed plugins are turned on.

Every plugin in METRA_PLUGINS (and every bundled one) is installed and
loaded at startup. An admin turns each one on or off on the Plugins page;
that only hides it, so no restart is needed. While a plugin is off, the
items it added to the hooks, its messaging providers, its event receivers
and its pages under /plugins/<name>/ are left out, and its data is kept.

Items and receivers belong to the plugin whose package registered them;
``owner_of`` works that out from the module name.
"""

import sys
import time

from django.conf import settings
from django.db import DatabaseError

# Seconds a process trusts its copy of the on/off states. Other web
# processes and the worker see a change within this time.
TTL = 2.0

_cache = {"disabled": frozenset(), "at": -TTL}


def plugin_packages():
    """{top-level package: plugin name} for the installed plugins."""
    return {entry.split(".")[0]: name for name, entry in settings.PLUGIN_APPS.items()}


def owner_of(module):
    """The name of the plugin a module belongs to, or None for Metra itself."""
    if not module:
        return None
    return plugin_packages().get(module.split(".")[0])


SKIP = ("apps.plugins", "apps.messaging.registry", "apps.notifications.kinds")


def calling_plugin(skip=SKIP):
    """The plugin whose code called into the plugin API, found by walking up
    the stack past Metra's own plugin modules; None when Metra called."""
    frame = sys._getframe(1)
    while frame is not None:
        module = frame.f_globals.get("__name__", "")
        if not module.startswith(skip):
            return owner_of(module)
        frame = frame.f_back
    return None


def disabled():
    """The names of the installed plugins that are turned off."""
    now = time.monotonic()
    if now - _cache["at"] > TTL:
        from .models import PluginState

        try:
            names = PluginState.objects.filter(enabled=False).values_list("name", flat=True)
            _cache["disabled"] = frozenset(names)
        except DatabaseError:
            # Before the first migration, or while the database is being restored.
            _cache["disabled"] = frozenset()
        _cache["at"] = now
    return _cache["disabled"]


def is_enabled(name):
    """Whether an installed plugin is on. Metra itself (None) always is."""
    return name is None or (name in settings.PLUGIN_APPS and name not in disabled())


def forget():
    """Read the states again on next use (after a change, and in tests)."""
    _cache["at"] = -TTL
