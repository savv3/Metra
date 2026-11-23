from django.conf import settings
from django.utils import translation
from huey import crontab
from huey.contrib.djhuey import db_periodic_task

from apps.plugins import api


@db_periodic_task(crontab(hour="9", minute="0"))
def meeting_reminders():
    """Send the reminders that are due today, while the add-on is on."""
    if not api.plugin_enabled("meetings"):
        return
    from . import invitations

    with translation.override(settings.LANGUAGE_CODE):
        invitations.send_due_reminders()
