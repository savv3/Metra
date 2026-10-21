"""SMS and email providers, looked up by name.

An installation picks one provider per channel with a setting
(``METRA_SMS_PROVIDER``; for email the Email settings page, see
email_config). Providers register here
under a name, so another one (GatewayAPI, Sinch, a plugin's own) can be
added without touching the code that sends messages. With
``METRA_SMS_PROVIDER`` left at "auto", the first registered provider that
says it is configured is used, so installing a provider plugin and giving it
its settings is enough.
"""

import inspect
from dataclasses import dataclass

from django.conf import settings

SMS = "sms"
EMAIL = "email"
# Email of a send-out carries its id in this header, so a provider can tag
# the messages (Mailgun's o:tag) and group their statistics by send-out.
SEND_OUT_HEADER = "X-Metra-Send-Out"


class ProviderError(Exception):
    """The provider refused or could not take the message. The text is shown to staff."""


@dataclass
class SendResult:
    provider_id: str = ""
    # "sent" when handed over; "delivered" if the provider already knows.
    status: str = "sent"


class Provider:
    """Sends one message. Subclasses set ``channel`` and ``name`` and implement ``send``."""

    channel = ""
    name = ""
    # The plugin that added the provider (set when it is registered), or None.
    plugin = None
    # A short human description for pages that show the provider; empty means
    # the name is shown. Translatable.
    description = ""

    @classmethod
    def label(cls):
        return str(cls.description or cls.name)

    @classmethod
    def is_configured(cls):
        """True when the provider has what it needs to send, so "auto" may pick it."""
        return False

    def send(self, recipient, body, subject="", callback_url=None, headers=None, attachments=None):
        """Send and return a SendResult, or raise ProviderError. Email providers
        add ``headers`` (e.g. List-Unsubscribe) and ``attachments`` ([(filename,
        bytes, mimetype)], e.g. an invoice PDF) to the message; SMS ignore them."""
        raise NotImplementedError

    def send_email_message(self, message):
        """Send a whole Django EmailMessage: the app's own mail, such as login
        codes, when this provider is the chosen email provider. By default
        each recipient gets the plain text; a provider that can send the
        message as it is (with its HTML part) overrides this."""
        attachments = [a for a in message.attachments if isinstance(a, tuple)]
        for recipient in message.recipients():
            self.send(
                recipient,
                message.body,
                subject=message.subject,
                headers=dict(message.extra_headers),
                attachments=attachments or None,
            )

    def sender(self):
        """The name or number an SMS is sent from; providers with their own
        setting override this."""
        return settings.MESSAGING["sms_sender"]

    def delivery_callback_url(self):
        """Where the provider reports delivery, or None if it does not."""
        return None


class ProviderRegistry:
    """Providers by channel and name. A provider a plugin added is left out
    while that plugin is turned off (see apps.plugins.state)."""

    def __init__(self):
        self._providers = {SMS: {}, EMAIL: {}}

    def register(self, provider_class):
        """Register a Provider subclass under its channel and name. Usable as a decorator."""
        from apps.plugins import state

        if provider_class.channel not in self._providers:
            raise ValueError(f"Unknown channel {provider_class.channel!r}")
        provider_class.plugin = state.owner_of(provider_class.__module__)
        self._providers[provider_class.channel][provider_class.name] = provider_class
        return provider_class

    def _available(self, channel):
        from apps.plugins import state

        return {
            name: provider_class
            for name, provider_class in self._providers[channel].items()
            if state.is_enabled(getattr(provider_class, "plugin", None))
        }

    def names(self, channel, everything=False):
        """The providers' names; with ``everything``, also those of plugins that are off."""
        return sorted(self._providers[channel] if everything else self._available(channel))

    def get(self, channel, name):
        try:
            return self._available(channel)[name]()
        except KeyError:
            raise ProviderError(f"No {channel} provider called {name!r}") from None

    def configured(self, channel):
        """The first registered provider of the channel that is configured, or None."""
        for provider_class in self._available(channel).values():
            if provider_class.is_configured():
                return provider_class()
        return None


registry = ProviderRegistry()


def email_headers(provider, batch, headers=None):
    """The ``headers`` argument for an email of a send-out: ``headers`` plus
    the send-out header. Empty for providers written before headers existed
    (e.g. in a plugin), which still work."""
    if "headers" not in inspect.signature(provider.send).parameters:
        return {}
    return {"headers": {**(headers or {}), SEND_OUT_HEADER: str(batch.pk)}}


AUTO = "auto"


def provider_for(channel):
    """The installation's provider for a channel, or None when it is not set up."""
    if channel == EMAIL:
        from .email_config import current

        name = current().provider
        if name and name not in registry.names(EMAIL):
            # The chosen add-on is off or gone: email is not set up for now.
            return None
        return registry.get(EMAIL, name) if name else None
    name = settings.MESSAGING[f"{channel}_provider"]
    if name == AUTO:
        provider = registry.configured(channel)
        if provider is None and settings.DEBUG and channel == SMS:
            provider = registry.get(channel, "console")
        return provider
    return registry.get(channel, name) if name and name != "none" else None
