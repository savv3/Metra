"""The books: financial years, the chart of accounts, voucher series,
vouchers with their lines and receipts.

Every entry rests on a voucher (tosite). A voucher is a draft until it is
posted; posting checks that it balances, gives it the next number in its
series for the year (gapless, since posted vouchers are never deleted) and
locks it. A posted voucher, its lines and its receipts never change again
(the models refuse it): a mistake is corrected with a new voucher that
reverses it, and both stay in the books. Receipts can still be added to a
posted voucher, but not removed.
"""

import datetime
import secrets
from decimal import Decimal

from auditlog.registry import auditlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils import formats, timezone
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from . import countries

ZERO = Decimal("0.00")


class LockedError(ValidationError):
    """A posted voucher, or a closed year, cannot change."""


def months_between(start, end):
    """How many months a period from ``start`` to ``end`` (inclusive) covers,
    counting a started month as a whole one."""
    after = end + datetime.timedelta(days=1)
    months = (after.year - start.year) * 12 + after.month - start.month
    return months + (1 if after.day > start.day else 0)


def _years_after(date, years):
    try:
        return date.replace(year=date.year + years)
    except ValueError:  # 29 February
        return date.replace(year=date.year + years, day=28)


class FiscalYear(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", _("Open")
        CLOSED = "closed", _("Closed")

    start = models.DateField(_("first day"), unique=True)
    end = models.DateField(_("last day"), unique=True)
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.OPEN
    )
    country = models.CharField(_("country"), max_length=2, default=countries.DEFAULT)
    created_at = models.DateTimeField(_("created"), auto_now_add=True)

    class Meta:
        ordering = ["-start"]
        verbose_name = _("financial year")
        verbose_name_plural = _("financial years")

    def __str__(self):
        if (self.start.month, self.start.day, self.end.month, self.end.day) == (1, 1, 12, 31) and (
            self.start.year == self.end.year
        ):
            return str(self.start.year)
        start = formats.date_format(self.start, "SHORT_DATE_FORMAT")
        end = formats.date_format(self.end, "SHORT_DATE_FORMAT")
        return f"{start}–{end}"

    def get_absolute_url(self):
        return reverse("metra_bookkeeping:year_detail", args=[self.pk])

    @property
    def is_open(self):
        return self.status == self.Status.OPEN

    @property
    def books_kept_until(self):
        """The financial statements, journal, ledger, chart of accounts and list
        of books are kept at least 10 years from the end of the year (KPL 2:10)."""
        return _years_after(self.end, 10)

    @property
    def vouchers_kept_until(self):
        """Vouchers and receipts are kept at least 6 years from the end of the
        calendar year in which the financial year ended (KPL 2:10)."""
        return datetime.date(self.end.year + 6, 12, 31)

    def contains(self, date):
        return self.start <= date <= self.end

    @classmethod
    def for_date(cls, date):
        return cls.objects.filter(start__lte=date, end__gte=date).first()

    @classmethod
    def current(cls):
        """The open year that today falls in, else the newest open one."""
        today = timezone.localdate()
        open_years = cls.objects.filter(status=cls.Status.OPEN)
        return open_years.filter(start__lte=today, end__gte=today).first() or open_years.first()

    def previous(self):
        return FiscalYear.objects.filter(end__lt=self.start).order_by("-end").first()

    def clean(self):
        if not (self.start and self.end):
            return
        if self.end <= self.start:
            raise ValidationError({"end": _("The year must end after it starts.")})
        rules = countries.get(self.country)
        shortest, longest = rules.FIRST_YEAR_MONTHS
        months = months_between(self.start, self.end)
        if not shortest <= months <= longest:
            raise ValidationError(
                _(
                    "A financial year is %(usual)s months; a first or changed one "
                    "%(min)s to %(max)s."
                )
                % {"usual": rules.YEAR_MONTHS, "min": shortest, "max": longest}
            )
        others = FiscalYear.objects.exclude(pk=self.pk)
        if others.filter(start__lte=self.end, end__gte=self.start).exists():
            raise ValidationError(_("The year overlaps another financial year."))
        before = others.filter(end__lt=self.start).order_by("-end").first()
        if before and before.end + datetime.timedelta(days=1) != self.start:
            raise ValidationError(
                {
                    "start": _("The year must start the day after the previous one ends (%(day)s).")
                    % {"day": formats.date_format(before.end + datetime.timedelta(days=1))}
                }
            )
        after = others.filter(start__gt=self.end).order_by("start").first()
        if after and self.end + datetime.timedelta(days=1) != after.start:
            raise ValidationError(
                {"end": _("The year must end the day before the next one starts.")}
            )
        if self.pk and self.vouchers.exclude(date__range=(self.start, self.end)).exists():
            raise ValidationError(_("Some of the year's vouchers would fall outside it."))

    def check_open(self):
        if not self.is_open:
            raise LockedError(
                _("The financial year %(year)s is closed.") % {"year": self}, code="closed"
            )


