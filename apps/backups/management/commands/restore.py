import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connections

from apps.backups import archive as backup_archive
from apps.backups.models import BackupRun
from apps.backups.rclone import RcloneError
from apps.backups.restore import is_newer
from apps.backups.service import SnapshotFailed, database_path, remote, take_snapshot
from apps.register.models import Person, Unit


def database_has_data():
    try:
        return get_user_model().objects.exists() or Unit.objects.exists() or Person.objects.exists()
    except DatabaseError:
        return False  # no tables yet: a fresh database


class Command(BaseCommand):
    help = (
        "Restore the database and uploads from a snapshot. Stop the web app and the "
        "worker first. A snapshot of the current data is taken before anything is replaced."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "archive", help="A metra-snapshot-*.tar.gz file, or with --remote the name of one."
        )
        parser.add_argument(
            "--remote", action="store_true", help="Download the archive from the remote first."
        )
        parser.add_argument(
            "--force", action="store_true", help="Replace a database that already has data."
        )
        parser.add_argument(
            "--skip-snapshot",
            action="store_true",
            help="Restore without first taking a snapshot of the current data, for a "
            "database too damaged to copy.",
        )

    def handle(self, *args, **options):
        if database_has_data() and not options["force"]:
            raise CommandError(
                "The database already has users or register data. Restoring replaces all "
                "of it; run again with --force if that is what you want."
            )
        name = Path(options["archive"]).name
        if database_has_data() and not options["skip_snapshot"]:
            try:
                path, _run = take_snapshot(BackupRun.Trigger.RESTORE)
            except SnapshotFailed as error:
                raise CommandError(
                    f"Could not take a snapshot of the current data first: {error}. "
                    "Run again with --skip-snapshot to restore anyway."
                ) from None
            self.stdout.write(f"Snapshot of the current data: {path.name}")
        with tempfile.TemporaryDirectory() as tmp:
            path = self._fetch(options["archive"], options["remote"], Path(tmp))
            try:
                db_file, media = backup_archive.extract_archive(path, Path(tmp) / "extracted")
            except backup_archive.ArchiveError as error:
                raise CommandError(str(error)) from None
            version = backup_archive.manifest_version(Path(tmp) / "extracted")
            if version and is_newer(version):
                raise CommandError(
                    f"{name} was taken by Metra {version}, newer than this one "
                    f"({settings.METRA_VERSION}); restore it with that version or newer."
                )
            connections.close_all()
            backup_archive.restore_database(db_file, database_path())
            backup_archive.restore_media(media, settings.MEDIA_ROOT)
        # A backup from an older version is brought up to date.
        call_command("migrate", interactive=False, verbosity=0)
        self.stdout.write(self.style.SUCCESS(f"Restored {name}."))

    def _fetch(self, archive, from_remote, tmp):
        if not from_remote:
            path = Path(archive)
            if not path.is_file():
                raise CommandError(f"{path} does not exist.")
            return path
        target = remote()
        if target is None:
            raise CommandError("No remote is configured (METRA_BACKUP_REMOTE_TYPE).")
        path = tmp / Path(archive).name
        try:
            target.download(path.name, path)
        except RcloneError as error:
            raise CommandError(str(error)) from None
        return path
