"""The built-in providers: email through Django, and console and dummy SMS
providers for development and tests. Real SMS providers are plugins, such as
the bundled 46elks plugin in plugins/sms-46elks."""

import logging
import re

from django.core.mail import EmailMessage
from django.core.mail.message import make_msgid
from django.utils.translation import gettext_lazy as _

from . import email_config
from .registry import EMAIL, SMS, Provider, ProviderError, SendResult, registry

logger = logging.getLogger(__name__)


@registry.register
class DjangoEmail(Provider):
    """Email through Django's mail: SMTP or the console, as the email settings
    say (see apps.messaging.email_config)."""

    channel = EMAIL
    name = "django"
    description = _("SMTP (your own mail server or account)")

    def send(self, recipient, body, subject="", callback_url=None, headers=None, attachments=None):
        config = email_config.current()
        message_id = make_msgid(domain=config.domain)
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=config.from_email,
            to=[recipient],
            reply_to=[config.reply_to] if config.reply_to else None,
            headers={"Message-ID": message_id, **(headers or {})},
        )
        for filename, content, mimetype in attachments or []:
            email.attach(filename, content, mimetype)
        try:
            email.send()
        except Exception as error:  # smtplib and socket errors alike
            raise ProviderError(str(error)) from error
        return SendResult(provider_id=message_id)


def normalise_phone(number, country_code):
    """+358401234567 from "040 123 4567", "+358 40-123 4567" or "00358401234567"."""
    number = number.strip()
    digits = re.sub(r"\D", "", number)
    if number.startswith("+"):
        pass
    elif digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = country_code + digits[1:]
    elif not digits.startswith(country_code):
        digits = country_code + digits
    if not 8 <= len(digits) <= 15:
        raise ProviderError(f"Not a phone number: {number!r}")
    return "+" + digits


@registry.register
class ConsoleSMS(Provider):
    """Writes SMS to the log instead of sending them. For development."""

    channel = SMS
    name = "console"
    description = _("Shown in the server log (development)")

    def send(self, recipient, body, subject="", callback_url=None, headers=None):
        logger.warning("SMS to %s:\n%s", recipient, body)
        return SendResult()


# Messages the dummy provider "sent", for tests.
outbox = []


@registry.register
class DummySMS(Provider):
    """Keeps SMS in ``outbox`` instead of sending them. For tests."""

    channel = SMS
    name = "dummy"
    description = _("Kept in memory, nothing is sent (tests)")

    def send(self, recipient, body, subject="", callback_url=None, headers=None):
        if recipient.strip() == "+000":
            raise ProviderError("Dummy failure")
        outbox.append({"to": recipient, "body": body, "callback_url": callback_url})
        return SendResult(provider_id=f"dummy-{len(outbox)}")
