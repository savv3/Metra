import json
import re
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.core import mail
from django.core.management import CommandError, call_command
from django.urls import reverse

from apps.register.models import Organisation

pytestmark = pytest.mark.django_db

User = get_user_model()
LINK = re.compile(r"https?://\S+/accounts/password/reset/key/\S+/")


@pytest.fixture
def admin_client(admin_client, monkeypatch):
    """The admin has set up two-factor login."""
    monkeypatch.setattr("apps.accounts.middleware.has_two_factor", lambda user: True)
    return admin_client


@pytest.fixture
def no_email(settings):
    settings.MESSAGING = {**settings.MESSAGING, "email_provider": ""}


def add_user(client, role="Admin", **data):
    values = {
        "first_name": "Bo",
        "last_name": "Berg",
        "email": "Bo@Example.org",
        "role": Group.objects.get(name=role).pk,
        **data,
    }
    return client.post(
        reverse("admin:auth_user_add"), values, follow=True, HTTP_ACCEPT_LANGUAGE="en"
    )


def texts(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


def test_the_add_user_page_asks_for_no_password(admin_client):
    page = admin_client.get(reverse("admin:auth_user_add")).content.decode()

    assert 'name="email"' in page and 'name="role"' in page
    assert "password1" not in page


def test_adding_a_user_emails_an_invitation(admin_client, client):
    Organisation.objects.create(name="Byns vatten")

    response = add_user(admin_client)

    user = User.objects.get(username="bo@example.org")
    assert user.email == "bo@example.org" and user.first_name == "Bo"
    assert user.is_staff and list(user.groups.values_list("name", flat=True)) == ["Admin"]
    assert not user.has_usable_password()
    [email] = mail.outbox
    assert email.to == ["bo@example.org"] and "Byns vatten" in email.subject
    assert "two-factor" in email.body
    assert any("Invitation sent" in text for text in texts(response))

    link = LINK.search(email.body).group(0)
    client.logout()
    page = client.get(link.split("testserver")[1], follow=True)
    assert b"password1" in page.content


def test_a_board_member_is_not_staff_and_not_told_about_two_factor(admin_client):
    add_user(admin_client, role="Board")

    user = User.objects.get(username="bo@example.org")
    assert not user.is_staff
    assert "two-factor" not in mail.outbox[0].body


def test_without_email_the_link_is_shown_once(admin_client, no_email):
    response = add_user(admin_client)

    assert User.objects.filter(username="bo@example.org").exists()
    assert not mail.outbox
    [warning] = [text for text in texts(response) if "Email is not set up" in text]
    assert LINK.search(warning)


def test_an_email_that_is_taken_is_refused(admin_client, make_user):
    make_user("bo@example.org")

    response = add_user(admin_client)

    assert response.context["adminform"].form.errors["email"]
    assert not mail.outbox


def test_sending_a_new_invitation(admin_client, make_user):
    waiting = User.objects.create(username="new@example.org", email="new@example.org")
    waiting.set_unusable_password()
    waiting.save()
    done = make_user("done@example.org", email="done@example.org")

    response = admin_client.post(
        reverse("admin:auth_user_changelist"),
        {"action": "send_invitation", "_selected_action": [waiting.pk, done.pk]},
        follow=True,
        HTTP_ACCEPT_LANGUAGE="en",
    )

    assert [email.to for email in mail.outbox] == [["new@example.org"]]
    assert any("already chosen a password" in text for text in texts(response))


def run(command, *args):
    out = StringIO()
    call_command(command, *args, stdout=out)
    return out.getvalue()


def test_create_organisation_can_email_the_link():
    result = json.loads(
        run(
            "create_organisation",
            "--name",
            "Klubben",
            "--admin-email",
            "a@example.org",
            "--send",
            "--json",
        )
    )

    assert result["sent"] is True
    [email] = mail.outbox
    assert email.to == ["a@example.org"] and result["link"] in email.body


def test_create_organisation_without_email_still_gives_the_link(no_email):
    result = json.loads(
        run(
            "create_organisation",
            "--name",
            "Klubben",
            "--admin-email",
            "a@example.org",
            "--send",
            "--json",
        )
    )

    assert result["sent"] is False and result["error"]
    assert result["link"] and not mail.outbox


def test_invite_user_makes_a_new_link_for_someone_still_waiting():
    run("create_organisation", "--name", "Klubben", "--admin-email", "a@example.org")

    result = json.loads(run("invite_user", "--email", "A@example.org", "--send", "--json"))

    assert result["sent"] is True and result["username"] == "a@example.org"
    assert result["link"] in mail.outbox[0].body


def test_invite_user_refuses_someone_with_a_password(make_user):
    make_user("a@example.org")

    with pytest.raises(CommandError, match="already chosen"):
        run("invite_user", "--email", "a@example.org")

    with pytest.raises(CommandError, match="no active user"):
        run("invite_user", "--email", "nobody@example.org")
