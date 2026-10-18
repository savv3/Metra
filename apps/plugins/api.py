"""What plugins import. Everything here stays stable between releases with
the same API_VERSION; anything else in the app may change.

    from apps.plugins import api

    class MyConfig(AppConfig):
        name = "my_plugin"
        personal_data = []  # what personal data the plugin stores, see docs

        def ready(self):
            api.add_navigation(api.NavItem("My page", "my_plugin:index", "register.view_unit"))
            api.add_unit_panel(api.Panel("my_plugin/panel.html", title="Mine"))
            api.add_messaging_provider(MySMSProvider)
            api.add_settings_link(api.SettingsLink("My settings", "my_plugin:settings"))

    @receiver(api.events.invoice_issued)
    def on_issue(sender, invoice, **kwargs): ...
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from apps.messaging.registry import EMAIL, SMS, Provider, ProviderError, SendResult, registry

from . import events
from .hooks import NAVIGATION, PERSON_PANELS, SETTINGS_LINKS, UNIT_PANELS, hooks
from .roles import grant_to_roles

API_VERSION = 1

__all__ = [
    "API_VERSION",
    "EMAIL",
    "SMS",
    "NavItem",
    "Panel",
    "Provider",
    "ProviderError",
    "SendResult",
    "SettingsLink",
    "add_messaging_provider",
    "add_navigation",
    "add_person_panel",
    "add_settings_link",
    "add_unit_panel",
    "events",
    "grant_to_roles",
]


@dataclass
class NavItem:
    """A link in the main menu. ``permission`` hides it from users without it."""

    label: str
    url_name: str
    permission: str = ""


@dataclass
class Panel:
    """A section on unit or person pages, rendered from ``template``.

    The template gets ``object`` (the unit or person), ``request``, ``perms``,
    ``title`` and whatever ``context(request, object)`` returns.
    """

    template: str
    title: str = ""
    permission: str = ""
    context: Callable | None = field(default=None)


def add_navigation(item):
    return hooks.register(NAVIGATION, item)


def add_unit_panel(panel):
    return hooks.register(UNIT_PANELS, panel)


def add_person_panel(panel):
    return hooks.register(PERSON_PANELS, panel)


def add_messaging_provider(provider_class):
    """An SMS or email provider, chosen with METRA_SMS_PROVIDER by its ``name``."""
    return registry.register(provider_class)


@dataclass
class SettingsLink:
    """A link on the Settings page to a plugin's own settings or tools."""

    label: str
    url_name: str
    permission: str = ""
    description: str = ""


def add_settings_link(link):
    return hooks.register(SETTINGS_LINKS, link)
