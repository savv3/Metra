"""Messages sent to people, grouped in batches (for example "the 2026 links"),
and the templates their text comes from.

A message body is stored as sent, except that a personal self-service link
is replaced by a placeholder: links are kept only as hashes (see
apps.selfservice), so a copy of the database must not hold them either.
"""

import re
import secrets

from auditlog.registry import auditlog
from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils import timezone
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy as _

from apps.readings.models import ReadingRound
from apps.register.models import Organisation, Person, Unit


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
        BROADCAST = "broadcast", _("Message")
        ALERT = "alert", _("Urgent alert")
        NEWSLETTER = "newsletter", _("Newsletter")
        INVOICES = "invoices", _("Invoices")
        PAYMENT_REMINDERS = "payment_reminders", _("Payment reminders")

    class Scope(models.TextChoices):
        ALL = "all", _("All units")
        MISSING = "missing", _("Units missing a reading")

    class Channels(models.TextChoices):
        """For messages written by staff: which channels each person gets."""

        SMS = "sms", _("SMS only")
        EMAIL = "email", _("Email only")
        SMS_OR_EMAIL = "sms_or_email", _("SMS, or email for those without a phone")
        SMS_AND_EMAIL = "sms_and_email", _("Both SMS and email")

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
    # Messages written by staff (kind broadcast or alert).
    channels = models.CharField(_("channels"), max_length=20, choices=Channels.choices, blank=True)
    subject = models.CharField(_("email subject"), max_length=200, blank=True)
    body = models.TextField(_("text"), blank=True)
    email_body = models.TextField(_("email text"), blank=True)
    audience = models.CharField(_("recipients"), max_length=300, blank=True)
    # [[person id, unit id], ...] as confirmed before sending.
    recipients = models.JSONField(default=list, blank=True, editable=False)
    notice = models.ForeignKey(
        "core.Notice",
        verbose_name=_("notice"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batches",
    )
    # The link SMS recipients get to the attached files. Only its hash is kept,
    # like self-service links, so a copy of the database cannot open it.
    files_token_hash = models.CharField(max_length=64, blank=True, editable=False)
    files_expire_at = models.DateTimeField(_("file link expires"), null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = _("send-out")
        verbose_name_plural = _("send-outs")
        permissions = [
            ("send_broadcast", _("Can send messages and alerts to everyone")),
            ("send_newsletter", _("Can send newsletters")),
            ("send_unit_message", _("Can send a message to one unit")),
        ]

    def __str__(self):
        label = self.get_kind_display()
        if self.round_id:
            return f"{label}: {self.round}"
        if self.is_written and self.body:
            return f"{label}: {Truncator(self.body).chars(40)}"
        return label

    def get_absolute_url(self):
        return reverse("messaging:batch_detail", args=[self.pk])

    @property
    def is_written(self):
        """A message staff wrote, as opposed to links or reminders."""
        return self.kind in (self.Kind.BROADCAST, self.Kind.ALERT, self.Kind.NEWSLETTER)


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


def organisation_placeholders():
    """{organisation}, {organisation_phone}, ... from the public contact details."""
    organisation = Organisation.current()
    if organisation is None:
        return dict.fromkeys(
            [
                "organisation",
                "organisation_phone",
                "organisation_email",
                "organisation_website",
                "emergency_phone",
            ],
            "",
        )
    return {
        "organisation": organisation.public_name,
        "organisation_phone": organisation.phone,
        "organisation_email": organisation.email,
        "organisation_website": organisation.website,
        "emergency_phone": organisation.emergency_phone or organisation.phone,
    }


class MessageTemplate(models.Model):
    """The text of one kind of message on one channel, edited under Settings."""

    class Purpose(models.TextChoices):
        LINK = "link", _("Self-service link")
        REMINDER = "reminder", _("Reminder")
        INVOICE = "invoice", _("Invoice")
        PAYMENT_REMINDER = "payment_reminder", _("Payment reminder")

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
            "{unit}, {organisation}, {organisation_phone}, {organisation_email}, "
            "{organisation_website} and {emergency_phone}. Keep SMS short: about 160 "
            "characters is one message."
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


class ConsentRecord(models.Model):
    """One yes or no to the newsletter, kept as a record of who agreed when and
    how. A person's current answer is their newest record; no record is a no."""

    class Source(models.TextChoices):
        SELF_SERVICE = "self_service", _("Self-service page")
        STAFF = "staff", _("Entered by staff")
        UNSUBSCRIBE_LINK = "unsubscribe_link", _("Unsubscribe link")

    person = models.ForeignKey(
        Person, verbose_name=_("person"), on_delete=models.CASCADE, related_name="consents"
    )
    subscribed = models.BooleanField(_("wants the newsletter"))
    source = models.CharField(_("source"), max_length=20, choices=Source.choices)
    recorded_at = models.DateTimeField(_("recorded"), default=timezone.now)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("recorded by"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    note = models.CharField(
        _("note"), max_length=200, blank=True, help_text=_("For example: signed form, 3 May.")
    )

    class Meta:
        ordering = ["-recorded_at", "-pk"]
        verbose_name = _("newsletter consent")
        verbose_name_plural = _("newsletter consents")

    def __str__(self):
        answer = _("yes") if self.subscribed else _("no")
        return f"{self.person}: {answer} ({self.get_source_display()})"

    @classmethod
    def current(cls, person):
        """The person's newest record, or None if they never answered."""
        return cls.objects.filter(person=person).first()

    @classmethod
    def subscribed_people(cls):
        """People whose newest answer is yes."""
        newest = cls.objects.filter(person=models.OuterRef("pk")).order_by("-recorded_at", "-pk")
        return Person.objects.annotate(
            newsletter=models.Subquery(newest.values("subscribed")[:1])
        ).filter(newsletter=True)

    @classmethod
    def record(cls, person, subscribed, source, by=None, note=""):
        """Add a record if the answer changes; returns the person's current record."""
        current = cls.current(person)
        if current is not None and current.subscribed == subscribed:
            return current
        return cls.objects.create(
            person=person, subscribed=subscribed, source=source, recorded_by=by, note=note
        )


def attachment_path(attachment, filename):
    # A random folder per file keeps names readable without clashes or guessing.
    return f"attachments/{timezone.now():%Y}/{secrets.token_hex(8)}/{filename}"


class Attachment(models.Model):
    """A file sent with a message or newsletter: attached to emails, and a
    link in SMS. Until the send-out is confirmed it has no batch."""

    batch = models.ForeignKey(
        MessageBatch,
        verbose_name=_("send-out"),
        on_delete=models.CASCADE,
        related_name="attachments",
        null=True,
        blank=True,
    )
    file = models.FileField(_("file"), upload_to=attachment_path, max_length=300)
    name = models.CharField(_("name"), max_length=200)
    size = models.PositiveIntegerField(_("size"))
    content_type = models.CharField(_("type"), max_length=100)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("uploaded by"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    uploaded_at = models.DateTimeField(_("uploaded"), auto_now_add=True)

    class Meta:
        ordering = ["pk"]
        verbose_name = _("attachment")
        verbose_name_plural = _("attachments")

    def __str__(self):
        return f"{self.name} ({filesizeformat(self.size)})"


@receiver(post_delete, sender=Attachment)
def _delete_attachment_file(sender, instance, **kwargs):
    instance.file.delete(save=False)


auditlog.register(MessageTemplate)
auditlog.register(ConsentRecord)
auditlog.register(MessageBatch, exclude_fields=["finished_at", "recipients", "files_token_hash"])
auditlog.register(Attachment)
