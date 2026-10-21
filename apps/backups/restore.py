"""Restoring a snapshot from inside the app.

An admin picks a snapshot and sees what it holds and what the restore would
remove (``inspect``). On confirmation (``start``) the app takes a safety
snapshot of the current data and switches to maintenance mode, and the
worker (``run``) replaces the database and the uploads with the snapshot's,
migrates a snapshot from an older version, records the restore and brings
the site back. If anything fails, the safety snapshot is put back.

Maintenance mode is a file in METRA_DATA_DIR, so the web and the worker,
which share that folder, both see it; while it is there, every page shows a
short "back soon" notice instead (see ``MaintenanceMiddleware``).
"""

import json
import logging
import sqlite3
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import connection, connections
from django.utils import timezone
from django.utils.translation import gettext as _

from . import archive, service

logger = logging.getLogger(__name__)

MAINTENANCE_FILE = "maintenance.json"

# What the preview counts, as (label, table, condition).
COUNTED = [
    ("units", "register_unit", ""),
    ("people", "register_person", ""),
    ("readings", "readings_reading", ""),
    ("messages", "messaging_message", ""),
    ("invoices", "invoicing_invoice", "status != 'draft'"),
    ("payments", "invoicing_payment", ""),
]


class RestoreError(Exception):
    """The snapshot cannot be restored. The message is shown to the admin."""


def version_tuple(version):
    """(0, 3, 1) from "0.3.1"; parts that are not numbers count as 0."""
    return tuple(int(part) if part.isdigit() else 0 for part in version.split("."))


def is_newer(version):
    """True for a version newer than the one running, which could not be restored."""
    return version_tuple(version) > version_tuple(settings.METRA_VERSION)


@dataclass
class Count:
    label: str
    now: int
    then: int

    @property
    def removed(self):
        return max(self.now - self.then, 0)


@dataclass
class Preview:
    """What a snapshot holds and what restoring it would remove."""

    info: archive.Info
    counts: list = field(default_factory=list)
    # Issued invoices and payments in the register now that the snapshot does not have.
    invoices_since: list = field(default_factory=list)
    payments_since: list = field(default_factory=list)

    @property
    def needs_bookkeeping_confirmation(self):
        return bool(self.invoices_since or self.payments_since)


def local_path(name):
    """The snapshot's file here, downloaded first if it is only offsite."""
    info = archive.parse_name(name)
    if info is None:
        raise RestoreError(_("That is not a snapshot."))
    path = Path(settings.BACKUP["dir"]) / name
    if path.is_file():
        return path
    target = service.remote()
    if target is None or name not in target.list():
        raise RestoreError(_("The snapshot %(name)s was not found.") % {"name": name})
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    target.download(name, partial)
    partial.replace(path)
    return path


def _ids(db, table, condition=""):
    where = f" WHERE {condition}" if condition else ""
    try:
        return {row[0] for row in db.execute(f"SELECT id FROM {table}{where}")}  # noqa: S608
    except sqlite3.Error:
        return set()  # a table the snapshot's version did not have yet


def inspect(name):
    """A Preview of restoring ``name``. Raises RestoreError if it cannot be restored."""
    path = local_path(name)
    info = archive.parse_name(name)
    if is_newer(info.version):
        raise RestoreError(
            _(
                "This snapshot was taken by Metra %(version)s, which is newer than the "
                "version running now (%(running)s), so it cannot be restored here."
            )
            % {"version": info.version, "running": settings.METRA_VERSION}
        )
    preview = Preview(info)
    with tempfile.TemporaryDirectory() as tmp:
        try:
            db_file, _media = archive.extract_archive(path, Path(tmp))
        except archive.ArchiveError as error:
            raise RestoreError(str(error)) from None
        then = sqlite3.connect(db_file)
        try:
            connection.ensure_connection()
            now = connection.connection  # the sqlite3 connection under Django's
            for label, table, condition in COUNTED:
                then_ids = _ids(then, table, condition)
                now_ids = _ids(now, table, condition)
                preview.counts.append(Count(label, len(now_ids), len(then_ids)))
                if table == "invoicing_invoice":
                    preview.invoices_since = _invoice_numbers(now_ids - then_ids)
                if table == "invoicing_payment":
                    preview.payments_since = _payments(now_ids - then_ids)
        finally:
            then.close()
    return preview


def _invoice_numbers(ids):
    from apps.invoicing.models import Invoice

    invoices = Invoice.objects.filter(pk__in=ids).order_by("sequence")
    return list(invoices.values_list("number", flat=True))


def _payments(ids):
    from apps.invoicing.models import Payment

    return list(Payment.objects.filter(pk__in=ids).select_related("invoice").order_by("pk"))


# Maintenance mode


def maintenance_path():
    return Path(settings.DATA_DIR) / MAINTENANCE_FILE


def in_maintenance():
    return maintenance_path().is_file()


def _enter_maintenance(name, user):
    maintenance_path().write_text(
        json.dumps(
            {"snapshot": name, "by": user.get_username(), "since": timezone.now().isoformat()}
        )
    )


def _leave_maintenance():
    maintenance_path().unlink(missing_ok=True)


# Restoring


def start(name, user, bookkeeping_confirmed=False):
    """Check, take a safety snapshot, switch to maintenance and hand the restore
    to the worker. Raises RestoreError (or SnapshotFailed) before changing anything."""
    if in_maintenance():
        raise RestoreError(_("A restore is already running."))
    preview = inspect(name)
    if preview.needs_bookkeeping_confirmation and not bookkeeping_confirmed:
        raise RestoreError(
            _("Confirm that invoices and payments recorded since the snapshot will be removed.")
        )
    from .models import BackupRun

    safety, _run = service.snapshot_before(BackupRun.Trigger.RESTORE, user)
    _enter_maintenance(name, user)
    from .tasks import restore_snapshot

    restore_snapshot(name, safety.name, user.get_username())
    return safety


def run(name, safety_name, username):
    """Restore ``name`` (in the worker). On failure, put the safety snapshot back."""
    from .models import Restore

    started = timezone.now()
    try:
        try:
            _replace_with(Path(settings.BACKUP["dir"]) / name)
        except Exception as error:
            message = str(error) or error.__class__.__name__
            logger.exception("Restoring %s failed; putting %s back", name, safety_name)
            _replace_with(Path(settings.BACKUP["dir"]) / safety_name)
            Restore.objects.create(
                snapshot=name,
                safety_snapshot=safety_name,
                requested_by=username,
                started_at=started,
                finished_at=timezone.now(),
                success=False,
                error=message,
            )
            return False
        # Recorded in the restored database, so the record survives the restore.
        Restore.objects.create(
            snapshot=name,
            safety_snapshot=safety_name,
            requested_by=username,
            started_at=started,
            finished_at=timezone.now(),
            success=True,
        )
        return True
    finally:
        _leave_maintenance()


def _replace_with(path):
    with tempfile.TemporaryDirectory() as tmp:
        db_file, media = archive.extract_archive(path, Path(tmp))
        version = archive.manifest_version(tmp)
        if version and is_newer(version):
            raise RestoreError(f"{path.name} is from a newer version ({version}).")
        connections.close_all()
        archive.restore_database(db_file, service.database_path())
        archive.restore_media(media, settings.MEDIA_ROOT)
    connections.close_all()
    # A snapshot from an older version is brought up to date.
    call_command("migrate", interactive=False, verbosity=0)
