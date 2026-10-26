import datetime
from decimal import Decimal

from metra_bookkeeping import reports
from metra_bookkeeping.models import Voucher

D = datetime.date


def test_journal_ledger_and_trial_balance_agree(make_voucher, year):
    make_voucher(
        [("1910", "1000.00", "0"), ("2250", "0", "1000.00")],
        date=D(2026, 1, 1),
        description="Opening balances",
        kind=Voucher.Kind.OPENING,
    ).post()
    make_voucher([("7100", "120.00", "0"), ("1910", "0", "120.00")], date=D(2026, 2, 3)).post()
    make_voucher([("1910", "500.00", "0"), ("3510", "0", "500.00")], date=D(2026, 1, 20)).post()
    make_voucher([("7400", "99.00", "0"), ("1910", "0", "99.00")], date=D(2026, 2, 4))  # draft

    vouchers, debit, credit = reports.journal(year, year.start, year.end)
    assert [v.date for v in vouchers] == [D(2026, 1, 1), D(2026, 1, 20), D(2026, 2, 3)]
    assert debit == credit == Decimal("1620.00")

    bank = next(a for a in reports.ledger(year, year.start, year.end) if a.account.number == "1910")
    assert bank.opening == 0
    assert [balance for _, balance in bank.entries] == [
        Decimal("1000.00"),
        Decimal("1500.00"),
        Decimal("1380.00"),
    ]
    assert bank.closing == Decimal("1380.00")

    rows, totals = reports.trial_balance(year, year.start, year.end)
    assert {row.account.number for row in rows} == {"1910", "2250", "3510", "7100"}
    assert totals["closing"] == 0
    assert totals["debit"] == totals["credit"]


def test_period_brings_balances_forward(make_voucher, year):
    make_voucher([("1910", "1000.00", "0"), ("2250", "0", "1000.00")], date=D(2026, 1, 1)).post()
    make_voucher([("7100", "100.00", "0"), ("1910", "0", "100.00")], date=D(2026, 3, 10)).post()
    accounts = reports.ledger(year, D(2026, 3, 1), D(2026, 3, 31))
    bank = next(a for a in accounts if a.account.number == "1910")
    assert bank.opening == Decimal("1000.00")
    assert bank.credit == Decimal("100.00")
    assert bank.closing == Decimal("900.00")
    # An account with a balance but no entries in the period is still listed.
    assert any(a.account.number == "2250" and not a.entries for a in accounts)
