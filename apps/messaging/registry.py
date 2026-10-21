"""SMS and email providers, looked up by name.

An installation picks one provider per channel with a setting
(``METRA_SMS_PROVIDER``, ``METRA_EMAIL_BACKEND``). Providers register here
under a name, so another one (GatewayAPI, Sinch, a plugin's own) can be
added without touching the code that sends messages. With
``METRA_SMS_PROVIDER`` left at "auto", the first registered provider that
says it is configured is used, so installing a provider plugin and giving it
its settings is enough.
"""

from dataclasses import dataclass

from django.conf import settings

SMS = "sms"
EMAIL = "email"


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

    def delivery_callback_url(self):
        """Where the provider reports delivery, or None if it does not."""
        return None


class ProviderRegistry:
    def __init__(self):
        self._providers = {SMS: {}, EMAIL: {}}

    def register(self, provider_class):
        """Register a Provider subclass under its channel and name. Usable as a decorator."""
        if provider_class.channel not in self._providers:
            raise ValueError(f"Unknown channel {provider_class.channel!r}")
        self._providers[provider_class.channel][provider_class.name] = provider_class
        return provider_class

    def names(self, channel):
        return sorted(self._providers[channel])

    def get(self, channel, name):
        try:
            return self._providers[channel][name]()
        except KeyError:
            raise ProviderError(f"No {channel} provider called {name!r}") from None

    def configured(self, channel):
        """The first registered provider of the channel that is configured, or None."""
        for provider_class in self._providers[channel].values():
            if provider_class.is_configured():
                return provider_class()
        return None


registry = ProviderRegistry()

AUTO = "auto"


def provider_for(channel):
    """The installation's provider for a channel, or None when it is not set up."""
    name = settings.MESSAGING[f"{channel}_provider"]
    if name == AUTO:
        provider = registry.configured(channel)
        if provider is None and settings.DEBUG and channel == SMS:
            provider = registry.get(channel, "console")
        return provider
    return registry.get(channel, name) if name and name != "none" else None
