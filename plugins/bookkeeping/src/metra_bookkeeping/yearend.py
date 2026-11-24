"""Locking periods and closing a financial year.

Months are locked once they are reported (a VAT return filed, say): nothing
can be posted on or before the day a year is locked until, and the lock only
moves forward. Records from invoicing dated in a locked period are booked on
the first open day instead, with a note.

Closing a year, once its books are complete:

1. the chart of accounts is kept as it reads that day, so a later rename
   never rewrites the year's books (KPL 2:10);
2. the year is locked for good;
3. the next year is opened, if it is not there yet, and gets the year's
   closing balance sheet as its opening balances (KPL 3:3), with the
   result for the year carried to the result of earlier years;
4. accruals of the year are reversed on the first day of the next one.

Year-end entries the treasurer reviews and posts before closing: the
depreciation by the plans in the asset register (KPL 5:5) and the accrual
of invoices issued after the year for supplies made in it.
"""

import datetime
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings as django_settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import formats, timezone, translation
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from apps.plugins import api

from . import countries, postings, statements
from .models import (
    ZERO,
    Account,
    BankBalance,
    ChartEntry,
    FiscalYear,
    FixedAsset,
    PostingSettings,
    Voucher,
    VoucherLine,
    VoucherSeries,
    _years_after,
)


def _short(date):
    return formats.date_format(date, "SHORT_DATE_FORMAT")


def _rules(year):
    return countries.get(year.country)


# Locking


