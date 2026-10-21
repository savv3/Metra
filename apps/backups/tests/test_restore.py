"""Restoring a snapshot from the Backups page."""

import sqlite3

import pytest
from django.conf import settings
from django.db import connection
from django.urls import reverse

from apps.backups import archive, restore, service
from apps.backups.models import BackupRun, Restore
from apps.register.models import Unit

pytestmark = pytest.mark.django_db


def copy_of_test_database(path):
    """A file copy of the (in-memory) test database, as it is now."""
    # The online backup cannot copy a database inside the test's open
    # transaction; a dump through the same connection can.
    connection.ensure_connection()
    target = sqlite3.connect(path)
    target.executescript("\n".join(connection.connection.iterdump()))
    target.close()
    return path


@pytest.fixture
def snapshot_of_now(tmp_path, monkeypatch):
    """Take a snapshot of the test database as it is at this moment."""

    def take(trigger=BackupRun.Trigger.MANUAL, version=None):
        source = copy_of_test_database(tmp_path / f"copy-{trigger}.sqlite3")
        monkeypatch.setattr(service, "database_path", lambda: source)
        if version:
            monkeypatch.setattr(settings, "METRA_VERSION", version)
        path, _run = service.take_snapshot(trigger)
        # Restores write to this file, never to the test database.
        target = tmp_path / "live.sqlite3"
        sqlite3.connect(target).close()
        monkeypatch.setattr(service, "database_path", lambda: target)
        return path

    return take


def reauthenticated(role_client, role="Admin"):
    client = role_client(role)
    client.post(reverse("account_reauthenticate"), {"password": "pw"})
    return client


def test_the_preview_counts_what_the_restore_would_remove(snapshot_of_now, household):
    Unit.objects.create(unit_type=household, name="Kept")
    path = snapshot_of_now()
    Unit.objects.create(unit_type=household, name="Added later")

    preview = restore.inspect(path.name)

    units = next(c for c in preview.counts if c.label == "units")
    assert (units.now, units.then, units.removed) == (2, 1, 1)
    assert not preview.needs_bookkeeping_confirmation


def test_a_snapshot_from_a_newer_version_is_refused(snapshot_of_now, monkeypatch):
    path = snapshot_of_now(version="99.0.0")
    monkeypatch.setattr(settings, "METRA_VERSION", "0.2.0")

    from django.utils import translation

    with translation.override("en"), pytest.raises(restore.RestoreError, match="newer"):
        restore.inspect(path.name)


def test_an_offsite_snapshot_is_downloaded_first(snapshot_of_now, monkeypatch, tmp_path):
    path = snapshot_of_now()
    offsite = tmp_path / "offsite"
    offsite.mkdir()
    path.rename(offsite / path.name)

    class Offsite:
        def list(self):
            return [path.name]

        def download(self, name, destination):
            destination.write_bytes((offsite / name).read_bytes())

    monkeypatch.setattr(service, "remote", lambda runner=None: Offsite())

    restore.inspect(path.name)

    assert (settings.BACKUP["dir"] / path.name).is_file()


def test_run_replaces_the_data_and_records_the_restore(snapshot_of_now, household, tmp_path):
    Unit.objects.create(unit_type=household, name="In the snapshot")
    path = snapshot_of_now()
    restore.maintenance_path().write_text("{}")

    assert restore.run(path.name, path.name, "admin")

    live = sqlite3.connect(service.database_path())
    names = [row[0] for row in live.execute("SELECT name FROM register_unit")]
    live.close()
    assert names == ["In the snapshot"]
    record = Restore.objects.get()
    assert record.success and record.requested_by == "admin"
    assert not restore.in_maintenance()


def test_a_failed_restore_puts_the_safety_snapshot_back(snapshot_of_now, tmp_path):
    safety = snapshot_of_now(BackupRun.Trigger.RESTORE)
    broken = settings.BACKUP["dir"] / "metra-snapshot-20261001-023000-manual-0.1.0.tar.gz"
    broken.write_bytes(b"not a snapshot")
    restore.maintenance_path().write_text("{}")

    assert not restore.run(broken.name, safety.name, "admin")

    record = Restore.objects.get()
    assert not record.success and record.error
    assert not restore.in_maintenance()


def test_restoring_needs_a_fresh_login_check(role_client, snapshot_of_now):
    path = snapshot_of_now()
    client = role_client("Admin")

    response = client.get(reverse("backups:restore", args=[path.name]))

    assert response.status_code == 302
    assert response.url.startswith(reverse("account_reauthenticate"))


def test_an_admin_restores_from_the_backups_page(role_client, snapshot_of_now, household):
    Unit.objects.create(unit_type=household, name="Before")
    path = snapshot_of_now()
    client = reauthenticated(role_client)
    url = reverse("backups:restore", args=[path.name])

    page = client.get(url, HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert "Everything added or changed since" in page

    client.post(url)  # not confirmed: nothing happens
    assert not Restore.objects.exists()

    response = client.post(url, {"confirm": "1"})

    assert response.status_code == 302
    assert Restore.objects.get().success
    triggers = [
        archive.parse_name(p.name).trigger for p in archive.local_archives(settings.BACKUP["dir"])
    ]
    assert "restore" in triggers  # the safety snapshot


def test_bookkeeping_since_the_snapshot_needs_an_extra_confirmation(
    role_client, snapshot_of_now, monkeypatch
):
    path = snapshot_of_now()
    monkeypatch.setattr(
        restore.Preview, "needs_bookkeeping_confirmation", property(lambda self: True)
    )
    client = reauthenticated(role_client)
    url = reverse("backups:restore", args=[path.name])

    client.post(url, {"confirm": "1"})
    assert not Restore.objects.exists()

    client.post(url, {"confirm": "1", "bookkeeping": "1"})
    assert Restore.objects.exists()


@pytest.mark.parametrize("role", ["Board", "Treasurer", "Read-only"])
def test_only_admins_restore(role_client, snapshot_of_now, role):
    path = snapshot_of_now()

    client = reauthenticated(role_client, role)

    assert client.get(reverse("backups:restore", args=[path.name])).status_code == 403
    assert (
        client.post(reverse("backups:restore", args=[path.name]), {"confirm": "1"}).status_code
        == 403
    )


def test_pages_say_back_soon_while_a_restore_runs(client):
    restore.maintenance_path().write_text("{}")
    try:
        response = client.get("/", HTTP_ACCEPT_LANGUAGE="en")
        assert response.status_code == 503
        assert "A snapshot is being restored" in response.content.decode()
        swedish = client.get("/", HTTP_ACCEPT_LANGUAGE="sv").content.decode()
        assert "En säkerhetskopia återställs" in swedish and 'lang="sv"' in swedish
        assert client.get("/" + settings.STATIC_URL.lstrip("/") + "css/app.css").status_code != 503
    finally:
        restore.maintenance_path().unlink()
    assert client.get("/").status_code == 200


def test_the_restore_command_refuses_a_newer_snapshot(snapshot_of_now, monkeypatch):
    from django.core.management import CommandError, call_command

    path = snapshot_of_now(version="99.0.0")
    monkeypatch.setattr(settings, "METRA_VERSION", "0.2.0")

    with pytest.raises(CommandError, match="newer"):
        call_command("restore", str(path), "--force", "--skip-snapshot")
