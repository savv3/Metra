import logging
import subprocess
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from . import archive
from .models import BackupRun
from .rclone import Remote

logger = logging.getLogger(__name__)


def database_path():
    return Path(settings.DATABASES["default"]["NAME"])


def remote(runner=subprocess.run):
    return Remote.from_config(settings.BACKUP, runner)


def run_backup(trigger=BackupRun.Trigger.COMMAND, runner=subprocess.run):
    """Make one backup, keep the newest ones, and record how it went."""
    config = settings.BACKUP
    run = BackupRun.objects.create(trigger=trigger, target=f"{config['dir']}")
    target = None
    try:
        target = remote(runner)
        if target:
            run.target = f"{config['dir']} + {target.describe()}"
        path = archive.create_archive(
            database_path(), settings.MEDIA_ROOT, config["dir"], timezone.localtime()
        )
        run.archive_name = path.name
        run.size = path.stat().st_size
        archive.prune_local(config["dir"], config["keep"])
        if target:
            target.upload(path)
            target.prune(config["keep"])
        run.success = True
    except Exception as error:
        message = str(error) or error.__class__.__name__
        if target:
            message = target.scrub(message)
        run.error = message
        logger.error("Backup failed: %s", message)
    finally:
        run.finished_at = timezone.now()
        run.save()
    return run
