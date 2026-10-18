from datetime import timedelta

from django import template
from django.utils import timezone

from ..models import BackupRun

register = template.Library()

STALE_AFTER = timedelta(hours=36)


@register.inclusion_tag("backups/_status.html", takes_context=True)
def backup_status(context):
    """A small panel with the backup status, for users allowed to see backups."""
    user = context["request"].user
    if not user.has_perm("backups.view_backuprun"):
        return {"show": False}
    last = BackupRun.objects.first()
    last_success = BackupRun.objects.filter(success=True).first()
    stale = last_success is None or last_success.finished_at < timezone.now() - STALE_AFTER
    return {
        "show": True,
        "last": last,
        "last_success": last_success,
        "failed": last is not None and not last.success and last.finished_at is not None,
        "stale": stale,
    }
