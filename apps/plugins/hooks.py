"""Named extension points that plugins add to, in their AppConfig.ready().

This is the whole hook mechanism: a dict of lists. Each extension point is
documented in docs/plugins.md, together with what it expects.
"""

from collections import defaultdict

NAVIGATION = "navigation"
UNIT_PANELS = "unit_panels"
PERSON_PANELS = "person_panels"

KNOWN = {NAVIGATION, UNIT_PANELS, PERSON_PANELS}


class HookRegistry:
    def __init__(self):
        self._items = defaultdict(list)

    def register(self, hook, item):
        if hook not in KNOWN:
            raise ValueError(f"Unknown extension point {hook!r}; known: {', '.join(sorted(KNOWN))}")
        self._items[hook].append(item)
        return item

    def get(self, hook):
        return list(self._items[hook])

    def clear(self, hook=None):
        """For tests."""
        if hook is None:
            self._items.clear()
        else:
            self._items.pop(hook, None)


hooks = HookRegistry()
