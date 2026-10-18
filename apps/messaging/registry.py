"""SMS and email providers, looked up by name.

An installation picks one provider per channel with a setting
(``SCR_SMS_PROVIDER``, ``SCR_EMAIL_BACKEND``). Providers register here
under a name, so another one (GatewayAPI, Sinch, a plugin's own) can be
added without touching the code that sends messages.
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

    def send(self, recipient, body, subject="", callback_url=None):
        """Send and return a SendResult, or raise ProviderError."""
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


registry = ProviderRegistry()


def provider_for(channel):
    """The installation's provider for a channel, or None when it is not set up."""
    name = settings.MESSAGING[f"{channel}_provider"]
    return registry.get(channel, name) if name else None
