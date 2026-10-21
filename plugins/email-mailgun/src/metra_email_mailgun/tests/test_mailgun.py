import base64
import hashlib
import hmac
import io
import json
from email import message_from_bytes

import pytest
from django.core import mail
from django.urls import reverse

from apps.messaging import email_config
from apps.messaging.models import EmailSettings, Message, MessageBatch
from apps.plugins import api
from metra_email_mailgun.providers import Mailgun

EVENTS = "/plugins/mailgun/events/"
SETTINGS = reverse("plugins:settings", args=["mailgun"])


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, settings):
    for name in ["DOMAIN", "API_KEY", "REGION", "WEBHOOK_KEY"]:
        monkeypatch.delenv(f"METRA_MAILGUN_{name}", raising=False)
    for variable in [*email_config.ENVIRONMENT.values(), *email_config.SECURITY_ENVIRONMENT]:
        monkeypatch.delenv(variable, raising=False)
    # The Email settings page decides, and all mail goes the way it says.
    settings.MESSAGING = {**settings.MESSAGING, "email_provider": None}
    settings.EMAIL_BACKEND = "apps.messaging.email_config.ConfiguredBackend"
    settings.LANGUAGE_CODE = "en"


@pytest.fixture
def mailgun(monkeypatch, db):
    monkeypatch.setenv("METRA_MAILGUN_DOMAIN", "mg.example.fi")
    monkeypatch.setenv("METRA_MAILGUN_API_KEY", "key-123")
    monkeypatch.setenv("METRA_MAILGUN_WEBHOOK_KEY", "signing-key")


