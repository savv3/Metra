from django.conf import settings
from huey import crontab
from huey.contrib.djhuey import db_periodic_task

from .models import BackupRun
from .service import run_backup


def schedule_time(value):
    """(hour, minute) from "HH:MM"; the nightly default is 02:30 local time."""
    hour, _, minute = value.partition(":")
    hour, minute = int(hour), int(minute or 0)
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise ValueError(f"SCR_BACKUP_TIME must be HH:MM, not {value!r}")
    return hour, minute


HOUR, MINUTE = schedule_time(settings.BACKUP["time"])


@db_periodic_task(crontab(hour=str(HOUR), minute=str(MINUTE)))
def nightly_backup():
    run_backup(BackupRun.Trigger.SCHEDULE)
