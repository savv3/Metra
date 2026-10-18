"""Messages sent to people, grouped in batches (for example "the 2026 links"),
and the templates their text comes from.

A message body is stored as sent, except that a personal self-service link
is replaced by a placeholder: links are kept only as hashes (see
apps.selfservice), so a copy of the database must not hold them either.
"""

import re

from auditlog.registry import auditlog
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.readings.models import ReadingRound
from apps.register.models import Person, Unit


class Channel(models.TextChoices):
    SMS = "sms", _("SMS")
    EMAIL = "email", _("Email")
    LETTER = "letter", _("Letter")


class MessageBatch(models.Model):
    """One send-out, for example a round's links or a reminder."""

    class Kind(models.TextChoices):
        LINKS = "links", _("Self-service links")
        REMINDER = "reminder", _("Reminder")
        AUTO_REMINDER = "auto_reminder", _("Automatic reminder")

    class Scope(models.TextChoices):
        ALL = "all", _("All units")
        MISSING = "missing", _("Units missing a reading")

    class Status(models.TextChoices):
        QUEUED = "queued", _("Waiting to be sent")
        SENDING = "sending", _("Sending")
        DONE = "done", _("Done")

    kind = models.CharField(_("kind"), max_length=20, choices=Kind.choices)
    scope = models.CharField(_("to"), max_length=10, choices=Scope.choices, default=Scope.ALL)
    round = models.ForeignKey(
        ReadingRound,
        verbose_name=_("reading round"),
        on_delete=models.PROTECT,
        related_name="message_batches",
        null=True,
        blank=True,
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.QUEUED
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("sent by"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(_("created"), auto_now_add=True)
    finished_at = models.DateTimeField(_("finished"), null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = _("send-out")
        verbose_name_plural = _("send-outs")

    def __str__(self):
        label = self.get_kind_display()
        return f"{label}: {self.round}" if self.round_id else label

    def get_absolute_url(self):
        return reverse("messaging:batch_detail", args=[self.pk])


class Message(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", _("Queued")
        SENT = "sent", _("Sent")
        DELIVERED = "delivered", _("Delivered")
        FAILED = "failed", _("Failed")
        TO_PRINT = "to_print", _("To print")

    batch = models.ForeignKey(
        MessageBatch,
        verbose_name=_("send-out"),
        on_delete=models.CASCADE,
        related_name="messages",
        null=True,
        blank=True,
    )
    person = models.ForeignKey(
        Person,
        verbose_name=_("person"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
    )
    unit = models.ForeignKey(
        Unit,
        verbose_name=_("unit"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
    )
    channel = models.CharField(_("channel"), max_length=10, choices=Channel.choices)
    recipient = models.CharField(_("recipient"), max_length=254, blank=True)
    subject = models.CharField(_("subject"), max_length=200, blank=True)
    body = models.TextField(_("text"), blank=True)
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.QUEUED
    )
    provider = models.CharField(_("provider"), max_length=50, blank=True)
    provider_id = models.CharField(_("provider's id"), max_length=200, blank=True, db_index=True)
    error = models.TextField(_("error"), blank=True)
    created_at = models.DateTimeField(_("created"), auto_now_add=True)
    sent_at = models.DateTimeField(_("sent"), null=True, blank=True)
    status_changed_at = models.DateTimeField(_("status changed"), null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = _("message")
        verbose_name_plural = _("messages")

    def __str__(self):
        return f"{self.get_channel_display()} → {self.recipient or self.person}"


PLACEHOLDER = re.compile(r"\{(\w+)\}")


class MessageTemplate(models.Model):
    """The text of one kind of message on one channel, edited under Settings."""

    class Purpose(models.TextChoices):
        LINK = "link", _("Self-service link")
        REMINDER = "reminder", _("Reminder")

    purpose = models.CharField(_("purpose"), max_length=20, choices=Purpose.choices)
    channel = models.CharField(
        _("channel"),
        max_length=10,
        choices=[(Channel.SMS, Channel.SMS.label), (Channel.EMAIL, Channel.EMAIL.label)],
    )
    subject = models.CharField(_("subject"), max_length=200, blank=True, help_text=_("Email only."))
    body = models.TextField(
        _("text"),
        help_text=_(
            "Placeholders: {name}, {first_name}, {link}, {closes}, {period}, {reading_type}, "
            "{unit} and {organisation}. Keep SMS short: about 160 characters is one message."
        ),
    )

    class Meta:
        ordering = ["purpose", "channel"]
        verbose_name = _("message template")
        verbose_name_plural = _("message templates")
        constraints = [
            models.UniqueConstraint(fields=["purpose", "channel"], name="unique_template"),
        ]

    def __str__(self):
        return f"{self.get_purpose_display()} ({self.get_channel_display()})"

    @staticmethod
    def fill(text, values):
        """Replace known {placeholders}; anything else is left as written."""
        return PLACEHOLDER.sub(lambda match: str(values.get(match[1], match[0])), text)


auditlog.register(MessageTemplate)
auditlog.register(MessageBatch, exclude_fields=["finished_at"])
