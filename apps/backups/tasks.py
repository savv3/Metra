from django.conf import settings
from huey import crontab
from huey.contrib.djhuey import db_periodic_task, db_task

from .models import BackupRun
from .service import SnapshotFailed, send_offsite, take_snapshot


def schedule_time(value):
    """(hour, minute) from "HH:MM"; the nightly default is 02:30 local time."""
    hour, _, minute = value.partition(":")
    hour, minute = int(hour), int(minute or 0)
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise ValueError(f"METRA_BACKUP_TIME must be HH:MM, not {value!r}")
    return hour, minute


HOUR, MINUTE = schedule_time(settings.BACKUP["time"])


@db_periodic_task(crontab(hour=str(HOUR), minute=str(MINUTE)))
def nightly_snapshot():
    try:
        take_snapshot(BackupRun.Trigger.NIGHTLY)
    except SnapshotFailed:
        pass  # recorded on the run, and shown on the Backups page


@db_task()
def upload_snapshot(run_id):
    """Send a snapshot taken during a request offsite."""
    run = BackupRun.objects.filter(pk=run_id).first()
    if run is None or not run.archive_name:
        return
    path = settings.BACKUP["dir"] / run.archive_name
    if path.is_file():
        send_offsite(path, run)


@db_task()
def restore_snapshot(name, safety_name, username):
    """Restore a snapshot an admin chose on the Backups page."""
    from . import restore

    restore.run(name, safety_name, username)
