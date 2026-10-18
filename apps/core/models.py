from auditlog.registry import auditlog
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class NoticeQuerySet(models.QuerySet):
    def current(self):
        now = timezone.now()
        return self.filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now), starts_at__lte=now)


class Notice(models.Model):
    """A short notice at the top of the public page and members' pages, such as
    "Water off in the village until 18:00". Often published with an urgent alert."""

    class Level(models.TextChoices):
        INFO = "info", _("Information")
        URGENT = "urgent", _("Urgent")

    text = models.TextField(_("text"), max_length=500)
    level = models.CharField(_("level"), max_length=10, choices=Level.choices, default=Level.INFO)
    starts_at = models.DateTimeField(_("shown from"), default=timezone.now)
    ends_at = models.DateTimeField(
        _("shown until"), null=True, blank=True, help_text=_("Empty: until it is removed.")
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("created by"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(_("created"), auto_now_add=True)

    objects = NoticeQuerySet.as_manager()

    class Meta:
        ordering = ["-starts_at", "-pk"]
        verbose_name = _("notice")
        verbose_name_plural = _("notices")

    def __str__(self):
        return self.text[:60]

    @property
    def is_current(self):
        now = timezone.now()
        return self.starts_at <= now and (self.ends_at is None or self.ends_at > now)

    def end_now(self):
        self.ends_at = timezone.now()
        self.save(update_fields=["ends_at"])


auditlog.register(Notice)
