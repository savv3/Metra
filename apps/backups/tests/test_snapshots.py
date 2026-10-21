"""Snapshots before risky actions, and the Backups page."""

import pytest
from django.conf import settings
from django.core.management import call_command
from django.urls import reverse

from apps.backups import archive, service
from apps.backups.models import BackupRun
from apps.backups.tests.test_backups import REMOTE, FakeRclone
from apps.register.models import CustomField, Unit, UnitType
from apps.register.tests.test_csv import run_import

pytestmark = pytest.mark.django_db


def snapshots(trigger=None):
    names = [p.name for p in archive.local_archives(settings.BACKUP["dir"])]
    return [n for n in names if trigger is None or archive.parse_name(n).trigger == trigger]


@pytest.fixture
def broken_snapshots(monkeypatch, tmp_path):
    # A directory is no database, so every snapshot fails.
    monkeypatch.setattr(service, "database_path", lambda: tmp_path)


@pytest.fixture
def settings_admin(client, make_user, settings):
    """An admin who can open Settings (staff), with two-factor off for the test."""
    settings.REQUIRE_MFA = False
    client.force_login(make_user("root", "Admin", is_staff=True))
    return client


@pytest.fixture
def old_snapshot(tmp_path):
    """A snapshot file to restore from."""
    from apps.backups.tests.test_backups import make_database

    source = tmp_path / "source.sqlite3"
    make_database(source, rows=3).close()
    moment = archive.datetime.datetime(2026, 10, 1)
    return archive.create_archive(source, tmp_path / "none", tmp_path / "in", moment)


# Before risky actions


def test_a_csv_import_takes_a_snapshot_first(board_client, make_user):
    import io

    from django.core.management import call_command as call

    call("load_sample_setup", "water", stdout=io.StringIO())
    water = UnitType.objects.get(name="Hushåll")
    run_import(board_client, water, "Namn;Fastighetsbeteckning\nNy;1\n")

    board_client.post(reverse("register:unit_import_preview"))

    assert Unit.objects.filter(name="Ny").exists()
    assert len(snapshots("import")) == 1
    assert BackupRun.objects.get().started_by.username == "board"


def test_no_import_without_a_snapshot(board_client, broken_snapshots):
    import io

    from django.core.management import call_command as call

    call("load_sample_setup", "water", stdout=io.StringIO())
    water = UnitType.objects.get(name="Hushåll")
    run_import(board_client, water, "Namn;Fastighetsbeteckning\nNy;1\n")

    response = board_client.post(reverse("register:unit_import_preview"), HTTP_ACCEPT_LANGUAGE="en")

    assert not Unit.objects.filter(name="Ny").exists()
    assert "Nothing was imported" in response.content.decode()


def test_deleting_a_unit_type_takes_a_snapshot_first(settings_admin, household):
    url = reverse("admin:register_unittype_delete", args=[household.pk])

    settings_admin.post(url, {"post": "yes"})

    assert not UnitType.objects.filter(pk=household.pk).exists()
    assert len(snapshots("delete")) == 1


def test_no_unit_type_is_deleted_without_a_snapshot(settings_admin, household, broken_snapshots):
    url = reverse("admin:register_unittype_delete", args=[household.pk])

    settings_admin.post(url, {"post": "yes"})

    assert UnitType.objects.filter(pk=household.pk).exists()


def test_deleting_fields_from_the_list_takes_a_snapshot_first(settings_admin, household):
    field = household.custom_fields.first()
    url = reverse("admin:register_customfield_changelist")
    data = {"action": "delete_selected", "_selected_action": [field.pk]}

    settings_admin.post(url, data)  # the confirmation page: nothing yet
    assert snapshots() == []
    settings_admin.post(url, {**data, "post": "yes"})

    assert not CustomField.objects.filter(pk=field.pk).exists()
    assert len(snapshots("delete")) == 1


def test_no_fields_are_deleted_from_the_list_without_a_snapshot(
    settings_admin, household, broken_snapshots
):
    field = household.custom_fields.first()
    url = reverse("admin:register_customfield_changelist")

    settings_admin.post(
        url, {"action": "delete_selected", "_selected_action": [field.pk], "post": "yes"}
    )

    assert CustomField.objects.filter(pk=field.pk).exists()


def test_restore_takes_a_snapshot_of_the_current_data_first(tmp_path, make_user, monkeypatch):
    from apps.backups.tests.test_backups import make_database

    source = tmp_path / "source.sqlite3"
    make_database(source, rows=3).close()
    backup = archive.create_archive(
        source, tmp_path / "none", tmp_path / "in", archive.datetime.datetime(2026, 10, 1)
    )
    monkeypatch.setattr(archive, "restore_database", lambda src, dst: None)
    monkeypatch.setattr(archive, "restore_media", lambda src, dst: None)
    make_user("someone")

    call_command("restore", str(backup), "--force")

    assert len(snapshots("restore")) == 1


