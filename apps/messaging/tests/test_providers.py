import io
import json
import urllib.error
import urllib.parse

import pytest
from django.core import mail
from django.urls import reverse

from apps.messaging.models import Message
from apps.messaging.providers import (
    DjangoEmail,
    FortySixElks,
    elks_callback_secret,
    normalise_phone,
)
from apps.messaging.registry import ProviderError


@pytest.mark.parametrize(
    "number, expected",
    [
        ("040 123 4567", "+358401234567"),
        ("+358 40-123 4567", "+358401234567"),
        ("00358401234567", "+358401234567"),
        ("+46 70 123 45 67", "+46701234567"),
        ("358401234567", "+358401234567"),
    ],
)
def test_normalise_phone(number, expected):
    assert normalise_phone(number, "358") == expected


def test_normalise_phone_rejects_nonsense():
    with pytest.raises(ProviderError):
        normalise_phone("12", "358")


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def elks_settings(settings):
    settings.MESSAGING = {
        **settings.MESSAGING,
        "elks_api_user": "u123",
        "elks_api_password": "secret",
        "sms_sender": "Vatten",
        "elks_dry_run": True,
    }
    return settings


def test_46elks_posts_the_message(monkeypatch, elks_settings):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        return FakeResponse(json.dumps({"id": "s123", "status": "created"}).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = FortySixElks().send("040 1234567", "Hej", callback_url="https://x.test/cb/")

    sent = urllib.parse.parse_qs(calls[0].data.decode())
    assert calls[0].full_url == "https://api.46elks.com/a1/sms"
    assert calls[0].get_header("Authorization").startswith("Basic ")
    assert sent == {
        "from": ["Vatten"],
        "to": ["+358401234567"],
        "message": ["Hej"],
        "whendelivered": ["https://x.test/cb/"],
        "dryrun": ["yes"],
    }
    assert result.provider_id == "s123"


def test_46elks_errors_become_provider_errors(monkeypatch, elks_settings):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 403, "Forbidden", {}, io.BytesIO(b"Not enough credits")
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(ProviderError, match="Not enough credits"):
        FortySixElks().send("0401234567", "Hej")


def test_46elks_needs_credentials(settings):
    settings.MESSAGING = {**settings.MESSAGING, "elks_api_user": ""}

    with pytest.raises(ProviderError):
        FortySixElks().send("0401234567", "Hej")


def test_46elks_callback_only_for_public_https(settings):
    settings.BASE_URL = "http://localhost:8000"
    assert FortySixElks().delivery_callback_url() is None
    settings.BASE_URL = "https://register.example.com"
    assert (
        FortySixElks()
        .delivery_callback_url()
        .startswith("https://register.example.com/messaging/46elks/delivery/")
    )


def test_delivery_callback_updates_the_message(client, db):
    message = Message.objects.create(
        channel="sms", recipient="+358401", provider="46elks", provider_id="s1", status="sent"
    )
    url = reverse("messaging:elks_delivery", args=[elks_callback_secret()])

    response = client.post(url, {"id": "s1", "status": "delivered", "delivered": "1700000000"})

    message.refresh_from_db()
    assert response.status_code == 200
    assert message.status == "delivered"
    assert message.status_changed_at is not None


def test_delivery_callback_with_wrong_secret_is_refused(client, db):
    message = Message.objects.create(channel="sms", provider="46elks", provider_id="s1")

    response = client.post(
        reverse("messaging:elks_delivery", args=["wrong"]), {"id": "s1", "status": "failed"}
    )

    message.refresh_from_db()
    assert response.status_code == 404
    assert message.status == "queued"


def test_email_provider_uses_django_mail(settings):
    settings.DEFAULT_FROM_EMAIL = "styrelsen@example.com"

    result = DjangoEmail().send("anna@example.com", "Text", subject="Ämne")

    assert mail.outbox[0].to == ["anna@example.com"]
    assert mail.outbox[0].from_email == "styrelsen@example.com"
    assert result.provider_id.startswith("<")
