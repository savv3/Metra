from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class BackupRun(models.Model):
    """One attempt to make a backup. The newest rows are the backup status."""

    class Trigger(models.TextChoices):
        SCHEDULE = "schedule", _("Nightly schedule")
        COMMAND = "command", _("Command")

    started_at = models.DateTimeField(_("started"), default=timezone.now)
    finished_at = models.DateTimeField(_("finished"), null=True, blank=True)
    trigger = models.CharField(
        _("started by"), max_length=10, choices=Trigger.choices, default=Trigger.COMMAND
    )
    success = models.BooleanField(_("succeeded"), default=False)
    archive_name = models.CharField(_("archive"), max_length=100, blank=True)
    size = models.BigIntegerField(_("size in bytes"), null=True, blank=True)
    # Where the backup went, e.g. "S3 s3.example.com bucket/scr"; never credentials.
    target = models.CharField(_("target"), max_length=300, blank=True)
    error = models.TextField(_("error"), blank=True)

    class Meta:
        ordering = ["-started_at", "-pk"]
        verbose_name = _("backup")
        verbose_name_plural = _("backups")

    def __str__(self):
        return self.archive_name or f"{self.started_at:%Y-%m-%d %H:%M}"