def test_restore_stops_if_no_snapshot_can_be_taken(
    tmp_path, make_user, broken_snapshots, monkeypatch
):
    from django.core.management import CommandError

    from apps.backups.tests.test_backups import make_database

    source = tmp_path / "source.sqlite3"
    make_database(source, rows=3).close()
    backup = archive.create_archive(
        source, tmp_path / "none", tmp_path / "in", archive.datetime.datetime(2026, 10, 1)
    )
    restored = []
    monkeypatch.setattr(archive, "restore_database", lambda src, dst: restored.append(src))
    monkeypatch.setattr(archive, "restore_media", lambda src, dst: None)
    make_user("someone")

    with pytest.raises(CommandError, match="--skip-snapshot"):
        call_command("restore", str(backup), "--force")
    assert restored == []

    call_command("restore", str(backup), "--force", "--skip-snapshot")
    assert len(restored) == 1


# The Backups page


def test_admins_see_snapshots_here_and_offsite(role_client, settings, monkeypatch):
    path, _run = service.take_snapshot(BackupRun.Trigger.NIGHTLY)
    offsite_only = "metra-snapshot-20261001-023000-upgrade-0.1.0.tar.gz"
    settings.BACKUP = dict(
        settings.BACKUP, **{k: v for k, v in REMOTE.items() if k != "remote_type"}
    )
    settings.BACKUP["remote_type"] = "s3"
    listing = f"{path.name};{path.stat().st_size}\n{offsite_only};4096\n"
    monkeypatch.setattr(
        service, "remote", lambda runner=None: service.Remote(settings.BACKUP, FakeRclone(listing))
    )

    page = role_client("Admin").get(reverse("backups:list"), HTTP_ACCEPT_LANGUAGE="en")

    html = page.content.decode()
    assert page.status_code == 200
    assert "Nightly" in html and "Before an upgrade" in html
    assert "This server, Offsite" in html  # last night's: in both places
    assert html.count("Offsite") >= 2
    assert "S3 s3.example.com bucket/metra (encrypted)" in html


def test_an_admin_takes_and_deletes_a_snapshot_by_hand(role_client):
    client = role_client("Admin")

    client.post(reverse("backups:take"))

    (name,) = snapshots("manual")
    assert BackupRun.objects.get().trigger == "manual"
    page = client.get(reverse("backups:list")).content.decode()
    assert f'value="{name}"' in page  # a delete button

    client.post(reverse("backups:delete"), {"name": name})
    assert snapshots() == []


def test_automatic_snapshots_cannot_be_deleted_by_hand(role_client):
    path, _run = service.take_snapshot(BackupRun.Trigger.NIGHTLY)

    role_client("Admin").post(reverse("backups:delete"), {"name": path.name})

    assert path.is_file()


@pytest.mark.parametrize("role", ["Board", "Treasurer", "Read-only"])
def test_only_admins_reach_backups(role_client, role):
    client = role_client(role)

    assert client.get(reverse("backups:list")).status_code == 403
    assert client.post(reverse("backups:take")).status_code == 403
    assert client.post(reverse("backups:delete"), {"name": "x"}).status_code == 403
    assert snapshots() == []


def test_a_broken_remote_is_shown_not_a_crash(role_client, settings):
    settings.BACKUP = dict(settings.BACKUP, remote_type="nfs")

    page = role_client("Admin").get(reverse("backups:list"), HTTP_ACCEPT_LANGUAGE="en")

    assert page.status_code == 200
    assert "must be one of" in page.content.decode()


def test_settings_link_to_backups(settings_admin):
    url = reverse("backups:list")

    assert url in settings_admin.get(reverse("admin:index")).content.decode()


def test_a_snapshot_during_a_request_is_sent_offsite_after_the_commit(
    role_client, settings, monkeypatch, django_capture_on_commit_callbacks
):
    settings.BACKUP = {**settings.BACKUP, **REMOTE}
    runner = FakeRclone()
    monkeypatch.setattr(
        service, "remote", lambda runner_=None: service.Remote(settings.BACKUP, runner)
    )

    with django_capture_on_commit_callbacks(execute=True):
        role_client("Admin").post(reverse("backups:take"))

    run = BackupRun.objects.get()
    assert "copyto" in runner.verbs()
    assert run.uploaded_at is not None and run.success
