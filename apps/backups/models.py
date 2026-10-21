from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class BackupRun(models.Model):
    """One attempt to take a snapshot and send it offsite. The newest rows are
    the backup status; the snapshots themselves are files (see archive.py)."""

    class Trigger(models.TextChoices):
        NIGHTLY = "nightly", _("Nightly")
        MANUAL = "manual", _("Taken by hand")
        COMMAND = "command", _("Command")
        UPGRADE = "upgrade", _("Before an upgrade")
        IMPORT = "import", _("Before a CSV import")
        DELETE = "delete", _("Before deleting a unit type or field")
        RESTORE = "restore", _("Before a restore")

    started_at = models.DateTimeField(_("started"), default=timezone.now)
    finished_at = models.DateTimeField(_("finished"), null=True, blank=True)
    trigger = models.CharField(
        _("started by"), max_length=10, choices=Trigger.choices, default=Trigger.COMMAND
    )
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("taken by"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    success = models.BooleanField(_("succeeded"), default=False)
    archive_name = models.CharField(_("snapshot"), max_length=150, blank=True)
    size = models.BigIntegerField(_("size in bytes"), null=True, blank=True)
    version = models.CharField(_("version"), max_length=30, blank=True)
    # Where the snapshot went, e.g. "S3 s3.example.com bucket/metra"; never credentials.
    target = models.CharField(_("target"), max_length=300, blank=True)
    uploaded_at = models.DateTimeField(_("sent offsite"), null=True, blank=True)
    error = models.TextField(_("error"), blank=True)

    class Meta:
        ordering = ["-started_at", "-pk"]
        verbose_name = _("snapshot")
        verbose_name_plural = _("snapshots")
        permissions = [
            ("take_snapshot", _("Can take a snapshot")),
            ("delete_snapshot", _("Can delete snapshots taken by hand")),
            ("restore_snapshot", _("Can restore a snapshot")),
        ]

    def __str__(self):
        return self.archive_name or f"{self.started_at:%Y-%m-%d %H:%M}"


class Restore(models.Model):
    """A snapshot restored from the app. It is recorded in the restored
    database, so the record survives the restore it describes."""

    snapshot = models.CharField(_("snapshot"), max_length=150)
    # Taken just before, with the data as it was; put back if the restore fails.
    safety_snapshot = models.CharField(_("snapshot taken before"), max_length=150)
    # A name, not a link: the user may not exist in the restored data.
    requested_by = models.CharField(_("restored by"), max_length=150)
    started_at = models.DateTimeField(_("started"))
    finished_at = models.DateTimeField(_("finished"))
    success = models.BooleanField(_("succeeded"), default=False)
    error = models.TextField(_("error"), blank=True)

    class Meta:
        ordering = ["-started_at", "-pk"]
        verbose_name = _("restore")
        verbose_name_plural = _("restores")

    def __str__(self):
        return self.snapshot
