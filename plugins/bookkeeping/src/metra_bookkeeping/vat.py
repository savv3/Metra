"""The VAT summary: sales and purchase VAT per VAT period, by rate, for
checking and filling in the VAT return (arvonlisäveroilmoitus).

Only lines with a VAT code count; the VAT itself is on lines on the VAT
accounts (from the posting settings), the base on the other lines. The
period follows the supply, not the voucher date (AVL 15 §):

- an invoice or credit note from Metra counts at the end of its supply
  period (a continuous supply such as water is made at the end of each
  billing period); without one, on the invoice date;
- but the part of an invoice paid before its supply is made is an advance
  payment, taxed for the month the payment was received;
- a reversal counts where the voucher it reverses counted, since a VAT
  error is corrected for the period it was made in;
- anything else (receipts entered by hand) counts on its voucher date.

Reverse charge, imports (also across the Åland tax border) and entries
made without a VAT code are not in the summary; it says so, and it is
marked not ready while such entries, drafts or records waiting from
invoicing could change it.
"""

import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Q
from django.utils import timezone

from apps.plugins import api

from . import countries, postings
from .models import (
    ZERO,
    Posting,
    PostingSettings,
    VatCode,
    VatRegistration,
    Voucher,
    VoucherLine,
)

CENT = Decimal("0.01")
# How far outside the asked dates a voucher can be and still count in them:
# an invoice issued months after its supply period, or a reversal later.
REACH = datetime.timedelta(days=550)


