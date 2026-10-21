from huey import crontab
from huey.contrib.djhuey import db_periodic_task

from .service import delete_old


@db_periodic_task(crontab(hour="3", minute="45"))
def delete_old_notifications():
    """Read and dismissed notifications are removed after 90 days."""
    delete_old()
