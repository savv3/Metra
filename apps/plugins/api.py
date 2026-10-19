"""What plugins import. Everything here stays stable between releases with
the same API_VERSION; anything else in the app may change.

    from apps.plugins import api

    class MyConfig(AppConfig):
        name = "my_plugin"
        personal_data = []  # what personal data the plugin stores, see docs
        metra_api = [1]  # the API_VERSIONs the plugin works with

        def ready(self):
            api.add_navigation(api.NavItem("My page", "my_plugin:index", "register.view_unit"))
            api.add_unit_panel(api.Panel("my_plugin/panel.html", title="Mine"))
            api.add_messaging_provider(MySMSProvider)
            api.add_settings_link(api.SettingsLink("My settings", "my_plugin:settings"))
            api.add_webhook_event(
                api.WebhookEvent("thing.saved", "A thing was saved", thing_saved, thing_payload)
            )

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

from django.dispatch import Signal

from apps.messaging.registry import EMAIL, SMS, Provider, ProviderError, SendResult, registry

from . import events
from .hooks import NAVIGATION, PERSON_PANELS, SETTINGS_LINKS, UNIT_PANELS, WEBHOOK_EVENTS, hooks
from .roles import grant_to_roles

# Bump API_VERSION only for a breaking change; additions keep it. The previous
# version stays in SUPPORTED_API_VERSIONS for one more major release, so
# plugins have time to catch up. See docs/releasing.md.
API_VERSION = 1
SUPPORTED_API_VERSIONS = (1,)

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
    "SUPPORTED_API_VERSIONS",
    "EMAIL",
    "SMS",
    "NavItem",
    "Panel",
    "Provider",
    "ProviderError",
    "SendResult",
    "SettingsLink",
    "WebhookEvent",
    "add_messaging_provider",
    "add_navigation",
    "add_person_panel",
    "add_settings_link",
    "add_unit_panel",
    "add_webhook_event",
    "events",
    "grant_to_roles",
    *RECORDS,
    "normalise_phone",
    "on_webhook_event",
    "record_delivery",
    "sms_country_code",
    "sms_sender",
    "webhook_events",
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


@dataclass
class WebhookEvent:
    """An event that webhook endpoints can subscribe to (see the webhooks plugin).

    ``name`` is what receivers see, like "invoice.issued"; ``label`` is shown to
    staff choosing events. ``signal`` is a Django signal, sent after the change
    is committed (see ``events.send_on_commit``). ``payload(**signal_kwargs)``
    returns the event's data as a JSON-serialisable dict. Webhooks go to
    outside systems, so return ids and non-personal facts only, never names,
    email addresses, phone numbers or addresses.
    """

    name: str
    label: str
    signal: Signal
    payload: Callable[..., dict]


def add_webhook_event(event):
    """Make an event available as a webhook. It works with any plugin that
    sends webhooks and does not depend on one."""
    return hooks.register(WEBHOOK_EVENTS, event)


def webhook_events():
    """Every registered ``WebhookEvent``. For plugins that send webhooks."""
    return hooks.get(WEBHOOK_EVENTS)


def on_webhook_event(listener):
    """Call ``listener(event)`` for each ``WebhookEvent`` registered from now on,
    so a sender of webhooks also sees events of plugins that load after it."""
    hooks.subscribe(WEBHOOK_EVENTS, listener)


# For SMS provider plugins.


def sms_sender():
    """The sender name or number SMS are sent from (METRA_SMS_SENDER)."""
    from django.conf import settings

    return settings.MESSAGING["sms_sender"]


def sms_country_code():
    """The country code for numbers written without one (METRA_SMS_COUNTRY_CODE)."""
    from django.conf import settings

    return settings.MESSAGING["sms_country_code"]


def normalise_phone(number, country_code=None):
    """+358401234567 from "040 123 4567" and the like; ProviderError if it is not a number."""
    from apps.messaging.providers import normalise_phone

    return normalise_phone(number, country_code or sms_country_code())


def record_delivery(provider, provider_id, delivered):
    """A provider reported whether the SMS it calls ``provider_id`` arrived.
    For a provider plugin's delivery-report view; unknown ids are ignored."""
    from apps.messaging.delivery_reports import record

    return record(provider, provider_id, delivered)
