from auditlog.registry import auditlog
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.invoicing.models import Invoice, Payment


class BankStatement(models.Model):
    """One imported bank file."""

    file_name = models.CharField(_("file"), max_length=255)
    file_hash = models.CharField(_("checksum"), max_length=64, unique=True)
    format = models.CharField(_("format"), max_length=40)
    account = models.CharField(_("account"), max_length=40, blank=True)
    starts = models.DateField(_("from"), null=True, blank=True)
    ends = models.DateField(_("to"), null=True, blank=True)
    skipped = models.PositiveIntegerField(
        _("already imported"),
        default=0,
        help_text=_("Lines skipped because an earlier file had them."),
    )
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("imported by"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    imported_at = models.DateTimeField(_("imported"), default=timezone.now)

    class Meta:
        ordering = ["-imported_at", "-pk"]
        verbose_name = _("bank file")
        verbose_name_plural = _("bank files")

    def __str__(self):
        return self.file_name

    def get_absolute_url(self):
        return reverse("banking:statement_detail", args=[self.pk])


class BankTransaction(models.Model):
    """A line of a bank file: one payment in or out. The bank's data never
    changes; only what Metra did with it (status, reason, invoice, payment)."""

    class Status(models.TextChoices):
        MATCHED = "matched", _("Recorded")
        REVIEW = "review", _("To review")
        OUTGOING = "outgoing", _("Money out")

    class Reason(models.TextChoices):
        NONE = "", ""
        NO_REFERENCE = "no_reference", _("No reference")
        UNKNOWN_REFERENCE = "unknown", _("No invoice has this reference")
        PARTIAL = "partial", _("Less than the amount to pay")
        TOO_MUCH = "too_much", _("More than the amount to pay")
        ALREADY_PAID = "paid", _("The invoice is already paid")
        CREDITED = "credited", _("The invoice is credited")
        CURRENCY = "currency", _("Not in euros")

    statement = models.ForeignKey(
        BankStatement,
        verbose_name=_("bank file"),
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    key = models.CharField(
        _("line id"),
        max_length=200,
        unique=True,
        help_text=_("The bank's reference for the line, so it is imported only once."),
    )
    booked_on = models.DateField(_("booked"))
    value_date = models.DateField(_("value date"), null=True, blank=True)
    amount = models.DecimalField(_("amount"), max_digits=12, decimal_places=2)
    currency = models.CharField(_("currency"), max_length=3, default="EUR")
    reference = models.CharField(_("reference"), max_length=40, blank=True)
    message = models.CharField(_("message"), max_length=500, blank=True)
    payer_name = models.CharField(_("payer"), max_length=200, blank=True)
    payer_account = models.CharField(_("payer's account"), max_length=40, blank=True)
    bank_reference = models.CharField(_("archive reference"), max_length=100, blank=True)
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.REVIEW
    )
    reason = models.CharField(
        _("reason"), max_length=12, choices=Reason.choices, blank=True, default=""
    )
    invoice = models.ForeignKey(
        Invoice,
        verbose_name=_("invoice"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bank_transactions",
    )
    payment = models.OneToOneField(
        Payment,
        verbose_name=_("payment"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bank_transaction",
    )

    class Meta:
        ordering = ["booked_on", "pk"]
        verbose_name = _("bank line")
        verbose_name_plural = _("bank lines")

    def __str__(self):
        return f"{self.booked_on} {self.amount} {self.currency} {self.payer_name}".strip()


auditlog.register(BankStatement)
auditlog.register(BankTransaction)