@pytest.fixture
def posted(monkeypatch):
    """The requests sent to Mailgun, each as (url, headers, parsed form parts)."""
    calls = []

    def fake_urlopen(request, timeout):
        content_type = request.get_header("Content-type")
        raw = f"Content-Type: {content_type}\r\n\r\n".encode() + request.data
        parts = message_from_bytes(raw).get_payload()
        form = [(part.get_param("name", header="content-disposition"), part) for part in parts]
        calls.append((request.full_url, request, form))
        return FakeResponse(json.dumps({"id": f"<msg{len(calls)}@mg.example.fi>"}).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return calls


def text_fields(form):
    return [(name, part.get_payload(decode=True).decode()) for name, part in form]


def sign(payload, key="signing-key", timestamp="1700000000", token="abc"):
    signature = hmac.new(key.encode(), f"{timestamp}{token}".encode(), hashlib.sha256)
    return {
        "signature": {"timestamp": timestamp, "token": token, "signature": signature.hexdigest()},
        **payload,
    }


def event(client, kind, message_id, **data):
    payload = sign(
        {"event-data": {"event": kind, "message": {"headers": {"message-id": message_id}}, **data}}
    )
    return client.post(EVENTS, json.dumps(payload), content_type="application/json")


def test_the_plugin_is_bundled_and_on():
    from django.conf import settings

    assert "mailgun" in settings.PLUGINS


def test_sends_through_the_eu_region_with_attachments_and_headers(mailgun, posted, settings):
    EmailSettings.objects.create(from_email="vatten@example.fi", reply_to="styrelsen@example.fi")

    result = Mailgun().send(
        "anna@example.com",
        "Hej",
        subject="Nyhetsbrev",
        headers={"List-Unsubscribe": "<https://x.test/u/>", api.SEND_OUT_HEADER: "7"},
        attachments=[("faktura.pdf", b"%PDF-1", "application/pdf")],
    )

    url, request, form = posted[0]
    assert url == "https://api.eu.mailgun.net/v3/mg.example.fi/messages"
    assert (
        request.get_header("Authorization") == "Basic " + base64.b64encode(b"api:key-123").decode()
    )
    fields = text_fields([(n, p) for n, p in form if n != "attachment"])
    assert fields == [
        ("from", "vatten@example.fi"),
        ("to", "anna@example.com"),
        ("subject", "Nyhetsbrev"),
        ("text", "Hej"),
        ("h:Reply-To", "styrelsen@example.fi"),
        ("h:List-Unsubscribe", "<https://x.test/u/>"),
        ("o:tag", "send-out-7"),
    ]
    attachment = dict(form)["attachment"]
    assert attachment.get_filename() == "faktura.pdf"
    assert attachment.get_payload(decode=True) == b"%PDF-1"
    assert result.provider_id == "msg1@mg.example.fi"


def test_us_region(mailgun, posted, monkeypatch):
    monkeypatch.setenv("METRA_MAILGUN_REGION", "us")

    Mailgun().send("anna@example.com", "Hej")

    assert posted[0][0] == "https://api.mailgun.net/v3/mg.example.fi/messages"


def test_errors_become_provider_errors(mailgun, monkeypatch):
    import urllib.error

    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "No", {}, io.BytesIO(b"Forbidden"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(api.ProviderError, match="401 Forbidden"):
        Mailgun().send("anna@example.com", "Hej")


def test_needs_a_domain_and_key(db):
    assert not Mailgun.is_configured()
    with pytest.raises(api.ProviderError, match="Settings > Add-ons > Mailgun"):
        Mailgun().send("anna@example.com", "Hej")


def test_an_admin_sets_up_mailgun_and_login_mail_goes_through_it(role_client, posted):
    client = role_client("Admin")
    client.post(SETTINGS, {"domain": "mg.example.fi", "api_key": "key-9", "region": "eu"})
    client.post(
        reverse("messaging:email_settings"),
        {
            "action": "save",
            "provider": "mailgun",
            "from_email": "vatten@example.fi",
            "port": "587",
            "security": "tls",
        },
    )
    assert Mailgun.is_configured()

    mail.EmailMultiAlternatives(
        "Your code",
        "123456",
        to=["anna@example.com"],
        alternatives=[("<b>123456</b>", "text/html")],
    ).send()

    url, _request, form = posted[-1]
    assert url == "https://api.eu.mailgun.net/v3/mg.example.fi/messages.mime"
    assert text_fields([(n, p) for n, p in form if n == "to"]) == [("to", "anna@example.com")]
    sent = dict(form)["message"].as_bytes()
    assert b"From: vatten@example.fi" in sent
    assert b"text/html" in sent


def test_a_newsletter_goes_out_through_mailgun_and_a_bounce_shows(
    role_client, client, posted, mailgun
):
    admin_client = role_client("Admin")
    from apps.messaging.models import ConsentRecord
    from apps.register.models import Person

    EmailSettings.objects.create(provider="mailgun", from_email="vatten@example.fi")
    anna = Person.objects.create(first_name="Anna", email="anna@example.com")
    ConsentRecord.record(anna, True, ConsentRecord.Source.STAFF)

    data = {"subject": "Nytt", "body": "Hej!"}
    admin_client.post("/messages/newsletter/new/", {**data, "step": "preview"})
    admin_client.post("/messages/newsletter/new/", {**data, "step": "confirm"})

    batch = MessageBatch.objects.get()
    fields = dict(text_fields(posted[0][2]))
    assert fields["to"] == "anna@example.com"
    assert fields["o:tag"] == f"send-out-{batch.pk}"
    assert fields["h:List-Unsubscribe"].startswith("<https://")
    message = Message.objects.get(batch=batch)
    assert (message.provider, message.provider_id) == ("mailgun", "msg1@mg.example.fi")

    response = event(
        client,
        "failed",
        "msg1@mg.example.fi",
        severity="permanent",
        **{"delivery-status": {"description": "", "message": "550 No such user"}},
    )

    assert response.status_code == 200
    message.refresh_from_db()
    anna.refresh_from_db()
    assert message.status == Message.Status.FAILED
    assert message.error == "Bounced: 550 No such user"
    assert anna.email_bounced_at is not None
    assert anna.email_bounce_reason == "550 No such user"
    page = admin_client.get(anna.get_absolute_url(), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert "Bounced" in page
    assert "550 No such user" in page
    batch_page = admin_client.get(batch.get_absolute_url(), HTTP_ACCEPT_LANGUAGE="en")
    assert "Bounced: 550 No such user" in batch_page.content.decode()


def test_delivered_and_complained_are_recorded(client, mailgun, db):
    message = Message.objects.create(
        channel="email", provider="mailgun", provider_id="m1", status="sent"
    )

    event(client, "delivered", "m1")
    message.refresh_from_db()
    assert message.status == Message.Status.DELIVERED

    event(client, "complained", "m1")
    message.refresh_from_db()
    assert message.status == Message.Status.DELIVERED
    assert message.error == "The recipient marked this email as spam."


def test_temporary_failures_are_not_bounces(client, mailgun, db):
    message = Message.objects.create(
        channel="email", provider="mailgun", provider_id="m1", status="sent"
    )

    event(client, "failed", "m1", severity="temporary")

    message.refresh_from_db()
    assert message.status == Message.Status.SENT


def test_unsigned_events_are_refused(client, mailgun, db):
    message = Message.objects.create(
        channel="email", provider="mailgun", provider_id="m1", status="sent"
    )
    payload = sign(
        {"event-data": {"event": "delivered", "message": {"headers": {"message-id": "m1"}}}},
        key="wrong",
    )

    response = client.post(EVENTS, json.dumps(payload), content_type="application/json")

    assert response.status_code == 406
    message.refresh_from_db()
    assert message.status == Message.Status.SENT


def test_without_a_signing_key_events_are_refused(client, mailgun, monkeypatch, db):
    monkeypatch.delenv("METRA_MAILGUN_WEBHOOK_KEY")

    assert event(client, "delivered", "m1").status_code == 406