class Account(models.Model):
    class Kind(models.TextChoices):
        ASSET = "asset", _("Asset")
        LIABILITY = "liability", _("Liability")
        EQUITY = "equity", _("Equity")
        INCOME = "income", _("Income")
        EXPENSE = "expense", _("Expense")

    number = models.CharField(
        _("number"),
        max_length=8,
        unique=True,
        validators=[RegexValidator(r"^[0-9]{1,8}$", _("Use digits only."))],
    )
    name = models.CharField(_("name"), max_length=100)
    kind = models.CharField(_("kind"), max_length=10, choices=Kind.choices)
    active = models.BooleanField(
        _("in use"), default=True, help_text=_("Accounts not in use cannot get new entries.")
    )

    class Meta:
        ordering = ["number"]
        verbose_name = _("account")
        verbose_name_plural = _("accounts")

    def __str__(self):
        return f"{self.number} {self.name}"

    def get_absolute_url(self):
        return reverse("metra_bookkeeping:account_ledger", args=[self.pk])

    @property
    def debit_normal(self):
        """Assets and expenses grow with debits; the rest with credits."""
        return self.kind in (self.Kind.ASSET, self.Kind.EXPENSE)

    def has_entries(self):
        return self.pk is not None and self.lines.exists()

    def clean(self):
        if self.pk and self.has_entries():
            stored = Account.objects.get(pk=self.pk)
            if (stored.number, stored.kind) != (self.number, self.kind):
                raise ValidationError(
                    _(
                        "The account has entries, so its number and kind stay as they are. "
                        "Rename it, or stop using it and add a new one."
                    )
                )

    def delete(self, *args, **kwargs):
        if self.has_entries():
            raise LockedError(_("An account with entries cannot be deleted."))
        return super().delete(*args, **kwargs)

    @classmethod
    def create_chart(cls, chart, language=None):
        """Add the accounts of a chart template (see countries) in ``language``."""
        cls.objects.bulk_create(
            [
                cls(number=account.number, name=account.name(language), kind=account.kind)
                for account in chart.accounts
            ]
        )


class VoucherSeries(models.Model):
    """Vouchers are numbered per series and year, for example one series
    for receipts entered by hand and, later, one for invoices."""

    code = models.CharField(
        _("code"),
        max_length=5,
        unique=True,
        blank=True,
        help_text=_("Shown before the number, for example M for M12. Can be empty for one series."),
    )
    name = models.CharField(_("name"), max_length=100)

    class Meta:
        ordering = ["code"]
        verbose_name = _("voucher series")
        verbose_name_plural = _("voucher series")

    def __str__(self):
        return f"{self.code} {self.name}" if self.code else self.name

    @classmethod
    def default(cls):
        series = cls.objects.first()
        if series is None:
            series = cls.objects.create(code="", name=gettext("Vouchers"))
        return series


