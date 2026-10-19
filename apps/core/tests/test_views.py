import tomllib

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_healthz_reports_ok(client):
    response = client.get(reverse("core:healthz"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_signed_in_users_see_the_version_in_the_account_menu(board_client, settings):
    settings.METRA_VERSION = "1.2.3"

    page = board_client.get(reverse("register:unit_list")).content.decode()

    assert "Metra 1.2.3" in page


def test_the_version_comes_from_pyproject(settings):
    with open(settings.BASE_DIR / "pyproject.toml", "rb") as f:
        assert settings.METRA_VERSION == tomllib.load(f)["project"]["version"]


def test_home_defaults_to_swedish(client):
    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    assert "Välkommen" in response.content.decode()


def test_home_follows_browser_language(client):
    response = client.get(reverse("core:home"), HTTP_ACCEPT_LANGUAGE="en")

    assert "Welcome" in response.content.decode()


def test_language_switch_remembers_choice(client):
    client.post(reverse("set_language"), {"language": "en", "next": "/"})

    response = client.get(reverse("core:home"))

    assert "Welcome" in response.content.decode()
