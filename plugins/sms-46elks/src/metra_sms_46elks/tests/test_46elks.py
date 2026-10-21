import io
import json
import urllib.error
import urllib.parse

import pytest
from django.urls import reverse

from apps.plugins import api
from metra_sms_46elks.providers import FortySixElks, callback_secret


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def elks(monkeypatch, settings):
    monkeypatch.setenv("METRA_ELKS_API_USER", "u123")
    monkeypatch.setenv("METRA_ELKS_API_PASSWORD", "secret")
    monkeypatch.setenv("METRA_ELKS_DRY_RUN", "true")
    settings.MESSAGING = {**settings.MESSAGING, "sms_sender": "Vatten"}


def test_the_plugin_is_bundled_and_on():
    from django.apps import apps
    from django.conf import settings

    assert apps.is_installed("metra_sms_46elks")
    assert "46elks" in settings.PLUGINS


def test_posts_the_message(monkeypatch, elks):
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


def test_errors_become_provider_errors(monkeypatch, elks):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 403, "Forbidden", {}, io.BytesIO(b"Not enough credits")
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(api.ProviderError, match="Not enough credits"):
        FortySixElks().send("0401234567", "Hej")


def test_needs_credentials(monkeypatch):
    monkeypatch.delenv("METRA_ELKS_API_USER", raising=False)

    assert not FortySixElks.is_configured()
    with pytest.raises(api.ProviderError):
        FortySixElks().send("0401234567", "Hej")


def test_auto_uses_46elks_once_it_has_credentials(elks, settings, db):
    from apps.messaging.registry import SMS, provider_for

    settings.MESSAGING = {**settings.MESSAGING, "sms_provider": "auto"}

    assert FortySixElks.is_configured()
    assert provider_for(SMS).name == "46elks"


def test_callback_only_for_public_https(settings):
    settings.BASE_URL = "http://localhost:8000"
    assert FortySixElks().delivery_callback_url() is None
    settings.BASE_URL = "https://register.example.com"
    assert FortySixElks().delivery_callback_url() == (
        f"https://register.example.com/plugins/46elks/delivery/{callback_secret()}/"
    )


def test_delivery_report_updates_the_message(client, db):
    from apps.messaging.models import Message

    message = Message.objects.create(
        channel="sms", recipient="+358401", provider="46elks", provider_id="s1", status="sent"
    )
    url = reverse("metra_sms_46elks:delivery", args=[callback_secret()])

    response = client.post(url, {"id": "s1", "status": "delivered", "delivered": "1700000000"})

    message.refresh_from_db()
    assert response.status_code == 200
    assert message.status == "delivered"
    assert message.status_changed_at is not None


def test_delivery_report_with_wrong_secret_is_refused(client, db):
    from apps.messaging.models import Message

    message = Message.objects.create(channel="sms", provider="46elks", provider_id="s1")

    response = client.post(
        reverse("metra_sms_46elks:delivery", args=["wrong"]), {"id": "s1", "status": "failed"}
    )

    message.refresh_from_db()
    assert response.status_code == 404
    assert message.status == "queued"