class Voucher(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        POSTED = "posted", _("Posted")

    class Kind(models.TextChoices):
        NORMAL = "normal", _("Voucher")
        OPENING = "opening", _("Opening balances")
        REVERSAL = "reversal", _("Reversal")

    year = models.ForeignKey(
        FiscalYear,
        verbose_name=_("financial year"),
        on_delete=models.PROTECT,
        related_name="vouchers",
    )
    series = models.ForeignKey(
        VoucherSeries, verbose_name=_("series"), on_delete=models.PROTECT, related_name="vouchers"
    )
    number = models.PositiveIntegerField(_("number"), null=True, blank=True)
    date = models.DateField(_("date"))
    description = models.CharField(_("description"), max_length=200)
    kind = models.CharField(_("kind"), max_length=10, choices=Kind.choices, default=Kind.NORMAL)
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    reverses = models.ForeignKey(
        "self",
        verbose_name=_("reverses"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversals",
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
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("posted by"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    posted_at = models.DateTimeField(_("posted"), null=True, blank=True)

    class Meta:
        ordering = ["date", "series__code", "number", "pk"]
        verbose_name = _("voucher")
        verbose_name_plural = _("vouchers")
        permissions = [("post_voucher", "Can post vouchers")]
        constraints = [
            models.UniqueConstraint(
                fields=["year", "series", "number"], name="voucher_number_unique_per_series"
            )
        ]

    def __str__(self):
        if self.number is None:
            return gettext("Draft voucher")
        return gettext("Voucher %(number)s") % {"number": self.display_number}

    def save(self, *args, **kwargs):
        self.check_draft()
        if self.status != self.Status.DRAFT or self.number is not None:
            # Only post() gives a voucher its number and posts it.
            raise LockedError(_("Vouchers are posted with post()."))
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("metra_bookkeeping:voucher_detail", args=[self.pk])

    def delete(self, *args, **kwargs):
        self.check_draft()
        return super().delete(*args, **kwargs)

    @property
    def display_number(self):
        if self.number is None:
            return ""
        return f"{self.series.code}{self.number}"

    @property
    def is_draft(self):
        return self.status == self.Status.DRAFT

    def _stored_status(self):
        if self.pk is None:
            return None
        return Voucher.objects.filter(pk=self.pk).values_list("status", flat=True).first()

    def check_draft(self):
        """Refuse a change to a voucher that is posted (as stored)."""
        if self._stored_status() == self.Status.POSTED:
            raise LockedError(
                _("A posted voucher cannot change. Correct it with a reversing voucher."),
                code="posted",
            )

    def totals(self):
        sums = self.lines.aggregate(debit=models.Sum("debit"), credit=models.Sum("credit"))
        return sums["debit"] or ZERO, sums["credit"] or ZERO

    @property
    def total(self):
        return self.totals()[0]

    def problems(self):
        """What stops this draft from being posted, as sentences."""
        problems = []
        year = self.year
        if not year.is_open:
            problems.append(gettext("The financial year %(year)s is closed.") % {"year": year})
        if not year.contains(self.date):
            problems.append(
                gettext("The date is outside the financial year %(year)s.") % {"year": year}
            )
        lines = list(self.lines.select_related("account"))
        if len(lines) < 2:
            problems.append(gettext("A voucher needs at least two lines."))
        debit, credit = self.totals()
        if debit != credit:
            problems.append(
                gettext("Debits (%(debit)s) and credits (%(credit)s) differ.")
                % {
                    "debit": formats.number_format(debit, 2),
                    "credit": formats.number_format(credit, 2),
                }
            )
        elif debit == ZERO and lines:
            problems.append(gettext("The amounts are zero."))
        for line in lines:
            if not line.account.active:
                problems.append(
                    gettext("The account %(account)s is not in use.") % {"account": line.account}
                )
        return problems

    def post(self, user=None):
        """Number and lock the voucher. Raises ValidationError when it cannot be posted."""
        with transaction.atomic():
            # SQLite transactions here take the write lock up front
            # (IMMEDIATE), so the number below cannot be taken twice.
            voucher = Voucher.objects.select_related("year", "series").get(pk=self.pk)
            if not voucher.is_draft:
                raise LockedError(_("The voucher is already posted."))
            if problems := voucher.problems():
                raise ValidationError(problems)
            last = Voucher.objects.filter(year=voucher.year, series=voucher.series).aggregate(
                last=models.Max("number")
            )["last"]
            now = timezone.now()
            Voucher.objects.filter(pk=self.pk, status=self.Status.DRAFT).update(
                status=self.Status.POSTED,
                number=(last or 0) + 1,
                posted_by=user,
                posted_at=now,
            )
            self.refresh_from_db()
            # The audit log does not see update(); record the posting there.
            from auditlog.models import LogEntry

            LogEntry.objects.log_create(
                self,
                action=LogEntry.Action.UPDATE,
                changes={"status": ["draft", "posted"], "number": [None, self.number]},
                force_log=True,
            )
        return self

    @property
    def reversed_by(self):
        return self.reversals.filter(status=self.Status.POSTED).first()

    def can_be_reversed(self):
        return (
            self.status == self.Status.POSTED
            and self.kind != self.Kind.REVERSAL
            and not self.reversals.exists()
        )

    def reverse(self, user=None, date=None, note=""):
        """Post a new voucher that cancels this one, dated ``date`` (today by
        default), in the open financial year that date falls in."""
        if not self.can_be_reversed():
            raise ValidationError(_("This voucher cannot be reversed."))
        date = date or timezone.localdate()
        year = FiscalYear.for_date(date)
        if year is None or not year.is_open:
            raise ValidationError(_("There is no open financial year for that date."))
        description = gettext("Reversal of voucher %(number)s") % {"number": self.display_number}
        if note:
            description = f"{description}: {note}"
        with transaction.atomic():
            reversal = Voucher.objects.create(
                year=year,
                series=self.series,
                date=date,
                description=description[:200],
                kind=self.Kind.REVERSAL,
                reverses=self,
                created_by=user,
            )
            VoucherLine.objects.bulk_create(
                [
                    VoucherLine(
                        voucher=reversal,
                        account=line.account,
                        debit=line.credit,
                        credit=line.debit,
                        description=line.description,
                        order=line.order,
                    )
                    for line in self.lines.all()
                ]
            )
            reversal.post(user)
        return reversal


class VoucherLine(models.Model):
    voucher = models.ForeignKey(
        Voucher, verbose_name=_("voucher"), on_delete=models.CASCADE, related_name="lines"
    )
    account = models.ForeignKey(
        Account, verbose_name=_("account"), on_delete=models.PROTECT, related_name="lines"
    )
    debit = models.DecimalField(_("debit"), max_digits=12, decimal_places=2, default=ZERO)
    credit = models.DecimalField(_("credit"), max_digits=12, decimal_places=2, default=ZERO)
    description = models.CharField(_("description"), max_length=200, blank=True)
    order = models.PositiveIntegerField(_("order"), default=0)

    class Meta:
        ordering = ["order", "pk"]
        verbose_name = _("voucher line")
        verbose_name_plural = _("voucher lines")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(debit__gte=0, credit__gte=0)
                & (models.Q(debit=0) | models.Q(credit=0)),
                name="voucherline_one_side",
            )
        ]

    def __str__(self):
        return f"{self.account} {self.debit or ''}/{self.credit or ''}"

    def save(self, *args, **kwargs):
        self.voucher.check_draft()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.voucher.check_draft()
        return super().delete(*args, **kwargs)

    @property
    def amount(self):
        """Debit as positive, credit as negative."""
        return self.debit - self.credit

    def clean(self):
        debit, credit = self.debit or ZERO, self.credit or ZERO
        if debit < 0 or credit < 0:
            raise ValidationError(_("Amounts are positive; use the other column instead."))
        if debit and credit:
            raise ValidationError(_("A line is either a debit or a credit, not both."))
        if not debit and not credit:
            raise ValidationError(_("Enter a debit or a credit."))


def receipt_path(receipt, filename):
    # A random folder per file keeps names readable without clashes or guessing.
    return f"bookkeeping/{timezone.now():%Y}/{secrets.token_hex(8)}/{filename}"


class Receipt(models.Model):
    """A scanned or photographed receipt, invoice or other document a voucher
    rests on. It belongs to the bookkeeping material and is kept as long."""

    voucher = models.ForeignKey(
        Voucher, verbose_name=_("voucher"), on_delete=models.CASCADE, related_name="receipts"
    )
    file = models.FileField(_("file"), upload_to=receipt_path, max_length=300)
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
        verbose_name = _("receipt")
        verbose_name_plural = _("receipts")

    def __str__(self):
        return f"{self.name} ({filesizeformat(self.size)})"

    def save(self, *args, **kwargs):
        if self.pk:
            raise LockedError(_("A receipt cannot be changed."))
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.voucher.check_draft()
        return super().delete(*args, **kwargs)


@receiver(post_delete, sender=Receipt)
def _delete_receipt_file(sender, instance, **kwargs):
    instance.file.delete(save=False)


auditlog.register(FiscalYear)
auditlog.register(Account)
auditlog.register(VoucherSeries)
auditlog.register(Voucher, exclude_fields=["created_at"])
auditlog.register(VoucherLine)
auditlog.register(Receipt, exclude_fields=["file"])
