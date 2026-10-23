import tomllib

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


def test_healthz_reports_ok(client):
    response = client.get(reverse("core:healthz"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": settings.METRA_VERSION}


def test_status_does_not_exist_without_a_token(client, settings):
    settings.STATUS_TOKEN = ""

    assert client.get(reverse("core:status")).status_code == 404


def test_status_refuses_a_wrong_token(client, settings):
    settings.STATUS_TOKEN = "right"

    assert client.get(reverse("core:status")).status_code == 403
    response = client.get(reverse("core:status"), headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 403


def test_status_reports_version_backups_and_addons(client, settings, unit, make_user):
    from apps.backups.models import BackupRun

    settings.STATUS_TOKEN = "right"
    make_user("boss", "Admin", is_staff=True)
    BackupRun.objects.create(finished_at=timezone.now(), success=True)

    response = client.get(reverse("core:status"), headers={"Authorization": "Bearer right"})

    assert response.status_code == 200
    data = response.json()
    assert data["version"] == settings.METRA_VERSION
    assert data["units"] == 1
    assert data["staff_users"] == 1
    assert data["backup"]["last_succeeded"] is True
    assert data["backup"]["last_offsite_at"] is None
    assert set(data["addons"]) == set(settings.PLUGIN_APPS)


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
