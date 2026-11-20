import os

import pytest
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.backups import restore
from apps.messaging.email_config import current
from apps.messaging.registry import EMAIL, SMS, provider_for
from apps.register.models import Unit
from apps.setup import demo
from apps.setup.tasks import nightly_demo_reset


@pytest.fixture
def demo_site(settings, tmp_path):
    settings.DEMO = True
    settings.REQUIRE_MFA = False
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.BACKUP = {**settings.BACKUP, "dir": tmp_path / "snapshots"}
    settings.DATA_DIR = tmp_path
    ContentType.objects.clear_cache()  # other tests may have replaced the database
    return settings


@pytest.mark.django_db
def test_reset_refuses_on_a_real_install(make_user):
    make_user("kept")
    with pytest.raises(CommandError, match="METRA_DEMO is off"):
        call_command("reset_demo")
    assert User.objects.filter(username="kept").exists()


@pytest.mark.django_db
def test_on_start_does_nothing_on_a_real_install():
    call_command("reset_demo", "--if-new")
    assert not Unit.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_reset_replaces_everything_with_demo_data(demo_site, make_user):
    make_user("visitor")
    upload = demo_site.MEDIA_ROOT / "uploaded.pdf"
    upload.parent.mkdir(parents=True)
    upload.write_bytes(b"%PDF")

    call_command("reset_demo")

    assert not User.objects.filter(username="visitor").exists()
    account = User.objects.get(username="demo")
    assert account.check_password("demo")
    assert account.is_staff
    assert account.groups.filter(name="Admin").exists()
    assert Unit.objects.count() == 15
    assert not upload.exists()
    assert not restore.in_maintenance()
    assert demo.reset_marker().exists()

    # The nightly task does the same, and the reset can run again and again.
    nightly_demo_reset.call_local()
    assert User.objects.filter(username="demo").count() == 1
    assert Unit.objects.count() == 15


@pytest.mark.django_db(transaction=True)
def test_on_start_fills_a_new_demo_site_once(demo_site, make_user):
    call_command("reset_demo", "--if-new")
    assert demo.has_demo_account()
    make_user("visitor")

    call_command("reset_demo", "--if-new")
    assert User.objects.filter(username="visitor").exists()


@pytest.mark.django_db
def test_demo_site_sends_nothing(demo_site):
    assert provider_for(SMS) is None
    assert provider_for(EMAIL) is None
    assert current().provider == ""


@pytest.mark.django_db
def test_login_page_shows_the_demo_login(client, demo_site):
    response = client.get("/accounts/login/")
    assert b"<strong>demo</strong>" in response.content
    assert b"demo-banner" in response.content


@pytest.mark.django_db
def test_no_demo_hints_on_a_real_install(client):
    response = client.get("/accounts/login/")
    assert b"demo-login" not in response.content
    assert b"demo-banner" not in response.content


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path", ["/accounts/password/change/", "/accounts/2fa/totp/activate/", "/admin/auth/user/add/"]
)
def test_accounts_cannot_be_changed_on_a_demo_site(client, demo_site, path):
    demo.create_demo_account()
    client.login(username="demo", password="demo")

    response = client.post(path, {"oldpassword": "demo", "password1": "x", "password2": "x"})

    assert response.status_code == 302
    assert response["Location"] == "/account/"
    assert User.objects.get(username="demo").check_password("demo")
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_demo_account_can_use_the_app_without_two_factor(client, demo_site):
    demo.create_demo_account()
    client.login(username="demo", password="demo")
    response = client.get("/")
    assert response.status_code in (200, 302)
    assert "mfa" not in response.get("Location", "")


def test_web_processes_forget_cached_content_types_after_a_reset(demo_site, monkeypatch):
    cleared = []
    monkeypatch.setattr(ContentType.objects, "clear_cache", lambda: cleared.append(1))
    monkeypatch.setattr(demo, "_seen_reset", None)
    demo.reset_marker().touch()
    demo.forget_old_database()
    demo.forget_old_database()
    assert cleared == []

    stat = demo.reset_marker().stat()
    os.utime(demo.reset_marker(), ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    demo.forget_old_database()
    assert cleared == [1]
