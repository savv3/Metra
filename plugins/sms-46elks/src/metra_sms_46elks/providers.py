"""SMS through 46elks (https://46elks.com), a Swedish provider."""

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.urls import reverse
from django.utils.crypto import salted_hmac

from apps.plugins import api

API_URL = "https://api.46elks.com/a1/sms"
# The plugin's name in METRA_PLUGINS and under Settings > Add-ons.
NAME = "46elks"


def config():
    """The plugin's settings: from its settings page under Settings > Add-ons,
    or from the environment (METRA_ELKS_*, METRA_SMS_SENDER), which wins."""
    values = api.plugin_settings(NAME)
    return {
        "api_user": values.get("api_user") or "",
        "api_password": values.get("api_password") or "",
        "sender": values.get("sender") or api.sms_sender(),
        "dry_run": bool(values.get("dry_run")),
    }


def callback_secret():
    """Part of the delivery-report address, so only 46elks (who knows it) can post there."""
    return salted_hmac("metra.messaging.46elks", "delivery").hexdigest()[:32]


class FortySixElks(api.Provider):
    channel = api.SMS
    name = "46elks"

    @classmethod
    def is_configured(cls):
        settings_ = config()
        return bool(settings_["api_user"] and settings_["api_password"])

    def sender(self):
        return config()["sender"]

    def delivery_callback_url(self):
        # 46elks can only report to a public HTTPS address.
        if not settings.BASE_URL.startswith("https://"):
            return None
        return settings.BASE_URL + reverse("metra_sms_46elks:delivery", args=[callback_secret()])

    def send(self, recipient, body, subject="", callback_url=None, headers=None):
        settings_ = config()
        if not (settings_["api_user"] and settings_["api_password"]):
            raise api.ProviderError(
                "Enter the 46elks API user and password under Settings > Add-ons > 46elks SMS."
            )
        data = {
            "from": settings_["sender"],
            "to": api.normalise_phone(recipient),
            "message": body,
        }
        if callback_url:
            data["whendelivered"] = callback_url
        if settings_["dry_run"]:
            data["dryrun"] = "yes"
        credentials = f"{settings_['api_user']}:{settings_['api_password']}"
        request = urllib.request.Request(
            API_URL,
            data=urllib.parse.urlencode(data).encode(),
            headers={"Authorization": "Basic " + base64.b64encode(credentials.encode()).decode()},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read(300).decode(errors="replace")
            raise api.ProviderError(f"46elks: {error.code} {detail}") from error
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            raise api.ProviderError(f"46elks: {error}") from error
        return api.SendResult(provider_id=payload.get("id", ""))
