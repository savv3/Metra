import secrets
import uuid

from auditlog.registry import auditlog
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def new_secret():
    return secrets.token_urlsafe(32)


class WebhookEndpoint(models.Model):
    """An address that gets a signed POST for each event it subscribes to."""

    url = models.URLField(_("address"), max_length=500)
    description = models.CharField(_("description"), max_length=200, blank=True)
    # Event names, like "invoice.issued". An empty list subscribes to nothing.
    events = models.JSONField(_("events"), default=list, blank=True)
    # Signs every request, so the receiver can tell it came from Metra.
    secret = models.CharField(_("secret"), max_length=100, default=new_secret, editable=False)
    active = models.BooleanField(_("active"), default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("created by"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(_("created"), auto_now_add=True)

    class Meta:
        ordering = ["description", "url", "pk"]
        verbose_name = _("webhook endpoint")
        verbose_name_plural = _("webhook endpoints")

    def __str__(self):
        return self.description or self.url

    def get_absolute_url(self):
        return reverse("metra_webhooks:endpoint_edit", args=[self.pk])

    def rotate_secret(self):
        self.secret = new_secret()
        self.save(update_fields=["secret"])


class WebhookDelivery(models.Model):
    """One event to send to one endpoint, with how the sending went."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Waiting")
        DELIVERED = "delivered", _("Delivered")
        FAILED = "failed", _("Failed, will retry")
        GIVEN_UP = "given_up", _("Given up")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    endpoint = models.ForeignKey(
        WebhookEndpoint,
        verbose_name=_("endpoint"),
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    event = models.CharField(_("event"), max_length=100)
    # The whole body that is sent: id, event, occurred_at and data. Kept as it
    # was, so a retry sends the same thing.
    payload = models.JSONField(_("payload"), default=dict)
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.PENDING
    )
    attempts = models.PositiveSmallIntegerField(_("attempts"), default=0)
    next_attempt_at = models.DateTimeField(_("next attempt"), default=timezone.now)
    last_attempt_at = models.DateTimeField(_("last attempt"), null=True, blank=True)
    response_status = models.PositiveSmallIntegerField(_("response code"), null=True, blank=True)
    response_excerpt = models.CharField(_("response"), max_length=500, blank=True)
    error = models.CharField(_("error"), max_length=500, blank=True)
    created_at = models.DateTimeField(_("created"), default=timezone.now)
    delivered_at = models.DateTimeField(_("delivered"), null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = _("webhook delivery")
        verbose_name_plural = _("webhook deliveries")
        indexes = [models.Index(fields=["status", "next_attempt_at"])]
        # Deliveries are made by the app; staff only look at them.
        default_permissions = ("view",)

    def __str__(self):
        return f"{self.event} → {self.endpoint}"


# The secret stays out of the audit log, which many staff can read.
auditlog.register(WebhookEndpoint, exclude_fields=["secret"])
auditlog.register(
    WebhookDelivery,
    exclude_fields=[
        "payload",
        "attempts",
        "next_attempt_at",
        "last_attempt_at",
        "response_excerpt",
        "error",
    ],
)
