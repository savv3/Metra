"""Invoicing: fee plans say what units pay, invoice runs turn them into draft
invoices for a period, and issuing gives an invoice its number and locks it.

Bookkeeping rules (see docs/architecture.md):
- An issued invoice never changes. Mistakes are corrected with a credit note
  that refers to the original.
- Numbers come from one sequence without gaps, assigned when an invoice is
  issued, inside the transaction that issues it.
- What the invoice says about the seller and the buyer is copied onto it at
  issue time, so later changes to the register do not rewrite old invoices.
- Invoices are kept for the bookkeeping period even when a person is erased:
  erasure anonymises the person, it does not delete their invoices.
"""

import datetime
from decimal import Decimal

from auditlog.registry import auditlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.readings.models import ReadingRound, ReadingType
from apps.register.models import Organisation, Person, Tag, Unit, UnitType

from .money import ZERO, cents, vat_of

VAT_RATE_VALIDATORS = [MinValueValidator(0), MaxValueValidator(100)]


class LockedError(Exception):
    """An issued invoice or its lines were about to be changed."""


class BillingSettings(models.Model):
    """How this installation invoices. One row, edited under Settings."""

    vat_registered = models.BooleanField(
        _("VAT registered"),
        default=False,
        help_text=_(
            "Untick if the organisation is not VAT registered (for example under the "
            "small-business limit): invoices then show no VAT and carry the text below."
        ),
    )
    vat_exemption_text = models.CharField(
        _("text when not VAT registered"),
        max_length=200,
        default="Ej momsskyldig (mervärdesskattelagen 3 §). Ei arvonlisäverovelvollinen (AVL 3 §).",
    )
    default_vat_rate = models.DecimalField(
        _("default VAT rate (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal("25.5"),
        validators=VAT_RATE_VALIDATORS,
    )
    iban = models.CharField(_("IBAN"), max_length=34, blank=True)
    bic = models.CharField(_("BIC"), max_length=11, blank=True)
    payment_terms_days = models.PositiveSmallIntegerField(_("payment terms (days)"), default=14)
    number_prefix = models.CharField(
        _("invoice number prefix"),
        max_length=20,
        blank=True,
        help_text=_("Optional, for example 2026-. Shown before the number."),
    )
    next_number = models.PositiveIntegerField(
        _("next invoice number"),
        default=1,
        validators=[MinValueValidator(1)],
        help_text=_("The number the next issued invoice gets. Numbers never skip."),
    )
    late_interest_text = models.CharField(
        _("late payment interest"),
        max_length=200,
        default="Dröjsmålsränta enligt räntelagen.",
    )
    footer = models.TextField(_("invoice footer"), blank=True)

    class Meta:
        verbose_name = _("invoice settings")
        verbose_name_plural = _("invoice settings")

    def __str__(self):
        return str(_("Invoice settings"))

    def clean(self):
        used = Invoice.objects.aggregate(models.Max("sequence"))["sequence__max"] or 0
        if self.next_number <= used:
            raise ValidationError(
                {
                    "next_number": _("Number %(number)s is already used; numbers cannot repeat.")
                    % {"number": used}
                }
            )

    @classmethod
    def current(cls):
        settings_row = cls.objects.order_by("pk").first()
        return settings_row or cls.objects.create()


class FeePlan(models.Model):
    """What units pay per period, for example "Kommunal vattenavgift".

    A plan applies to the active units of its unit type and, if a tag is set,
    only to units with that tag.
    """

    name = models.CharField(_("name"), max_length=100, unique=True)
    unit_type = models.ForeignKey(
        UnitType, verbose_name=_("unit type"), on_delete=models.PROTECT, related_name="fee_plans"
    )
    tag = models.ForeignKey(
        Tag,
        verbose_name=_("only units with tag"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fee_plans",
    )
    active = models.BooleanField(_("in use"), default=True)
    description = models.TextField(_("description"), blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("fee plan")
        verbose_name_plural = _("fee plans")

    def __str__(self):
        return self.name

    def applies_to(self, unit):
        if unit.unit_type_id != self.unit_type_id:
            return False
        return self.tag_id is None or any(tag.pk == self.tag_id for tag in unit.tags.all())


class FeeLine(models.Model):
    """One fee in a plan: a fixed amount, or a price per unit of usage."""

    class Kind(models.TextChoices):
        FIXED = "fixed", _("Fixed fee")
        USAGE = "usage", _("Usage")

    plan = models.ForeignKey(
        FeePlan, verbose_name=_("fee plan"), on_delete=models.CASCADE, related_name="lines"
    )
    kind = models.CharField(_("kind"), max_length=10, choices=Kind.choices, default=Kind.FIXED)
    description = models.CharField(
        _("text on the invoice"),
        max_length=200,
        help_text=_("{period} becomes the period, for example Grundavgift {period}."),
    )
    unit_price = models.DecimalField(
        _("price"),
        max_digits=12,
        decimal_places=4,
        help_text=_("Without VAT. For usage: the price per unit, for example per m³."),
    )
    quantity = models.DecimalField(
        _("quantity"),
        max_digits=12,
        decimal_places=3,
        default=Decimal("1"),
        help_text=_("Fixed fees only."),
    )
    unit_label = models.CharField(
        _("unit"), max_length=20, blank=True, help_text=_("For example pcs.")
    )
    vat_rate = models.DecimalField(
        _("VAT rate (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal("25.5"),
        validators=VAT_RATE_VALIDATORS,
    )
    reading_type = models.ForeignKey(
        ReadingType,
        verbose_name=_("reading type"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fee_lines",
        help_text=_("Usage only: the reading the usage comes from."),
    )
    condition_field = models.CharField(
        _("only when field"),
        max_length=50,
        blank=True,
        help_text=_("Optional: a unit custom field key, for example connection."),
    )
    condition_value = models.CharField(
        _("has the value"), max_length=100, blank=True, help_text=_("For example Sommar.")
    )
    order = models.PositiveIntegerField(_("order"), default=0)

    class Meta:
        ordering = ["plan", "order", "pk"]
        verbose_name = _("fee line")
        verbose_name_plural = _("fee lines")

    def __str__(self):
        return self.description

    def clean(self):
        if self.kind == self.Kind.USAGE and self.reading_type_id is None:
            raise ValidationError({"reading_type": _("Choose the reading the usage comes from.")})
        if self.kind == self.Kind.FIXED and self.reading_type_id is not None:
            raise ValidationError({"reading_type": _("Only usage fees come from a reading.")})
        if bool(self.condition_field) != bool(self.condition_value):
            raise ValidationError(
                {"condition_value": _("Give both the field and the value, or neither.")}
            )

    def applies_to(self, unit):
        if not self.condition_field:
            return True
        return str(unit.custom_data.get(self.condition_field, "")) == self.condition_value


class FeeTier(models.Model):
    """Usage priced in steps: up to ``up_to`` units at ``unit_price``, then the
    next tier. The last tier has no limit. With no tiers, all usage costs the
    line's price."""

    line = models.ForeignKey(
        FeeLine, verbose_name=_("fee line"), on_delete=models.CASCADE, related_name="tiers"
    )
    up_to = models.DecimalField(
        _("up to"),
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        help_text=_("Units of usage this tier covers up to, in total. Empty for the last tier."),
    )
    unit_price = models.DecimalField(_("price"), max_digits=12, decimal_places=4)

    class Meta:
        ordering = ["line", models.F("up_to").asc(nulls_last=True)]
        verbose_name = _("price tier")
        verbose_name_plural = _("price tiers")

    def __str__(self):
        return f"≤ {self.up_to}" if self.up_to is not None else "…"


class InvoiceRun(models.Model):
    """Draft invoices for one period, built from the fee plans and readings."""

    period_label = models.CharField(
        _("period"), max_length=50, help_text=_("Shown on the invoices, for example 2026.")
    )
    plans = models.ManyToManyField(FeePlan, verbose_name=_("fee plans"), related_name="runs")
    rounds = models.ManyToManyField(
        ReadingRound,
        verbose_name=_("reading rounds"),
        blank=True,
        related_name="invoice_runs",
        help_text=_("Where usage fees take their readings from."),
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

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = _("invoice run")
        verbose_name_plural = _("invoice runs")

    def __str__(self):
        return str(_("Invoices %(period)s") % {"period": self.period_label})

    def get_absolute_url(self):
        return reverse("invoicing:run_detail", args=[self.pk])


class InvoiceQuerySet(models.QuerySet):
    def issued(self):
        return self.exclude(status=Invoice.Status.DRAFT)

    def overdue(self):
        return self.filter(
            status=Invoice.Status.ISSUED,
            kind=Invoice.Kind.INVOICE,
            due_date__lt=timezone.localdate(),
        )


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        ISSUED = "issued", _("Issued")
        CREDITED = "credited", _("Credited")

    class Kind(models.TextChoices):
        INVOICE = "invoice", _("Invoice")
        CREDIT_NOTE = "credit_note", _("Credit note")

    kind = models.CharField(_("kind"), max_length=12, choices=Kind.choices, default=Kind.INVOICE)
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    run = models.ForeignKey(
        InvoiceRun,
        verbose_name=_("invoice run"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="invoices",
    )
    unit = models.ForeignKey(
        Unit, verbose_name=_("unit"), on_delete=models.PROTECT, related_name="invoices"
    )
    person = models.ForeignKey(
        Person, verbose_name=_("recipient"), on_delete=models.PROTECT, related_name="invoices"
    )
    credits = models.ForeignKey(
        "self",
        verbose_name=_("credits invoice"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credit_notes",
    )
    period_label = models.CharField(_("period"), max_length=50, blank=True)
    # Set when issued, never changed afterwards.
    sequence = models.PositiveIntegerField(_("sequence number"), null=True, blank=True, unique=True)
    number = models.CharField(_("number"), max_length=40, blank=True)
    issue_date = models.DateField(_("invoice date"), null=True, blank=True)
    due_date = models.DateField(_("due date"), null=True, blank=True)
    seller = models.JSONField(_("seller"), default=dict, blank=True)
    buyer = models.JSONField(_("buyer"), default=dict, blank=True)
    vat_registered = models.BooleanField(_("VAT registered"), default=False)
    total_net = models.DecimalField(
        _("total without VAT"), max_digits=12, decimal_places=2, default=ZERO
    )
    total_vat = models.DecimalField(_("VAT"), max_digits=12, decimal_places=2, default=ZERO)
    total = models.DecimalField(_("total"), max_digits=12, decimal_places=2, default=ZERO)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("issued by"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    issued_at = models.DateTimeField(_("issued"), null=True, blank=True)
    # Drafts only: what to check before issuing, e.g. a missing reading.
    problems = models.JSONField(_("to check"), default=list, blank=True)
    note = models.TextField(_("text on the invoice"), blank=True)
    created_at = models.DateTimeField(_("created"), auto_now_add=True)

    objects = InvoiceQuerySet.as_manager()

    class Meta:
        ordering = ["-issue_date", "-sequence", "-pk"]
        verbose_name = _("invoice")
        verbose_name_plural = _("invoices")
        permissions = [("issue_invoice", _("Can issue invoices and credit notes"))]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "unit"],
                condition=models.Q(kind="invoice"),
                name="one_invoice_per_unit_and_run",
            ),
        ]

    def __str__(self):
        label = self.get_kind_display()
        return f"{label} {self.number}" if self.number else f"{label} ({self.unit})"

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            stored = Invoice.objects.filter(pk=self.pk).values("status").first()
            if stored and stored["status"] != self.Status.DRAFT:
                raise LockedError(f"{self} is issued and cannot change.")
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("invoicing:invoice_detail", args=[self.pk])

    def delete(self, *args, **kwargs):
        if not self.is_draft:
            raise LockedError(f"{self} is issued and cannot be deleted.")
        return super().delete(*args, **kwargs)

    @property
    def is_draft(self):
        return self.status == self.Status.DRAFT

    @property
    def is_overdue(self):
        return (
            self.status == self.Status.ISSUED
            and self.kind == self.Kind.INVOICE
            and self.due_date is not None
            and self.due_date < timezone.localdate()
        )

    # Totals

    def vat_breakdown(self):
        """[(rate, base, vat)] per VAT rate, VAT rounded once per rate."""
        bases = {}
        for line in self.lines.all():
            rate = line.vat_rate if self.effective_vat_registered else ZERO
            bases[rate] = bases.get(rate, ZERO) + line.net
        return [(rate, base, vat_of(base, rate)) for rate, base in sorted(bases.items())]

    @property
    def effective_vat_registered(self):
        if self.is_draft:
            return BillingSettings.current().vat_registered
        return self.vat_registered

    def compute_totals(self):
        breakdown = self.vat_breakdown()
        self.total_net = sum((base for _rate, base, _vat in breakdown), ZERO)
        self.total_vat = sum((vat for _rate, _base, vat in breakdown), ZERO)
        self.total = self.total_net + self.total_vat

    # Issuing

    def check_can_issue(self):
        problems = []
        if not self.is_draft:
            problems.append(_("It is already issued."))
        if not self.lines.exists():
            problems.append(_("It has no lines."))
        if not self.buyer_from_register()["address"]:
            problems.append(_("The recipient has no address."))
        organisation = Organisation.current()
        if organisation is None or not (
            organisation.name and organisation.business_id and organisation.street_address
        ):
            problems.append(
                _("Fill in the organisation's name, address and business ID under Settings.")
            )
        elif BillingSettings.current().vat_registered and not organisation.vat_number:
            problems.append(_("A VAT registered organisation needs its VAT number under Settings."))
        if self.kind == self.Kind.CREDIT_NOTE:
            self.compute_totals()
            if self.total > 0:
                problems.append(_("A credit note's total must be negative."))
            elif self.credits is not None and -self.total > self.credits.creditable_amount():
                problems.append(_("It credits more than is left of the invoice."))
        elif self.total_from_lines() < 0:
            problems.append(_("An invoice's total cannot be negative; use a credit note."))
        return problems

    def total_from_lines(self):
        self.compute_totals()
        return self.total

    def creditable_amount(self):
        """How much of this invoice is not yet credited."""
        credited = sum(
            (note.total for note in self.credit_notes.exclude(status=self.Status.DRAFT)), ZERO
        )
        return self.total + credited

    def buyer_from_register(self):
        person = self.person
        street, postal_code, city = person.street_address, person.postal_code, person.city
        if not (street or city):
            street, postal_code, city = (
                self.unit.street_address,
                self.unit.postal_code,
                self.unit.city,
            )
        place = " ".join(part for part in [postal_code, city] if part)
        return {
            "name": person.full_name,
            "address": [line for line in [street, place] if line],
            "email": person.email,
            "unit": self.unit.name,
        }

    @transaction.atomic
    def issue(self, user=None):
        """Give the invoice its number and dates and lock it."""
        problems = self.check_can_issue()
        if problems:
            raise ValidationError(problems)
        billing = BillingSettings.objects.select_for_update().get(pk=BillingSettings.current().pk)
        organisation = Organisation.current()
        today = timezone.localdate()
        self.sequence = billing.next_number
        self.number = f"{billing.number_prefix}{billing.next_number}"
        billing.next_number += 1
        billing.save(update_fields=["next_number"])
        self.issue_date = today
        self.due_date = (
            today + datetime.timedelta(days=billing.payment_terms_days)
            if self.kind == self.Kind.INVOICE
            else None
        )
        self.vat_registered = billing.vat_registered
        self.seller = {
            "name": organisation.name if organisation else "",
            "address": [
                line
                for line in [
                    organisation.street_address if organisation else "",
                    " ".join(p for p in [organisation.postal_code, organisation.city] if p)
                    if organisation
                    else "",
                ]
                if line
            ],
            "business_id": organisation.business_id if organisation else "",
            "vat_number": organisation.vat_number if organisation else "",
            "email": organisation.email if organisation else "",
            "phone": organisation.phone if organisation else "",
            "iban": billing.iban,
            "bic": billing.bic,
            "vat_exemption_text": "" if billing.vat_registered else billing.vat_exemption_text,
            "late_interest_text": billing.late_interest_text,
            "footer": billing.footer,
        }
        self.buyer = self.buyer_from_register()
        self.compute_totals()
        self.problems = []
        self.status = self.Status.ISSUED
        self.issued_by = user
        self.issued_at = timezone.now()
        super().save()
        if self.kind == self.Kind.CREDIT_NOTE and self.credits is not None:
            if self.credits.creditable_amount() <= 0:
                # The one change an issued invoice gets: fully credited.
                Invoice.objects.filter(pk=self.credits_id).update(status=self.Status.CREDITED)
        return self

    def make_credit_note(self, user=None):
        """A draft credit note with this invoice's lines, negated. Edit it to
        credit only part, then issue it."""
        if self.is_draft or self.kind != self.Kind.INVOICE:
            raise ValidationError(_("Only issued invoices can be credited."))
        note = Invoice.objects.create(
            kind=self.Kind.CREDIT_NOTE,
            unit=self.unit,
            person=self.person,
            credits=self,
            period_label=self.period_label,
            note=str(_("Credit note for invoice %(number)s.") % {"number": self.number}),
        )
        for line in self.lines.all():
            InvoiceLine.objects.create(
                invoice=note,
                description=line.description,
                quantity=-line.quantity,
                unit_label=line.unit_label,
                unit_price=line.unit_price,
                vat_rate=line.vat_rate,
                order=line.order,
            )
        note.compute_totals()
        note.save()
        return note


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(
        Invoice, verbose_name=_("invoice"), on_delete=models.CASCADE, related_name="lines"
    )
    description = models.CharField(_("description"), max_length=200)
    quantity = models.DecimalField(_("quantity"), max_digits=12, decimal_places=3, default=1)
    unit_label = models.CharField(_("unit"), max_length=20, blank=True)
    unit_price = models.DecimalField(_("unit price"), max_digits=12, decimal_places=4)
    vat_rate = models.DecimalField(
        _("VAT rate (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal("25.5"),
        validators=VAT_RATE_VALIDATORS,
    )
    fee_line = models.ForeignKey(
        FeeLine,
        verbose_name=_("fee line"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    order = models.PositiveIntegerField(_("order"), default=0)

    class Meta:
        ordering = ["invoice", "order", "pk"]
        verbose_name = _("invoice line")
        verbose_name_plural = _("invoice lines")

    def __str__(self):
        return self.description

    def save(self, *args, **kwargs):
        self._check_draft()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._check_draft()
        return super().delete(*args, **kwargs)

    @property
    def net(self):
        """The line's amount without VAT, rounded to cents."""
        return cents(self.quantity * self.unit_price)

    def _check_draft(self):
        if (
            self.invoice_id
            and not Invoice.objects.filter(pk=self.invoice_id, status=Invoice.Status.DRAFT).exists()
        ):
            raise LockedError("Lines of an issued invoice cannot change.")


auditlog.register(BillingSettings)
auditlog.register(FeePlan)
auditlog.register(FeeLine)
auditlog.register(FeeTier)
auditlog.register(InvoiceRun, m2m_fields={"plans", "rounds"})
auditlog.register(Invoice, exclude_fields=["created_at"])
auditlog.register(InvoiceLine)
