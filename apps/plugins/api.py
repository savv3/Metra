"""What plugins import. Everything here stays stable between releases with
the same API_VERSION; anything else in the app may change.

    from apps.plugins import api

    class MyConfig(AppConfig):
        name = "my_plugin"
        personal_data = []  # what personal data the plugin stores, see docs
        metra_api = [1]  # the API_VERSIONs the plugin works with
        metra_settings = [api.Setting("api_key", "API key", kind=api.Setting.SECRET)]

        def ready(self):
            api.add_navigation(api.NavItem("My page", "my_plugin:index", "register.view_unit"))
            api.add_unit_panel(api.Panel("my_plugin/panel.html", title="Mine"))
            api.add_messaging_provider(MySMSProvider)
            api.add_settings_link(api.SettingsLink("My settings", "my_plugin:settings",
                                                   group="organisation"))
            api.add_webhook_event(
                api.WebhookEvent("thing.saved", "A thing was saved", thing_saved, thing_payload)
            )
            api.add_notification_kind(
                api.NotificationKind("thing_failed", "A thing failed", "%(thing)s failed.",
                                     roles=["Admin"], permission="my_plugin.view_thing")
            )
            api.add_member_panel(api.MemberPanel("my_plugin/member.html", "Mine"))

    api.notify("thing_failed", {"thing": "Pump"}, link="/plugins/my_plugin/")
    key = api.plugin_settings("my_plugin").get("api_key")

Everything a plugin registers is left out while an admin has turned the
plugin off under Settings > Plugins (see apps/plugins/state.py).

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

from apps.core.pdf import PDFUnavailable
from apps.messaging.registry import (
    EMAIL,
    SEND_OUT_HEADER,
    SMS,
    Provider,
    ProviderError,
    SendResult,
    registry,
)
from apps.notifications.kinds import Kind as NotificationKind

from . import events
from .hooks import (
    HELP_ARTICLES,
    MEMBER_PANELS,
    NAVIGATION,
    PERSON_PANELS,
    SETTINGS_LINKS,
    UNIT_PANELS,
    WEBHOOK_EVENTS,
    hooks,
)
from .plugin_settings import PluginSettings, Setting
from .roles import grant_to_roles
from .state import calling_plugin

# Bump API_VERSION only for a breaking change; additions keep it. The previous
# version stays in SUPPORTED_API_VERSIONS for one more major release, so
# plugins have time to catch up. See docs/releasing.md.
API_VERSION = 1
SUPPORTED_API_VERSIONS = (1,)

# Records: name -> module. A plugin reads and changes Metra's data through
# these, so it never imports app modules whose layout may change.
RECORDS = {
    # The register (apps/register/models.py). Organisation.current() is the
    # organisation's own details (name, address, contact), or None.
    "Organisation": "apps.register.models",
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
    "HelpArticles",
    "SUPPORTED_API_VERSIONS",
    "EMAIL",
    "SMS",
    "MemberPanel",
    "NavItem",
    "PDFUnavailable",
    "Panel",
    "Provider",
    "ProviderError",
    "SendResult",
    "Setting",
    "SettingsLink",
    "SETTINGS_GROUPS",
    "WebhookEvent",
    "HelpArticles",
    "NotificationKind",
    "add_member_panel",
    "add_help_articles",
    "add_notification_kind",
    "add_messaging_provider",
    "add_navigation",
    "add_person_panel",
    "add_settings_link",
    "add_unit_panel",
    "add_webhook_event",
    "events",
    "grant_to_roles",
    *RECORDS,
    "member_link",
    "member_page_url",
    "member_response",
    "member_unavailable",
    "message_draft",
    "normalise_phone",
    "notify",
    "on_webhook_event",
    "plugin_settings",
    "record_delivery",
    "record_email_event",
    "email_from",
    "DELIVERED",
    "BOUNCED",
    "COMPLAINED",
    "SEND_OUT_HEADER",
    "render_pdf",
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
    """A link to a plugin's own settings or tools. It shows on the Settings
    page, in the section named by ``group`` (see SETTINGS_GROUPS), and on the
    plugin's page under Settings > Add-ons."""

    label: str
    url_name: str
    permission: str = ""
    description: str = ""
    group: str = "integrations"


# The sections of the Settings page a SettingsLink can go in. A link with
# another group goes under "integrations".
SETTINGS_GROUPS = (
    "organisation",
    "register",
    "readings",
    "invoicing",
    "messages",
    "users",
    "integrations",
    "backups",
)


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


def webhook_events(everything=False):
    """The registered ``WebhookEvent``s of plugins that are on, for plugins
    that send webhooks. ``everything=True`` includes those of plugins that are
    off, for connecting receivers at startup (receivers of a plugin that is
    off are skipped when an event is sent)."""
    return hooks.get(WEBHOOK_EVENTS, everything=everything)


def on_webhook_event(listener):
    """Call ``listener(event)`` for each ``WebhookEvent`` registered from now on,
    so a sender of webhooks also sees events of plugins that load after it."""
    hooks.subscribe(WEBHOOK_EVENTS, listener)


