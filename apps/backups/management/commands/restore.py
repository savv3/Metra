import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connections

from apps.backups import archive as backup_archive
from apps.backups.rclone import RcloneError
from apps.backups.service import database_path, remote
from apps.register.models import Person, Unit


def database_has_data():
    try:
        return get_user_model().objects.exists() or Unit.objects.exists() or Person.objects.exists()
    except DatabaseError:
        return False  # no tables yet: a fresh database


class Command(BaseCommand):
    help = (
        "Restore the database and media from a backup archive. "
        "Stop the web app and the worker first."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "archive", help="A metra-backup-*.tar.gz file, or with --remote the name of one."
        )
        parser.add_argument(
            "--remote", action="store_true", help="Download the archive from the remote first."
        )
        parser.add_argument(
            "--force", action="store_true", help="Replace a database that already has data."
        )

    def handle(self, *args, **options):
        if database_has_data() and not options["force"]:
            raise CommandError(
                "The database already has users or register data. Restoring replaces all "
                "of it; run again with --force if that is what you want."
            )
        name = Path(options["archive"]).name
        with tempfile.TemporaryDirectory() as tmp:
            path = self._fetch(options["archive"], options["remote"], Path(tmp))
            try:
                db_file, media = backup_archive.extract_archive(path, Path(tmp) / "extracted")
            except backup_archive.ArchiveError as error:
                raise CommandError(str(error)) from None
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
