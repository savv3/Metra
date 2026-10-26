"""Named extension points that plugins add to, in their AppConfig.ready().

This is the whole hook mechanism: a dict of lists. Each extension point is
documented in docs/plugins.md, together with what it expects.
"""

from collections import defaultdict

from . import state

NAVIGATION = "navigation"
UNIT_PANELS = "unit_panels"
PERSON_PANELS = "person_panels"
INVOICE_PANELS = "invoice_panels"
SETTINGS_LINKS = "settings_links"
WEBHOOK_EVENTS = "webhook_events"
MEMBER_PANELS = "member_panels"

HELP_ARTICLES = "help_articles"
NOTIFICATION_KINDS = "notification_kinds"

KNOWN = {
    NAVIGATION,
    UNIT_PANELS,
    PERSON_PANELS,
    INVOICE_PANELS,
    SETTINGS_LINKS,
    WEBHOOK_EVENTS,
    HELP_ARTICLES,
    NOTIFICATION_KINDS,
    MEMBER_PANELS,
}


class HookRegistry:
    def __init__(self):
        self._items = defaultdict(list)
        self._listeners = defaultdict(list)
        self._owners = {}  # id(item): the plugin that added it

    def register(self, hook, item, owner=None):
        """Add ``item`` to ``hook``. It belongs to ``owner``, by default the
        plugin whose code is calling, and is left out while that plugin is off."""
        if hook not in KNOWN:
            raise ValueError(f"Unknown extension point {hook!r}; known: {', '.join(sorted(KNOWN))}")
        self._items[hook].append(item)
        self._owners[id(item)] = owner or state.calling_plugin()
        for listener in self._listeners[hook]:
            listener(item)
        return item

    def subscribe(self, hook, listener):
        """Call ``listener(item)`` for every item registered to ``hook`` from now
        on, so a plugin can react to items added by plugins that load after it."""
        self._listeners[hook].append(listener)

    def get(self, hook, everything=False):
        """The items of a hook whose plugins are on (all of them with ``everything``)."""
        items = list(self._items[hook])
        if everything:
            return items
        return [item for item in items if state.is_enabled(self.owner(item))]

    def owner(self, item):
        """The plugin that added ``item``, or None for Metra itself."""
        return self._owners.get(id(item))

    def clear(self, hook=None):
        """For tests."""
        if hook is None:
            self._items.clear()
        else:
            self._items.pop(hook, None)


hooks = HookRegistry()