def plugin_settings(name=None):
    """The settings a plugin lists in ``metra_settings`` on its AppConfig, as
    an object whose ``get(key)`` gives the environment's value, else the one
    saved on the plugin's settings page, else the default. ``name`` is the
    plugin's name; by default the calling plugin's."""
    return PluginSettings(name or calling_plugin())


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


# What an email provider reports about an email (see record_email_event).
DELIVERED = "delivered"
BOUNCED = "bounced"
COMPLAINED = "complained"
# SEND_OUT_HEADER, imported above, carries a send-out's id on its email; a
# provider may turn it into a tag of its own (see the Mailgun plugin).


def record_email_event(provider, provider_id, event, reason=""):
    """An email provider reported ``event`` (DELIVERED, BOUNCED or
    COMPLAINED) for the email it calls ``provider_id``. A bounce marks the
    message failed and flags the person's address; a complaint is noted on
    the message. For a provider plugin's webhook view; unknown ids are ignored."""
    from apps.messaging.delivery_reports import record_email

    return record_email(provider, provider_id, event, reason)


def email_from():
    """(from address, Reply-To address or "") of the installation's email,
    from Settings > Email or METRA_EMAIL_FROM and METRA_EMAIL_REPLY_TO."""
    from apps.messaging.email_config import current

    config = current()
    return config.from_email, config.reply_to


# PDFs.


def render_pdf(html):
    """PDF bytes for an HTML document (a full page, with its CSS inline and
    images as data: URIs), made with WeasyPrint. Raises ``PDFUnavailable``
    when WeasyPrint or its Pango library is missing."""
    from apps.core.pdf import html_to_pdf

    return html_to_pdf(html)


# Messages.


def message_draft(request, subject, body, files=(), email_body=""):
    """The address of the New message form, filled in for the current user
    with ``subject``, ``body`` (the SMS text, and the email's unless
    ``email_body`` is given) and ``files``, a list of (filename, bytes,
    mimetype) attached and ticked. Staff then choose the recipients, check
    and send as usual. Redirect to it. Opening the form needs the
    ``messaging.send_broadcast`` permission, so show the button only to users
    with it. Raises django.core.exceptions.ValidationError for a file that
    cannot be attached (type or size)."""
    from apps.messaging.drafts import create

    return create(request, subject, body, files=files, email_body=email_body)


# The member page behind personal links.


@dataclass
class MemberPanel:
    """A section on the member page, the page members open with their personal
    link. The template gets ``unit``, ``person``, ``token`` (for links to the
    plugin's member views), ``title``, ``request`` and whatever
    ``context(request, member_link)`` returns. No permission applies: members
    are not users, so show only what the member may see."""

    template: str
    title: str = ""
    context: Callable | None = field(default=None)


def add_member_panel(panel):
    return hooks.register(MEMBER_PANELS, panel)


def member_link(request, token):
    """For a plugin's own member views, such as a file download under the
    personal link: an object with ``unit``, ``person``, ``token`` and
    ``log_access(request, obj)``, or None for an unknown, expired or revoked
    token or too many tries (it counts against the member page's rate limit).
    Answer None with ``member_unavailable(request)`` and wrap every other
    response in ``member_response``."""
    from apps.selfservice.public import member_link

    return member_link(request, token)


def member_unavailable(request):
    """The member pages' answer for a link that does not work."""
    from apps.selfservice.public import member_unavailable

    return member_unavailable(request)


def member_response(response):
    """``response`` with the member pages' privacy headers (not cached, not
    indexed, no referrer to other sites)."""
    from apps.selfservice.public import member_response

    return member_response(response)


def member_page_url(token):
    """The full address of the member page for a personal link's token."""
    from apps.selfservice.public import member_page_url

    return member_page_url(token)


@dataclass
class HelpArticles:
    """A plugin's help articles: ``folder`` holds ``<language>/<slug>.md`` files
    (Markdown, starting with ``# Title``), ``order`` lists the slugs in the
    order the help index shows them, and ``pages`` maps the plugin's URL
    namespaces to the article its pages' Help link opens."""

    folder: str
    order: list = field(default_factory=list)
    pages: dict = field(default_factory=dict)


def add_help_articles(articles):
    return hooks.register(HELP_ARTICLES, articles)


# Notifications under the bell (apps/notifications). NotificationKind is
# documented in apps/notifications/kinds.py and docs/plugins.md.


def add_notification_kind(kind):
    """A kind of notification the plugin sends, shown on each user's
    notification settings page."""
    from apps.notifications import kinds

    return kinds.register(kind)


def notify(kind, params=None, link="", users=(), roles=(), group=""):
    """Notify staff about ``kind`` (a registered kind's name), once the current
    transaction commits. ``params`` fill the kind's message; keep them to
    counts and technical facts, never members' personal data. ``link`` is a
    path on this site. With no ``users`` or ``roles``, the kind's roles get it.
    A ``group`` joins it to an unread notification of the same kind and group
    from the last 24 hours. Never raises."""
    from apps.notifications.service import notify as send

    return send(kind, params, link=link, users=users, roles=roles, group=group)
