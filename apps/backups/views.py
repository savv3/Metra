from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import service
from .models import BackupRun


@login_required
@permission_required("backups.view_backuprun", raise_exception=True)
def backup_list(request):
    """The snapshots kept here and offsite, newest first, and recent problems."""
    snapshots, remote_error = service.list_snapshots()
    target = None
    try:
        target = service.remote()
    except Exception as error:  # a remote set up wrong is shown, not a crash
        remote_error = remote_error or str(error)
    config = settings.BACKUP
    context = {
        "snapshots": snapshots,
        "remote_error": remote_error,
        "remote": target.describe() if target else "",
        "failures": BackupRun.objects.filter(success=False, finished_at__isnull=False)[:5],
        "keep_days": config["keep_days"],
        "keep_weeks": config["keep_weeks"],
        "keep_months": config["keep_months"],
        "time": config["time"],
    }
    return render(request, "backups/backup_list.html", context)


@login_required
@permission_required("backups.take_snapshot", raise_exception=True)
@require_POST
def take(request):
    try:
        path, _run = service.take_snapshot(
            BackupRun.Trigger.MANUAL, request.user, upload=service.LATER
        )
    except service.SnapshotFailed as error:
        messages.error(request, _("The snapshot failed: %(error)s") % {"error": error})
    else:
        messages.success(request, _("Snapshot taken: %(name)s") % {"name": path.name})
    return redirect("backups:list")


@login_required
@permission_required("backups.delete_snapshot", raise_exception=True)
@require_POST
def delete(request):
    name = request.POST.get("name", "")
    try:
        service.delete_snapshot(name)
    except service.SnapshotFailed as error:
        messages.error(request, str(error))
    except Exception as error:  # rclone errors offsite
        messages.error(
            request, _("The snapshot could not be deleted: %(error)s") % {"error": error}
        )
    else:
        messages.success(request, _("Deleted %(name)s.") % {"name": name})
    return redirect("backups:list")
