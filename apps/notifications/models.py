import logging

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from . import kinds

logger = logging.getLogger(__name__)


class Notification(models.Model):
    """Something staff should know about, such as a failed snapshot.

    Only the kind's name and its parameters are stored; the text is made when
    it is shown, in the reader's language (see ``text``). Parameters hold
    counts and technical facts, never members' personal data.
    """

    kind = models.CharField(_("kind"), max_length=64)
    params = models.JSONField(_("details"), default=dict, blank=True)
    # A path on this site, such as "/backups/"; empty when there is nothing to open.
    link = models.CharField(_("link"), max_length=500, blank=True)
    # Notifications of the same kind and group within a day are one notification.
    group = models.CharField(_("group"), max_length=200, blank=True)
    created_at = models.DateTimeField(_("created"), default=timezone.now)
    updated_at = models.DateTimeField(_("updated"), default=timezone.now)

    class Meta:
        ordering = ["-updated_at", "-pk"]
        verbose_name = _("notification")
        verbose_name_plural = _("notifications")
        indexes = [models.Index(fields=["kind", "group", "created_at"])]

    def __str__(self):
        return self.text()

    @property
    def kind_info(self):
        return kinds.get(self.kind)

    def text(self):
        """The notification in the active language. Never fails: an unknown
        kind (its plugin was removed) or missing details give a general text."""
        kind = self.kind_info
        if kind is None:
            return gettext("A notification from a feature that is no longer installed.")
        params = self.params if isinstance(self.params, dict) else {}
        message = kind.variants.get(params.get("variant"), kind.message)
        try:
            return str(message % params)
        except (KeyError, ValueError, TypeError):
            logger.warning("Notification %s: details do not fit the %s message", self.pk, self.kind)
            return str(kind.label)


class Recipient(models.Model):
    """One user's copy of a notification, with whether they read or dismissed it."""

    notification = models.ForeignKey(
        Notification,
        verbose_name=_("notification"),
        on_delete=models.CASCADE,
        related_name="recipients",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("user"),
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    read_at = models.DateTimeField(_("read"), null=True, blank=True)
    dismissed_at = models.DateTimeField(_("dismissed"), null=True, blank=True)

    class Meta:
        verbose_name = _("notification recipient")
        verbose_name_plural = _("notification recipients")
        constraints = [
            models.UniqueConstraint(fields=["notification", "user"], name="one_copy_per_user"),
        ]
        # The bell counts a user's unread, undismissed copies on every page.
        indexes = [models.Index(fields=["user", "dismissed_at", "read_at"])]

    def __str__(self):
        return f"{self.user} – {self.notification}"

    @property
    def is_read(self):
        return self.read_at is not None


class Preference(models.Model):
    """A user's choice to get, or not get, a kind of notification. Without
    one, the kind's default applies."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("user"),
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    kind = models.CharField(_("kind"), max_length=64)
    enabled = models.BooleanField(_("on"), default=True)

    class Meta:
        verbose_name = _("notification setting")
        verbose_name_plural = _("notification settings")
        constraints = [
            models.UniqueConstraint(fields=["user", "kind"], name="one_preference_per_kind"),
        ]

    def __str__(self):
        return f"{self.user}: {self.kind}"
