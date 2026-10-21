"""Taking, sending offsite, listing and deleting snapshots.

A snapshot is taken nightly, before an upgrade, before risky actions (a CSV
import, deleting a unit type or field, a restore) and by hand. Each one is
kept in METRA_DATA_DIR/snapshots and, when a remote is set, also sent
offsite, encrypted. Snapshots taken during a request are sent offsite in the
background, so the page does not wait for the upload.
"""

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.db import DatabaseError, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.notifications.service import notify

from . import archive
from .models import BackupRun
from .rclone import RcloneError, Remote
from .retention import KEPT_UNTIL_DELETED, Policy

logger = logging.getLogger(__name__)

NOW, LATER = "now", "later"


class SnapshotFailed(Exception):
    """A snapshot could not be taken. The message is safe to show to staff."""


def database_path():
    return Path(settings.DATABASES["default"]["NAME"])


def remote(runner=subprocess.run):
    return Remote.from_config(settings.BACKUP, runner)


def policy():
    return Policy.from_settings(settings.BACKUP)


def local_now():
    """Local time without a time zone, as in snapshot names."""
    return timezone.localtime().replace(tzinfo=None)


def _record(trigger, user):
    """A BackupRun for this snapshot, or None when the table cannot be written
    yet (a snapshot taken before an upgrade, ahead of the migrations)."""
    try:
        return BackupRun.objects.create(
            trigger=trigger, started_by=user, target=str(settings.BACKUP["dir"])
        )
    except DatabaseError:
        return None


def notify_failure(message, variant=""):
    """Tell the admins (under the bell) that a snapshot failed."""
    params = {"error": message[:300]}
    if variant:
        params["variant"] = variant
    notify("backup_failed", params, link=reverse("backups:list"))


def _save(run, **fields):
    if run is None:
        return
    for name, value in fields.items():
        setattr(run, name, value)
    try:
        run.save()
    except DatabaseError:
        logger.warning("Could not record snapshot %s", run.archive_name)


def take_snapshot(trigger, user=None, upload=NOW, runner=subprocess.run):
    """Take a snapshot and keep the ones the schedule keeps. With a remote set,
    send it offsite now or, with ``upload=LATER``, in the background.

    Returns (path, run); run is None when it could not be recorded. Raises
    SnapshotFailed when no snapshot could be made."""
    config = settings.BACKUP
    run = _record(trigger, user)
    try:
        path = archive.create_archive(
            database_path(),
            settings.MEDIA_ROOT,
            config["dir"],
            timezone.localtime(),
            trigger,
            settings.METRA_VERSION,
        )
        archive.prune_local(config["dir"], policy(), local_now())
    except Exception as error:
        message = str(error) or error.__class__.__name__
        logger.error("Snapshot failed: %s", message)
        _save(run, error=message, finished_at=timezone.now())
        notify_failure(message)
        raise SnapshotFailed(message) from error
    _save(
        run,
        success=True,
        archive_name=path.name,
        size=path.stat().st_size,
        version=settings.METRA_VERSION,
        finished_at=timezone.now(),
    )
    if config["remote_type"]:
        if upload == LATER and run is not None:
            from .tasks import upload_snapshot

            # After the commit, so the worker finds the run (an import takes its
            # snapshot inside its own transaction).
            transaction.on_commit(lambda: upload_snapshot(run.pk))
        else:
            send_offsite(path, run, runner)
    return path, run


def send_offsite(path, run=None, runner=subprocess.run):
    """Upload a snapshot and delete the offsite ones the schedule no longer
    keeps. A failure is recorded on the run; it never raises."""
    target = None
    try:
        target = remote(runner)
        if target is None:
            return
        target.upload(path)
        target.prune(policy(), local_now())
    except Exception as error:
        message = str(error) or error.__class__.__name__
        if target:
            message = target.scrub(message)
        logger.error("Sending snapshot offsite failed: %s", message)
        _save(run, success=False, error=message)
        notify_failure(message, "offsite")
        return
    _save(
        run,
        uploaded_at=timezone.now(),
        target=f"{settings.BACKUP['dir']} + {target.describe()}",
    )


def snapshot_before(trigger, user=None):
    """Take a snapshot before a risky action. Raises SnapshotFailed, and the
    caller then stops the action: it must never go ahead without one."""
    return take_snapshot(trigger, user, upload=LATER)


@dataclass
class Snapshot:
    """A snapshot as the Backups page lists it: here, offsite, or both."""

    info: archive.Info
    local_size: int | None = None
    offsite_size: int | None = None
    here: bool = False
    offsite: bool = False

    @property
    def size(self):
        return self.local_size if self.local_size is not None else self.offsite_size

    @property
    def trigger_label(self):
        return (
            BackupRun.Trigger(self.info.trigger).label
            if self.info.trigger in (BackupRun.Trigger.values)
            else self.info.trigger
        )

    @property
    def deletable(self):
        return self.info.trigger in KEPT_UNTIL_DELETED


def list_snapshots(runner=subprocess.run):
    """(snapshots newest first, an error message if the remote could not be read)."""
    found = {}
    for path in archive.local_archives(settings.BACKUP["dir"]):
        info = archive.parse_name(path.name)
        found[path.name] = Snapshot(info, local_size=path.stat().st_size, here=True)
    error = ""
    try:
        target = remote(runner)
        if target is not None:
            for name, size in target.sizes().items():
                snapshot = found.setdefault(name, Snapshot(archive.parse_name(name)))
                snapshot.offsite, snapshot.offsite_size = True, size
    except RcloneError as failure:
        error = str(failure)
    return sorted(found.values(), key=lambda s: s.info.taken, reverse=True), error


def delete_snapshot(name, runner=subprocess.run):
    """Delete a snapshot taken by hand, here and offsite."""
    info = archive.parse_name(name)
    if info is None or info.trigger not in KEPT_UNTIL_DELETED:
        raise SnapshotFailed(_("Only snapshots taken by hand can be deleted."))
    path = Path(settings.BACKUP["dir"]) / name
    if path.is_file():
        path.unlink()
    target = remote(runner)
    if target is not None and name in target.list():
        target.delete(name)
