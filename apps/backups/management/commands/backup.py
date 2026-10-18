from django.core.management.base import BaseCommand, CommandError

from apps.backups.rclone import RcloneError
from apps.backups.service import remote, run_backup


class Command(BaseCommand):
    help = "Make a backup now (database and media), keep the newest and upload if configured."

    def add_arguments(self, parser):
        parser.add_argument(
            "--list-remote", action="store_true", help="List the backups on the remote instead."
        )

    def handle(self, *args, list_remote, **options):
        if list_remote:
            try:
                target = remote()
                if target is None:
                    raise CommandError("No remote is configured (METRA_BACKUP_REMOTE_TYPE).")
                for name in target.list():
                    self.stdout.write(name)
            except RcloneError as error:
                raise CommandError(str(error)) from None
            return
        run = run_backup()
        if not run.success:
            raise CommandError(f"Backup failed: {run.error}")
        self.stdout.write(
            self.style.SUCCESS(f"Backup {run.archive_name} ({run.size} bytes) to {run.target}.")
        )
