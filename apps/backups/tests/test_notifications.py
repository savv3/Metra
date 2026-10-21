"""Snapshots and restores notify the admins under the bell."""

import pytest
from django.urls import reverse
from django.utils import translation

from apps.backups import restore, service, tasks
from apps.backups.models import BackupRun
from apps.backups.service import SnapshotFailed, take_snapshot
from apps.backups.tests.test_backups import FakeRclone, live_db  # noqa: F401
from apps.backups.tests.test_restore import snapshot_of_now  # noqa: F401
from apps.notifications.models import Notification, Preference, Recipient

pytestmark = pytest.mark.django_db


@pytest.fixture
def broken_snapshots(monkeypatch, tmp_path):
    # A directory is no database, so every snapshot fails.
    monkeypatch.setattr(service, "database_path", lambda: tmp_path)


def test_a_failed_backup_reaches_every_admin_who_reads_and_dismisses_it(
    client, make_user, broken_snapshots, django_capture_on_commit_callbacks
):
    admins = [make_user("anna", "Admin"), make_user("bo", "Admin")]
    make_user("cia", "Board")

    with django_capture_on_commit_callbacks(execute=True), pytest.raises(SnapshotFailed):
        take_snapshot(BackupRun.Trigger.NIGHTLY)

    notification = Notification.objects.get(kind="backup_failed")
    assert {r.user for r in notification.recipients.all()} == set(admins)
    client.force_login(admins[0])
    page = client.get("/", follow=True, HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert 'aria-label="Notifications, 1 unread"' in page
    listed = client.get(reverse("notifications:list"), HTTP_ACCEPT_LANGUAGE="en")
    assert "A snapshot failed:" in listed.content.decode()

    client.post(reverse("notifications:read", args=[notification.pk]))
    client.post(reverse("notifications:dismiss", args=[notification.pk]))

    mine = Recipient.objects.get(user=admins[0])
    assert mine.read_at is not None and mine.dismissed_at is not None
    assert "A snapshot failed:" not in client.get(reverse("notifications:list")).content.decode()
    assert Recipient.objects.get(user=admins[1]).read_at is None


def test_a_failed_snapshot_by_hand_notifies_too(
    role_client, make_user, broken_snapshots, django_capture_on_commit_callbacks
):
    client = role_client("Admin")

    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("backups:take"))

    assert Notification.objects.filter(kind="backup_failed").exists()


def test_a_snapshot_that_cannot_go_offsite_notifies(
    live_db,  # noqa: F811
    settings,
    make_user,
    django_capture_on_commit_callbacks,
):
    make_user("anna", "Admin")
    settings.BACKUP = dict(settings.BACKUP, remote_type="s3")

    with django_capture_on_commit_callbacks(execute=True):
        take_snapshot(BackupRun.Trigger.NIGHTLY, runner=FakeRclone(fail="copyto"))

    notification = Notification.objects.get(kind="backup_failed")
    assert notification.params["variant"] == "offsite"
    with translation.override("en"):
        assert notification.text().startswith("A snapshot could not be sent offsite")


def test_a_nightly_success_notifies_only_admins_who_asked(
    make_user, django_capture_on_commit_callbacks
):
    wants = make_user("anna", "Admin")
    make_user("bo", "Admin")
    Preference.objects.create(user=wants, kind="backup_done", enabled=True)

    with django_capture_on_commit_callbacks(execute=True):
        tasks.nightly_snapshot.call_local()

    assert list(Recipient.objects.values_list("user", "notification__kind")) == [
        (wants.pk, "backup_done")
    ]


def test_a_restore_notifies_when_done(
    snapshot_of_now,  # noqa: F811
    make_user,
    django_capture_on_commit_callbacks,
):
    make_user("anna", "Admin")
    path = snapshot_of_now()

    with django_capture_on_commit_callbacks(execute=True):
        assert restore.run(path.name, path.name, "anna")

    notification = Notification.objects.get(kind="restore_done")
    assert notification.params == {"snapshot": path.name, "user": "anna"}
    assert notification.link == reverse("backups:list")


def test_a_failed_restore_notifies(
    snapshot_of_now,  # noqa: F811
    make_user,
    settings,
    django_capture_on_commit_callbacks,
):
    make_user("anna", "Admin")
    safety = snapshot_of_now(BackupRun.Trigger.RESTORE)
    broken = settings.BACKUP["dir"] / "metra-snapshot-20261001-023000-manual-0.1.0.tar.gz"
    broken.write_bytes(b"not a snapshot")

    with django_capture_on_commit_callbacks(execute=True):
        assert not restore.run(broken.name, safety.name, "anna")

    notification = Notification.objects.get(kind="restore_failed")
    assert notification.params["error"]
