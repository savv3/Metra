"""The built-in providers: email through Django, SMS through 46elks, and
console and dummy SMS providers for development and tests."""

import base64
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.mail.message import make_msgid
from django.urls import reverse
from django.utils.crypto import salted_hmac

from .registry import EMAIL, SMS, Provider, ProviderError, SendResult, registry

logger = logging.getLogger(__name__)


@registry.register
class DjangoEmail(Provider):
    """Email through Django's mail settings: SMTP (SCR_EMAIL_*) or the console."""

    channel = EMAIL
    name = "django"

    def send(self, recipient, body, subject="", callback_url=None, headers=None, attachments=None):
        message_id = make_msgid(domain=settings.MESSAGING["email_domain"])
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
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


def elks_callback_secret():
    """Part of the delivery-report address, so only 46elks (who knows it) can post there."""
    return salted_hmac("scr.messaging.46elks", "delivery").hexdigest()[:32]


@registry.register
class FortySixElks(Provider):
    """SMS through 46elks (https://46elks.com), a Swedish provider."""

    channel = SMS
    name = "46elks"
    api_url = "https://api.46elks.com/a1/sms"

    def delivery_callback_url(self):
        # 46elks can only report to a public HTTPS address.
        if not settings.BASE_URL.startswith("https://"):
            return None
        return settings.BASE_URL + reverse("messaging:elks_delivery", args=[elks_callback_secret()])

    def send(self, recipient, body, subject="", callback_url=None, headers=None):
        config = settings.MESSAGING
        if not (config["elks_api_user"] and config["elks_api_password"]):
            raise ProviderError("Set SCR_ELKS_API_USER and SCR_ELKS_API_PASSWORD.")
        data = {
            "from": config["sms_sender"],
            "to": normalise_phone(recipient, config["sms_country_code"]),
            "message": body,
        }
        if callback_url:
            data["whendelivered"] = callback_url
        if config["elks_dry_run"]:
            data["dryrun"] = "yes"
        credentials = f"{config['elks_api_user']}:{config['elks_api_password']}"
        request = urllib.request.Request(
            self.api_url,
            data=urllib.parse.urlencode(data).encode(),
            headers={"Authorization": "Basic " + base64.b64encode(credentials.encode()).decode()},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read(300).decode(errors="replace")
            raise ProviderError(f"46elks: {error.code} {detail}") from error
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            raise ProviderError(f"46elks: {error}") from error
        return SendResult(provider_id=payload.get("id", ""))


@registry.register
class ConsoleSMS(Provider):
    """Writes SMS to the log instead of sending them. For development."""

    channel = SMS
    name = "console"

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

    def send(self, recipient, body, subject="", callback_url=None, headers=None):
        if recipient.strip() == "+000":
            raise ProviderError("Dummy failure")
        outbox.append({"to": recipient, "body": body, "callback_url": callback_url})
        return SendResult(provider_id=f"dummy-{len(outbox)}")
