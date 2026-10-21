"""Named extension points that plugins add to, in their AppConfig.ready().

This is the whole hook mechanism: a dict of lists. Each extension point is
documented in docs/plugins.md, together with what it expects.
"""

from collections import defaultdict

NAVIGATION = "navigation"
UNIT_PANELS = "unit_panels"
PERSON_PANELS = "person_panels"
SETTINGS_LINKS = "settings_links"
WEBHOOK_EVENTS = "webhook_events"
MEMBER_PANELS = "member_panels"

HELP_ARTICLES = "help_articles"

KNOWN = {
    NAVIGATION,
    UNIT_PANELS,
    PERSON_PANELS,
    SETTINGS_LINKS,
    WEBHOOK_EVENTS,
    MEMBER_PANELS,
    HELP_ARTICLES,
}


class HookRegistry:
    def __init__(self):
        self._items = defaultdict(list)
        self._listeners = defaultdict(list)

    def register(self, hook, item):
        if hook not in KNOWN:
            raise ValueError(f"Unknown extension point {hook!r}; known: {', '.join(sorted(KNOWN))}")
        self._items[hook].append(item)
        for listener in self._listeners[hook]:
            listener(item)
        return item

    def subscribe(self, hook, listener):
        """Call ``listener(item)`` for every item registered to ``hook`` from now
        on, so a plugin can react to items added by plugins that load after it."""
        self._listeners[hook].append(listener)

    def get(self, hook):
        return list(self._items[hook])

    def clear(self, hook=None):
        """For tests."""
        if hook is None:
            self._items.clear()
        else:
            self._items.pop(hook, None)


hooks = HookRegistry()
