import pytest
from django.core import mail

from apps.messaging.models import Message
from apps.messaging.providers import DjangoEmail, normalise_phone
from apps.messaging.registry import AUTO, SMS, Provider, ProviderError, provider_for, registry


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


def test_email_provider_uses_django_mail(settings):
    settings.DEFAULT_FROM_EMAIL = "styrelsen@example.com"

    result = DjangoEmail().send("anna@example.com", "Text", subject="Ämne")

    assert mail.outbox[0].to == ["anna@example.com"]
    assert mail.outbox[0].from_email == "styrelsen@example.com"
    assert result.provider_id.startswith("<")


class ReadySMS(Provider):
    channel = SMS
    name = "ready-test"

    @classmethod
    def is_configured(cls):
        return True


def test_auto_picks_the_first_configured_sms_provider(settings):
    settings.MESSAGING = {**settings.MESSAGING, "sms_provider": AUTO}
    settings.DEBUG = False
    saved = dict(registry._providers[SMS])
    try:
        assert provider_for(SMS) is None  # nothing configured, not in development
        settings.DEBUG = True
        assert provider_for(SMS).name == "console"
        registry.register(ReadySMS)
        assert provider_for(SMS).name == "ready-test"
    finally:
        registry._providers[SMS] = saved


def test_none_turns_sms_off(settings):
    settings.MESSAGING = {**settings.MESSAGING, "sms_provider": "none"}

    assert provider_for(SMS) is None


def test_an_unknown_sms_provider_stops_startup(settings):
    from django.core.checks import run_checks

    settings.MESSAGING = {**settings.MESSAGING, "sms_provider": "gone"}

    assert "messaging.E001" in [message.id for message in run_checks()]


def test_delivery_reports_update_the_message(db):
    from apps.plugins import api

    message = Message.objects.create(
        channel="sms", provider="some-sms", provider_id="s1", status="sent"
    )

    assert api.record_delivery("some-sms", "s1", delivered=True) == 1
    assert api.record_delivery("other", "s1", delivered=False) == 0
    assert api.record_delivery("some-sms", "", delivered=False) == 0

    message.refresh_from_db()
    assert message.status == "delivered"