def month_ends(year, today=None):
    """The ends of the months the year can be locked until: those after the
    current lock that have passed (or end today)."""
    today = today or timezone.localdate()
    day = year.start
    ends = []
    while day <= year.end:
        following = (day.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
        end = min(following - datetime.timedelta(days=1), year.end)
        if end <= today and (year.locked_until is None or end > year.locked_until):
            ends.append(end)
        day = following
    return ends


def lock(year, until, user=None):
    """Lock ``year`` up to and including ``until``."""
    if not year.is_open:
        raise ValidationError(_("The financial year %(year)s is closed.") % {"year": year})
    if not year.contains(until):
        raise ValidationError(_("Choose a day in the financial year."))
    if year.locked_until is not None and until <= year.locked_until:
        raise ValidationError(_("The books are already locked up to that day."))
    drafts = year.vouchers.filter(status=Voucher.Status.DRAFT, date__lte=until).count()
    if drafts:
        raise ValidationError(
            ngettext(
                "%(count)s draft voucher is dated in the period. Post or delete it first.",
                "%(count)s draft vouchers are dated in the period. Post or delete them first.",
                drafts,
            )
            % {"count": drafts}
        )
    year.locked_until = until
    year.save(update_fields=["locked_until"])
    return year


# Balances


def closing_balances(year):
    """{account: debit minus credit} of the balance sheet accounts at the
    end of ``year``, without zeros."""
    sums = statements.account_sums(year, year.start, year.end, statements.BALANCE_SHEET_KINDS)
    return {account: amount for account, amount in sums.items() if amount}


def opening_entries(year, retained_earnings):
    """[(account, debit minus credit)] for the next year's opening balances:
    the closing balances, with the result carried to ``retained_earnings``."""
    balances = closing_balances(year)
    result = statements.result(year, year.start, year.end)
    balances[retained_earnings] = balances.get(retained_earnings, ZERO) - result
    return sorted(
        ((account, amount) for account, amount in balances.items() if amount),
        key=lambda item: item[0].number,
    )


def default_retained_earnings(year):
    return Account.objects.filter(number=_rules(year).RETAINED_EARNINGS).first()


# Checks before closing


def _waiting_in(year):
    return [r for r in postings.waiting() if year.contains(r.date)]


def _reversed(vouchers):
    return vouchers.exclude(reversals__status=Voucher.Status.POSTED)


def next_opening(year):
    """The next year's posted opening balances that still stand, if any."""
    following = year.following()
    if following is None:
        return None
    return _reversed(
        following.vouchers.filter(kind=Voucher.Kind.OPENING, status=Voucher.Status.POSTED)
    ).first()


def problems(year, today=None):
    """What stops ``year`` from being closed, as sentences."""
    today = today or timezone.localdate()
    found = []
    if not year.is_open:
        return [_("The financial year %(year)s is closed.") % {"year": year}]
    previous = year.previous()
    if previous is not None and previous.is_open:
        found.append(_("Close the financial year %(year)s first.") % {"year": previous})
    if today <= year.end:
        found.append(_("The year has not ended yet."))
    drafts = year.vouchers.filter(status=Voucher.Status.DRAFT).count()
    if drafts:
        found.append(
            ngettext(
                "%(count)s draft voucher is waiting. Post or delete it.",
                "%(count)s draft vouchers are waiting. Post or delete them.",
                drafts,
            )
            % {"count": drafts}
        )
    if waiting := _waiting_in(year):
        found.append(
            ngettext(
                "%(count)s record from invoicing dated in the year is waiting to be booked.",
                "%(count)s records from invoicing dated in the year are waiting to be booked.",
                len(waiting),
            )
            % {"count": len(waiting)}
        )
    income = statements.income_statement(year, year.start, year.end, compare=False)
    balance = statements.balance_sheet(year, year.end, compare=False)
    unmapped = sorted(
        set(income.unmapped) | set(balance.unmapped), key=lambda account: account.number
    )
    if unmapped:
        found.append(
            _("These accounts fall on no line of the statements: %(accounts)s.")
            % {"accounts": ", ".join(str(account) for account in unmapped)}
        )
    elif not balance.balances:
        found.append(_("The balance sheet does not balance."))
    if opening := next_opening(year):
        found.append(
            _(
                "The next year already has opening balances (voucher %(number)s). Reverse "
                "them, so the closing can carry the balances over."
            )
            % {"number": opening.display_number}
        )
    return found


def warnings(year, today=None):
    """What does not stop the closing but should be checked first."""
    today = today or timezone.localdate()
    found = []
    planned = depreciation_plan(year)
    booked = year.vouchers.filter(kind=Voucher.Kind.DEPRECIATION, status=Voucher.Status.POSTED)
    if planned and not booked.exists():
        found.append(_("The depreciation by plan is not booked."))
    if accrual_candidates(year) and not year.vouchers.filter(kind=Voucher.Kind.ACCRUAL).exists():
        found.append(_("Invoices issued after the year for supplies in it are not accrued."))
    for row in bank_rows(year):
        if row.statement is None:
            found.append(
                _("The bank statement balance of %(account)s is not given.")
                % {"account": row.account}
            )
        elif row.difference:
            found.append(
                _("%(account)s differs from the bank statement by %(amount)s.")
                % {"account": row.account, "amount": formats.number_format(row.difference, 2)}
            )
    receivables = receivables_rows(year)
    if receivables and receivables.difference:
        found.append(
            _("The receivables account differs from the open invoices by %(amount)s.")
            % {"amount": formats.number_format(receivables.difference, 2)}
        )
    for item in asset_accounts(year):
        if item.difference:
            found.append(
                _("%(account)s differs from the asset register by %(amount)s.")
                % {"account": item.account, "amount": formats.number_format(item.difference, 2)}
            )
    if not year.notes.exists():
        found.append(_("The notes to the financial statements are not written yet."))
    if today > year.statements_due:
        found.append(
            _("The financial statements were due on %(day)s.")
            % {"day": _short(year.statements_due)}
        )
    return found


# Closing


def _next_year(year):
    following = year.following()
    if following is not None:
        return following
    start = year.end + datetime.timedelta(days=1)
    following = FiscalYear(
        start=start,
        end=_years_after(start, 1) - datetime.timedelta(days=1),
        country=year.country,
        chart=year.chart,
        staff=year.staff,
    )
    following.full_clean()
    following.save()
    return following


def _in_books_language(text, **values):
    with translation.override(django_settings.LANGUAGE_CODE):
        return (str(text) % values)[:200]


def _voucher(year, date, description, entries, user, kind=Voucher.Kind.NORMAL, series=None):
    """A draft voucher with [(account, debit minus credit, text)] lines."""
    voucher = Voucher.objects.create(
        year=year,
        series=series or VoucherSeries.default(),
        date=date,
        description=description,
        kind=kind,
        created_by=user,
    )
    VoucherLine.objects.bulk_create(
        [
            VoucherLine(
                voucher=voucher,
                account=account,
                debit=max(amount, ZERO),
                credit=max(-amount, ZERO),
                description=text[:200],
                order=order,
            )
            for order, (account, amount, text) in enumerate(entries, start=1)
        ]
    )
    return voucher


def close(year, user=None, retained_earnings=None, today=None):
    """Close ``year`` and open the next one. Returns the next year."""
    retained_earnings = retained_earnings or default_retained_earnings(year)
    if retained_earnings is None or retained_earnings.kind != Account.Kind.EQUITY:
        raise ValidationError(_("Choose the equity account the result is carried to."))
    with transaction.atomic():
        year.refresh_from_db()
        if found := problems(year, today):
            raise ValidationError(found)
        entries = opening_entries(year, retained_earnings)
        accruals = list(
            _reversed(year.vouchers.filter(kind=Voucher.Kind.ACCRUAL, status=Voucher.Status.POSTED))
        )
        ChartEntry.objects.bulk_create(
            [
                ChartEntry(
                    year=year,
                    account=account,
                    number=account.number,
                    name=account.name,
                    kind=account.kind,
                    active=account.active,
                )
                for account in Account.objects.all()
            ]
        )
        following = _next_year(year)
        year.status = FiscalYear.Status.CLOSED
        year.locked_until = year.end
        year.retained_earnings = retained_earnings
        year.closed_at = timezone.now()
        year.closed_by = user
        year.save()
        if entries:
            opening = _voucher(
                following,
                following.start,
                _in_books_language(
                    _("Opening balances from the financial year %(year)s"), year=year
                ),
                [(account, amount, "") for account, amount in entries],
                user,
                kind=Voucher.Kind.OPENING,
            )
            opening.post(user, carried=True)
        for accrual in accruals:
            accrual.reverse(
                user,
                following.start,
                _in_books_language(_("accrual of %(year)s"), year=year),
            )
    return following


# Depreciation


def depreciation_plan(year):
    """[(asset, the plan's depreciation for the year)], without zeros."""
    assets = FixedAsset.objects.exclude(method=FixedAsset.Method.NONE).select_related(
        "account", "depreciation_account"
    )
    rows = [(asset, asset.depreciation(year)) for asset in assets if asset.acquired <= year.end]
    return [(asset, amount) for asset, amount in rows if amount]


def make_depreciation(year, user=None):
    """A draft voucher for the depreciation by plan, dated the last day of
    the year: each asset's depreciation account debited, its asset account
    credited (direct depreciation). None when there is nothing to book."""
    if problem := year.lock_problem(year.end):
        raise ValidationError(problem)
    existing = year.vouchers.filter(kind=Voucher.Kind.DEPRECIATION)
    if existing.exists():
        raise ValidationError(_("The year already has a depreciation voucher."))
    plan = depreciation_plan(year)
    if not plan:
        return None
    entries = []
    for asset, amount in plan:
        entries.append((asset.depreciation_account, amount, asset.name))
        entries.append((asset.account, -amount, asset.name))
    with transaction.atomic():
        return _voucher(
            year,
            year.end,
            _in_books_language(_("Depreciation by plan %(year)s"), year=year),
            entries,
            user,
            kind=Voucher.Kind.DEPRECIATION,
        )


@dataclass
class AssetAccount:
    account: Account
    books: Decimal
    register: Decimal
    rows: list  # (asset, earlier depreciation, depreciation for the year, book value)

    @property
    def difference(self):
        return self.books - self.register


def asset_accounts(year):
    """Each account of the asset register's assets: its balance in the books
    at the end of ``year`` and the book value of its assets by plan."""
    balances = closing_balances(year)
    by_account = defaultdict(list)
    for asset in FixedAsset.objects.select_related("account").filter(acquired__lte=year.end):
        if asset.disposed and asset.disposed < year.start:
            continue
        before = asset.book_value(year.start - datetime.timedelta(days=1))
        before = asset.cost if asset.acquired >= year.start else before
        value = asset.book_value(year.end)
        this_year = asset.depreciation(year)
        by_account[asset.account].append((asset, asset.cost - before, this_year, value))
    year.apply_chart(list(by_account))
    return [
        AssetAccount(
            account,
            balances.get(account, ZERO),
            sum((row[3] for row in rows), ZERO),
            rows,
        )
        for account, rows in sorted(by_account.items(), key=lambda item: item[0].number)
    ]


# Accruals


def accrual_candidates(year):
    """Issued invoices and credit notes dated after ``year`` for supplies
    made in it: income of the year, invoiced in the next one."""
    return list(
        api.Invoice.objects.issued()
        .filter(issue_date__gt=year.end, supply_end__isnull=False, supply_end__lte=year.end)
        .exclude(total=ZERO)
        .prefetch_related("lines")
        .order_by("issue_date", "number")
    )


def make_accruals(year, user=None):
    """A draft accrual voucher dated the last day of the year: the net
    income of the invoices from accrual_candidates() on their sales accounts,
    against accrued income. Closing the year reverses it on the first day of
    the next one, where the invoices themselves are booked. VAT is left out:
    it is reported by its supply period from the invoices."""
    if problem := year.lock_problem(year.end):
        raise ValidationError(problem)
    if year.vouchers.filter(kind=Voucher.Kind.ACCRUAL).exists():
        raise ValidationError(_("The year already has an accrual voucher."))
    invoices = accrual_candidates(year)
    if not invoices:
        return None
    accrued = Account.objects.filter(number=_rules(year).ACCRUED_INCOME).first()
    settings = PostingSettings.current()
    if accrued is None or settings.sales is None:
        raise ValidationError(
            _("The accrued income account %(number)s or the sales account is missing.")
            % {"number": _rules(year).ACCRUED_INCOME}
        )
    sales = defaultdict(lambda: ZERO)
    numbers = []
    for invoice in invoices:
        numbers.append(invoice.number)
        for line in invoice.lines.all():
            sales[settings.sales_account(line.fee_line_id, line.vat_rate)] += line.net
    total = sum(sales.values(), ZERO)
    text = ", ".join(numbers)
    entries = [(accrued, total, text)] + [(account, -net, text) for account, net in sales.items()]
    with transaction.atomic():
        return _voucher(
            year,
            year.end,
            _in_books_language(_("Accrual: invoiced after %(year)s for supplies in it"), year=year),
            [entry for entry in entries if entry[1]],
            user,
            kind=Voucher.Kind.ACCRUAL,
        )


# Balance sheet specifications


@dataclass
class BankRow:
    account: Account
    books: Decimal
    statement: Decimal | None
    reference: str

    @property
    def difference(self):
        return None if self.statement is None else self.books - self.statement


def bank_accounts(year):
    """The accounts on the balance sheet's cash and bank line that are in use
    or have a balance at the end of the year."""
    line = next(
        item
        for item in _rules(year).BALANCE_SHEET.sides[0].walk()
        if item.key == _rules(year).CASH_LINE
    )
    balances = closing_balances(year)
    return [
        account
        for account in Account.objects.filter(kind=Account.Kind.ASSET)
        if line.covers(account.number) and (account in balances or account.active)
    ]


def bank_rows(year):
    given = {row.account_id: row for row in BankBalance.objects.filter(year=year)}
    balances = closing_balances(year)
    accounts = year.apply_chart(bank_accounts(year))
    return [
        BankRow(
            account,
            balances.get(account, ZERO),
            given[account.pk].balance if account.pk in given else None,
            given[account.pk].reference if account.pk in given else "",
        )
        for account in accounts
        if account in balances or account.pk in given
    ]


@dataclass
class Receivables:
    account: Account
    books: Decimal
    rows: list  # (invoice, outstanding at the end of the year)

    @property
    def total(self):
        return sum((amount for _invoice, amount in self.rows), ZERO)

    @property
    def difference(self):
        return self.books - self.total


def receivables_rows(year):
    """The invoices open at the end of ``year`` against the receivables
    account, or None while postings from invoicing are off."""
    settings = PostingSettings.current()
    if not settings.is_on:
        return None
    end = year.end
    invoices = api.Invoice.objects.issued().filter(
        kind=api.Invoice.Kind.INVOICE, issue_date__lte=end
    )
    credited = dict(
        api.Invoice.objects.issued()
        .filter(kind=api.Invoice.Kind.CREDIT_NOTE, issue_date__lte=end, credits__isnull=False)
        .values("credits")
        .annotate(total=Sum("total"))
        .values_list("credits", "total")
    )
    paid = dict(
        api.Payment.objects.filter(paid_on__lte=end)
        .values("invoice")
        .annotate(total=Sum("amount"))
        .values_list("invoice", "total")
    )
    fees = dict(
        api.PaymentReminder.objects.filter(created_at__date__lte=end)
        .values("invoice")
        .annotate(total=Sum("fee"))
        .values_list("invoice", "total")
    )
    rows = []
    for invoice in invoices.order_by("issue_date", "number"):
        amount = (
            invoice.total
            + (credited.get(invoice.pk) or ZERO)
            + (fees.get(invoice.pk) or ZERO)
            - (paid.get(invoice.pk) or ZERO)
        )
        if amount:
            rows.append((invoice, amount))
    account = settings.receivables
    year.apply_chart([account])
    return Receivables(account, closing_balances(year).get(account, ZERO), rows)
