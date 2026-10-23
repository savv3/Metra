import json
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command

from apps.register.models import Organisation

pytestmark = pytest.mark.django_db


def run(*args):
    out = StringIO()
    call_command("create_organisation", *args, stdout=out)
    return out.getvalue()


def test_creates_the_organisation_and_an_admin_with_a_setup_link(client):
    out = run("--name", "Golfklubben", "--admin-email", "Anna@Example.org", "--json")

    result = json.loads(out)
    assert Organisation.current().name == "Golfklubben"
    user = get_user_model().objects.get(username="anna@example.org")
    assert user.is_staff
    assert not user.has_usable_password()
    assert user.groups.filter(name="Admin").exists()
    assert result["username"] == "anna@example.org"
    path = result["link"].split("://", 1)[1].split("/", 1)[1]
    response = client.get("/" + path, follow=True)
    assert response.status_code == 200
    assert response.context["form"] is not None


def test_refuses_an_install_that_already_has_an_admin(make_user):
    make_user("boss", "Admin", is_staff=True)

    with pytest.raises(CommandError):
        run("--name", "X", "--admin-email", "a@example.org")


def test_refuses_a_bad_email():
    with pytest.raises(CommandError):
        run("--name", "X", "--admin-email", "not-an-email")
