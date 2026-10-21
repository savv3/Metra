import pytest
from django.core import mail
from django.core.mail import send_mail
from django.urls import reverse

from apps.messaging import email_config
from apps.messaging.models import EmailSettings
from apps.messaging.providers import DjangoEmail
from apps.messaging.registry import EMAIL, Provider, SendResult, provider_for, registry

URL = reverse("messaging:email_settings")
SMTP = {
    "provider": "smtp",
    "host": "smtp.example.fi",
    "port": "587",
    "security": "tls",
    "user": "styrelsen@example.fi",
    "password": "s3cret",
    "from_email": "styrelsen@example.fi",
    "reply_to": "ordforande@example.fi",
}


@pytest.fixture(autouse=True)
def page_decides(settings, monkeypatch):
    """The environment sets nothing, so the Email settings page decides."""
    settings.MESSAGING = {**settings.MESSAGING, "email_provider": None}
    settings.LANGUAGE_CODE = "en"
    for variable in [*email_config.ENVIRONMENT.values(), *email_config.SECURITY_ENVIRONMENT]:
        monkeypatch.delenv(variable, raising=False)


@pytest.fixture
def admin(role_client):
    return role_client("Admin")


def test_email_is_off_until_set_up_except_in_development(db, settings):
    settings.DEBUG = False
    assert provider_for(EMAIL) is None

    settings.DEBUG = True
    config = email_config.current()
    assert (config.provider, config.transport) == ("django", "console")


def test_admin_sets_up_smtp(admin, db):
    response = admin.post(URL, SMTP, follow=True)

    assert "Saved the email settings." in response.content.decode()
    saved = EmailSettings.objects.get()
    assert saved.provider == "smtp"
    assert "s3cret" not in saved.password
    config = email_config.current()
    assert (config.provider, config.transport, config.host) == ("django", "smtp", "smtp.example.fi")
    assert config.password == "s3cret"
    assert isinstance(provider_for(EMAIL), DjangoEmail)


def test_messages_use_the_from_and_reply_to_addresses(admin, db):
    admin.post(URL, SMTP)

    provider_for(EMAIL).send("anna@example.com", "Hej", subject="Test")

    sent = mail.outbox[-1]
    assert sent.from_email == "styrelsen@example.fi"
    assert sent.reply_to == ["ordforande@example.fi"]
    assert "@example.fi>" in sent.extra_headers["Message-ID"]


def test_the_password_is_never_shown_and_kept_when_left_empty(admin, db):
    admin.post(URL, SMTP)

    page = admin.get(URL).content.decode()
    admin.post(URL, {**SMTP, "password": "", "host": "smtp2.example.fi"})

    assert "s3cret" not in page
    assert EmailSettings.objects.get().password not in page
    assert "A password is saved. Leave this empty to keep it." in page
    assert email_config.current().password == "s3cret"
    assert email_config.current().host == "smtp2.example.fi"

    admin.post(URL, {**SMTP, "password": "", "clear_password": "on"})
    assert email_config.current().password == ""


def test_smtp_needs_a_server_and_a_from_address(admin, db):
    response = admin.post(URL, {**SMTP, "host": "", "from_email": ""})

    page = response.content.decode()
    assert "Enter the mail server to send through SMTP." in page
    assert "Enter the address email is sent from." in page
    assert not EmailSettings.objects.exists()


def test_the_environment_wins_and_locks_the_field(admin, settings, monkeypatch, db):
    admin.post(URL, SMTP)
    monkeypatch.setenv("METRA_EMAIL_FROM", "noreply@example.org")
    settings.MESSAGING = {**settings.MESSAGING, "email_provider": "django"}

    page = admin.get(URL).content.decode()
    admin.post(URL, {**SMTP, "provider": "none", "from_email": "other@example.fi"})

    assert "Set in the server environment (METRA_EMAIL_FROM)" in page
    config = email_config.current()
    assert config.from_email == "noreply@example.org"
    assert config.provider == "django"
    assert EmailSettings.objects.get().from_email == "styrelsen@example.fi"


def test_the_test_button_sends_a_test_email(admin, db):
    admin.post(URL, SMTP)

    response = admin.post(URL, {"action": "test", "to": "me@example.com"}, follow=True)

    assert "Test sent to me@example.com." in response.content.decode()
    assert mail.outbox[-1].to == ["me@example.com"]


def test_only_admins_change_email_settings(role_client, db):
    for role in ["Board", "Treasurer", "Read-only"]:
        assert role_client(role).get(URL).status_code == 403


# The app's own mail (login codes, invitations) goes the same way.


@pytest.fixture
def configured_backend(settings, monkeypatch):
    settings.EMAIL_BACKEND = "apps.messaging.email_config.ConfiguredBackend"
    # SMTP is replaced with the test outbox.
    monkeypatch.setitem(
        email_config.TRANSPORTS, "smtp", "django.core.mail.backends.locmem.EmailBackend"
    )


def test_system_mail_goes_through_smtp_with_the_from_address(admin, configured_backend, db):
    admin.post(URL, SMTP)
    mail.outbox.clear()

    send_mail("Your code", "123456", None, ["anna@example.com"])

    assert mail.outbox[0].from_email == "styrelsen@example.fi"
    assert mail.outbox[0].reply_to == ["ordforande@example.fi"]


def test_system_mail_is_dropped_when_email_is_not_set_up(configured_backend, settings, db):
    settings.DEBUG = False

    assert send_mail("Your code", "123456", None, ["anna@example.com"]) == 0
    assert mail.outbox == []


class Postbox(Provider):
    channel = EMAIL
    name = "test-postbox"
    description = "Test postbox"
    sent = []

    def send(self, recipient, body, subject="", callback_url=None, headers=None, attachments=None):
        self.sent.append((recipient, subject, body))
        return SendResult()


@pytest.fixture
def postbox():
    registry.register(Postbox)
    Postbox.sent.clear()
    yield Postbox
    registry._providers[EMAIL].pop(Postbox.name)


def test_an_add_on_provider_can_be_chosen_for_all_email(admin, postbox, configured_backend, db):
    page = admin.get(URL).content.decode()
    admin.post(URL, {**SMTP, "provider": "test-postbox", "host": ""})

    send_mail("Your code", "123456", None, ["anna@example.com"])
    provider_for(EMAIL).send("bo@example.com", "Hej", subject="Nyheter")

    assert "Test postbox" in page
    assert Postbox.sent == [
        ("anna@example.com", "Your code", "123456"),
        ("bo@example.com", "Nyheter", "Hej"),
    ]


def test_email_is_not_set_up_while_the_chosen_add_on_is_gone(admin, postbox, db):
    admin.post(URL, {**SMTP, "provider": "test-postbox", "host": ""})
    registry._providers[EMAIL].pop(Postbox.name)

    try:
        assert provider_for(EMAIL) is None
    finally:
        registry.register(Postbox)
