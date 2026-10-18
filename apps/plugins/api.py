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

Records: Metra's models, forms and helpers a plugin may use, such as
``api.Unit`` or ``api.PersonForm`` (see RECORDS below). They are loaded on
first use, so import this module freely; use them once apps are loaded (in
``ready()``, views, serializers), not at the top of a plugin's models.py.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import import_module

from apps.messaging.registry import EMAIL, SMS, Provider, ProviderError, SendResult, registry

from . import events
from .hooks import NAVIGATION, PERSON_PANELS, SETTINGS_LINKS, UNIT_PANELS, hooks
from .roles import grant_to_roles

API_VERSION = 1

# Records: name -> module. A plugin reads and changes Metra's data through
# these, so it never imports app modules whose layout may change.
RECORDS = {
    # The register (apps/register/models.py)
    "Tag": "apps.register.models",
    "UnitType": "apps.register.models",
    "CustomField": "apps.register.models",
    "Unit": "apps.register.models",
    "Person": "apps.register.models",
    "UnitContact": "apps.register.models",
    # The forms staff use. Validate data from outside through them, so a
    # plugin cannot store what the web pages would refuse, custom fields
    # included. UnitForm(data, instance=..., unit_type=...), PersonForm(data,
    # instance=...), UnitContactForm(data, unit=...), ReadingForm(data,
    # instance=..., round_=..., unit=...).
    "UnitForm": "apps.register.forms",
    "PersonForm": "apps.register.forms",
    "UnitContactForm": "apps.register.forms",
    "ReadingForm": "apps.readings.forms",
    # log_view(obj): record in the audit log that the current user opened a
    # unit or person, as the detail pages do.
    "log_view": "apps.register.history",
    # Readings (apps/readings/models.py)
    "ReadingType": "apps.readings.models",
    "ReadingRound": "apps.readings.models",
    "Reading": "apps.readings.models",
    # Invoicing (apps/invoicing/models.py). Issued invoices and payments
    # never change: read them, do not edit them.
    "Invoice": "apps.invoicing.models",
    "InvoiceLine": "apps.invoicing.models",
    "Payment": "apps.invoicing.models",
}


def __getattr__(name):
    """Load a record (see RECORDS) on first use, avoiding import cycles."""
    if name in RECORDS:
        value = getattr(import_module(RECORDS[name]), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
    *RECORDS,
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
