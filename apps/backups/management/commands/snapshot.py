from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.backups import service
from apps.backups.models import BackupRun
from apps.backups.rclone import RcloneError
from apps.backups.service import SnapshotFailed, remote, take_snapshot

VERSION_FILE = ".metra-version"


class Command(BaseCommand):
    help = (
        "Take a snapshot now (database and uploads), keep the ones the schedule keeps, "
        "and send it offsite if a remote is set."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--list-remote", action="store_true", help="List the snapshots offsite instead."
        )
        parser.add_argument(
            "--before-upgrade",
            action="store_true",
            help="Only when this version of Metra has not run on the database yet; for "
            "the container to call before migrating.",
        )

    def handle(self, *args, list_remote, before_upgrade, **options):
        if list_remote:
            return self.list_remote()
        trigger = BackupRun.Trigger.COMMAND
        if before_upgrade:
            if not self.upgrading():
                return
            trigger = BackupRun.Trigger.UPGRADE
        try:
            path, run = take_snapshot(trigger)
        except SnapshotFailed as error:
            raise CommandError(f"Snapshot failed: {error}") from None
        if run is not None and not run.success:
            raise CommandError(f"Snapshot {path.name} was taken, but: {run.error}")
        if before_upgrade:
            self.version_file().write_text(settings.METRA_VERSION)
        self.stdout.write(
            self.style.SUCCESS(f"Snapshot {path.name} ({path.stat().st_size} bytes).")
        )

    def version_file(self):
        return settings.DATA_DIR / VERSION_FILE

    def upgrading(self):
        """True when there is a database and it was last run by another version."""
        if not service.database_path().is_file():
            # A new install: nothing to protect yet.
            self.version_file().write_text(settings.METRA_VERSION)
            return False
        version_file = self.version_file()
        previous = version_file.read_text().strip() if version_file.is_file() else ""
        if previous == settings.METRA_VERSION:
            return False
        return True

    def list_remote(self):
        try:
            target = remote()
            if target is None:
                raise CommandError("No remote is configured (METRA_BACKUP_REMOTE_TYPE).")
            for name in target.list():
                self.stdout.write(name)
        except RcloneError as error:
            raise CommandError(str(error)) from None
