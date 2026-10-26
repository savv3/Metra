"""The books as the Accounting Act asks for them: entries in date order
(the journal, päiväkirja) and in account order (the general ledger,
pääkirja), plus a trial balance. Only posted vouchers count."""

from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Q, Sum

from .models import Account, Voucher, VoucherLine

ZERO = Decimal("0.00")


def posted_lines(year):
    return VoucherLine.objects.filter(voucher__year=year, voucher__status=Voucher.Status.POSTED)


def journal(year, start, end):
    """Posted vouchers from ``start`` to ``end``, by date and number, with
    their lines; and the totals of debits and credits."""
    vouchers = (
        Voucher.objects.filter(year=year, status=Voucher.Status.POSTED, date__range=(start, end))
        .select_related("series", "reverses__series")
        .prefetch_related("lines__account")
        .order_by("date", "series__code", "number")
    )
    totals = (
        posted_lines(year)
        .filter(voucher__date__range=(start, end))
        .aggregate(debit=Sum("debit"), credit=Sum("credit"))
    )
    return vouchers, totals["debit"] or ZERO, totals["credit"] or ZERO


@dataclass
class LedgerAccount:
    account: Account
    opening: Decimal = ZERO
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    entries: list = field(default_factory=list)

    @property
    def closing(self):
        return self.opening + self.debit - self.credit


def _balances_before(year, start):
    rows = (
        posted_lines(year)
        .filter(voucher__date__lt=start)
        .values("account")
        .annotate(debit=Sum("debit"), credit=Sum("credit"))
    )
    return {row["account"]: (row["debit"] or ZERO) - (row["credit"] or ZERO) for row in rows}


def ledger(year, start, end, account=None):
    """Each account with a balance or entries in the period: the balance at
    ``start`` (from the year's earlier entries, including the opening
    balances), the entries with a running balance, and the balance at
    ``end``. Balances are debit minus credit."""
    before = _balances_before(year, start)
    lines = (
        posted_lines(year)
        .filter(voucher__date__range=(start, end))
        .select_related("voucher__series", "account")
        .order_by("account__number", "voucher__date", "voucher__series__code", "voucher__number")
    )
    accounts = Account.objects.filter(Q(pk__in=before) | Q(lines__in=lines)).distinct()
    if account is not None:
        accounts = accounts.filter(pk=account.pk)
        lines = lines.filter(account=account)
    result = {a.pk: LedgerAccount(a, opening=before.get(a.pk, ZERO)) for a in accounts}
    if account is not None and account.pk not in result:
        result[account.pk] = LedgerAccount(account)
    for line in lines:
        item = result[line.account_id]
        item.debit += line.debit
        item.credit += line.credit
        item.entries.append((line, item.closing))
    return sorted(result.values(), key=lambda item: item.account.number)


def trial_balance(year, start, end):
    """Every account with a balance: at ``start``, the period's debits and
    credits, and at ``end``; plus the column totals. The balances at the
    end add up to zero when the books balance."""
    rows = ledger(year, start, end)
    totals = {
        "opening": sum((row.opening for row in rows), ZERO),
        "debit": sum((row.debit for row in rows), ZERO),
        "credit": sum((row.credit for row in rows), ZERO),
        "closing": sum((row.closing for row in rows), ZERO),
    }
    return rows, totals
