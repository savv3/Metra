"""Whether the setup wizard has been run on this installation. One row."""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class SetupState(models.Model):
    finished_at = models.DateTimeField(_("finished"), null=True, blank=True)
    finished_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("finished by"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    # The steps saved at least once, so the wizard can show what is done.
    saved_steps = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = _("setup")
        verbose_name_plural = _("setup")
        permissions = [("run_setup", _("Can run the setup wizard"))]

    def __str__(self):
        return str(_("Setup"))

    @classmethod
    def current(cls):
        return cls.objects.order_by("pk").first() or cls.objects.create()

    def mark_saved(self, step):
        if step not in self.saved_steps:
            self.saved_steps = [*self.saved_steps, step]
            self.save(update_fields=["saved_steps"])

    def finish(self, user):
        if self.finished_at is None:
            self.finished_at = timezone.now()
            self.finished_by = user
            self.save(update_fields=["finished_at", "finished_by"])


def needs_setup(user):
    """True for an admin who should see the wizard after logging in."""
    if not user.is_authenticated or not user.has_perm("setup.run_setup"):
        return False
    state = SetupState.objects.order_by("pk").first()
    return state is None or state.finished_at is None
