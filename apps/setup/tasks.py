from django.conf import settings
from huey import crontab
from huey.contrib.djhuey import db_periodic_task

from apps.backups.tasks import schedule_time

HOUR, MINUTE = schedule_time(settings.DEMO_RESET_TIME)


@db_periodic_task(crontab(hour=str(HOUR), minute=str(MINUTE)))
def nightly_demo_reset():
    """Put a demo site back to its demo data every night (only with METRA_DEMO on)."""
    if settings.DEMO:
        from . import demo

        demo.reset()