def _month_end(date):
    first_of_next = (date.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
    return first_of_next - datetime.timedelta(days=1)


def period_of(date, length):
    """(first day, last day) of the VAT period of ``length`` ``date`` is in."""
    if length == VatRegistration.Period.YEAR:
        return datetime.date(date.year, 1, 1), datetime.date(date.year, 12, 31)
    if length == VatRegistration.Period.QUARTER:
        first = datetime.date(date.year, 3 * ((date.month - 1) // 3) + 1, 1)
        return first, _month_end(first.replace(month=first.month + 2))
    return date.replace(day=1), _month_end(date)


def due_date(period_end, length):
    """When the return and the tax for a period are due (vero.fi): the 12th
    of the second month after a month or quarter, and the end of February
    after a calendar year."""
    if length == VatRegistration.Period.YEAR:
        return _month_end(datetime.date(period_end.year + 1, 2, 1))
    month = period_end.month + 2
    year = period_end.year + (month - 1) // 12
    return datetime.date(year, (month - 1) % 12 + 1, 12)


def periods(start, end):
    """The VAT periods that meet ``start``..``end`` on days the organisation
    is VAT registered, with the period length of the registration in force."""
    result = []
    day = start
    while day <= end:
        registration = VatRegistration.on(day)
        if registration is None:
            following = (
                VatRegistration.objects.filter(start__gt=day, start__lte=end)
                .order_by("start")
                .first()
            )
            if following is None:
                break
            day = following.start
            continue
        first, last = period_of(day, registration.period)
        if registration.end is not None:
            last = min(last, registration.end)
        result.append(Period(max(first, registration.start), last, registration.period))
        day = last + datetime.timedelta(days=1)
    return result


@dataclass
class Amounts:
    base: Decimal = ZERO
    vat: Decimal = ZERO


@dataclass
class Period:
    start: datetime.date
    end: datetime.date
    length: str
    sales: dict = field(default_factory=lambda: defaultdict(Amounts))
    purchases: dict = field(default_factory=lambda: defaultdict(Amounts))
    # Lines posted after the period ended that count in it: if its return
    # was filed already, it needs correcting.
    late: list = field(default_factory=list)

    @property
    def due(self):
        return due_date(self.end, self.length)

    def _rows(self, amounts):
        return sorted(amounts.items(), key=lambda item: item[0], reverse=True)

    @property
    def sales_rows(self):
        return self._rows(self.sales)

    @property
    def purchase_rows(self):
        return self._rows(self.purchases)

    @property
    def sales_vat(self):
        return sum((a.vat for a in self.sales.values()), ZERO)

    @property
    def purchase_vat(self):
        return sum((a.vat for a in self.purchases.values()), ZERO)

    @property
    def payable(self):
        """Positive: to pay; negative: to get back."""
        return self.sales_vat - self.purchase_vat

    @property
    def is_empty(self):
        return not (self.sales or self.purchases)


@dataclass
class Summary:
    start: datetime.date
    end: datetime.date
    periods: list
    # Posted lines on the VAT accounts without a VAT code (reverse charge,
    # imports and the like, entered by hand): not in the summary.
    uncoded: list = field(default_factory=list)
    # Draft vouchers with VAT in the dates, and records from invoicing with
    # no voucher yet: the summary changes once they are posted.
    drafts: list = field(default_factory=list)
    waiting: list = field(default_factory=list)
    # Advance payments received on a day the line's VAT rate was not in force.
    rate_warnings: list = field(default_factory=list)
    registered: bool = True
    # The posting settings name no VAT accounts, so VAT cannot be told
    # from the base.
    accounts_missing: bool = False

    @property
    def ready(self):
        """Whether nothing known is missing from the summary."""
        return (
            self.registered
            and not self.accounts_missing
            and not (self.uncoded or self.drafts or self.waiting)
        )


def vat_accounts(settings=None):
    settings = settings or PostingSettings.current()
    return {pk for pk in (settings.sales_vat_id, settings.purchase_vat_id) if pk}


def _split(amount, shares):
    """``amount`` in cents over (date, share) parts; the last takes the rest."""
    parts, left = [], amount
    for index, (date, share) in enumerate(shares):
        if index == len(shares) - 1:
            part = left
        else:
            part = (amount * share).quantize(CENT, ROUND_HALF_UP)
            left -= part
        parts.append((date, part))
    return parts


def invoice_dates(posting):
    """[(date, share)] the VAT of an invoice voucher counts on: payments
    received before the supply is made, then the rest at the supply date."""
    vat_date = posting.vat_date
    if posting.source != Posting.Source.INVOICE:
        return [(vat_date, Decimal(1))]
    total = posting.invoice.total
    if total <= 0:
        return [(vat_date, Decimal(1))]
    shares, paid = [], ZERO
    for payment in api.Payment.objects.filter(invoice_id=posting.invoice_id, paid_on__lt=vat_date):
        before = min(max(paid, ZERO), total)
        paid += payment.amount
        after = min(max(paid, ZERO), total)
        if after != before:
            shares.append((payment.paid_on, (after - before) / total))
    rest = Decimal(1) - sum((share for _date, share in shares), Decimal(0))
    if rest:
        shares.append((vat_date, rest))
    return shares


def summary(start, end):
    """The VAT summary for the VAT periods that meet ``start``..``end``."""
    settings = PostingSettings.current()
    found = periods(start, end)
    result = Summary(start, end, found, registered=bool(found))
    if not found:
        return result
    start, end = found[0].start, found[-1].end
    vat_ids = vat_accounts(settings)
    result.accounts_missing = settings.sales_vat_id is None
    lines = (
        VoucherLine.objects.filter(
            voucher__status=Voucher.Status.POSTED,
            voucher__date__range=(start - REACH, end + REACH),
        )
        .exclude(vat_code="")
        .select_related("voucher__year", "voucher__posting__invoice", "voucher__series")
        .select_related("voucher__reverses__posting__invoice")
    )
    dates_of = {}

    def dates(voucher):
        if voucher.pk not in dates_of:
            source = voucher.reverses if voucher.kind == Voucher.Kind.REVERSAL else voucher
            posting = getattr(source, "posting", None) if source else None
            if posting is not None and posting.source in postings.INVOICES:
                dates_of[voucher.pk] = invoice_dates(posting)
            else:
                dates_of[voucher.pk] = [((source or voucher).date, Decimal(1))]
        return dates_of[voucher.pk]

    def period(date):
        return next((p for p in found if p.start <= date <= p.end), None)

    for line in lines:
        voucher = line.voucher
        sign = 1 if line.vat_code == VatCode.PURCHASES else -1
        amount = sign * line.amount
        is_vat = line.account_id in vat_ids
        shares = dates(voucher)
        for date, part in _split(amount, shares):
            target = period(date)
            if target is None or not part:
                continue
            bucket = target.sales if line.vat_code == VatCode.SALES else target.purchases
            if is_vat:
                bucket[line.vat_rate].vat += part
            else:
                bucket[line.vat_rate].base += part
            posted = timezone.localdate(voucher.posted_at) if voucher.posted_at else None
            if posted and posted > target.end and voucher not in target.late:
                target.late.append(voucher)
            if len(shares) > 1 and date != shares[-1][0] and is_vat:
                if not countries.vat_rate_applies(line.vat_rate, date, voucher.year.country):
                    result.rate_warnings.append((voucher, line.vat_rate, date))
    result.uncoded = _uncoded(start, end, vat_ids, settings)
    result.drafts = list(
        Voucher.objects.filter(status=Voucher.Status.DRAFT, date__range=(start, end))
        .filter(lines__vat_code__gt="")
        .distinct()
        .order_by("date", "pk")
    )
    result.waiting = [record for record in postings.waiting(settings) if record.date <= end]
    return result


def _uncoded(start, end, vat_ids, settings):
    """Posted vouchers in the dates with a line on a VAT account but no VAT
    code, other than the VAT settlement (a voucher only on VAT accounts)."""
    if not vat_ids:
        return []
    own = vat_ids | ({settings.vat_settlement_id} if settings.vat_settlement_id else set())
    vouchers = (
        Voucher.objects.filter(
            status=Voucher.Status.POSTED,
            date__range=(start, end),
            lines__account_id__in=vat_ids,
            lines__vat_code="",
        )
        .distinct()
        .order_by("date", "pk")
    )
    return [v for v in vouchers if v.lines.filter(~Q(account_id__in=own)).exists()]
