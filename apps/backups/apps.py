from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BackupsConfig(AppConfig):
    name = "apps.backups"
    verbose_name = _("Backups")

    def ready(self):
        from auditlog.registry import auditlog

        from .models import BackupRun, Restore

        auditlog.register(BackupRun)
        auditlog.register(Restore)
