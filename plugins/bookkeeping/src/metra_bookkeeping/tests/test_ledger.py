import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError

from metra_bookkeeping import timing
from metra_bookkeeping.models import (
    Account,
    FiscalYear,
    LockedError,
    Voucher,
    VoucherLine,
    VoucherSeries,
    months_between,
)

D = datetime.date


def test_months_between():
    assert months_between(D(2026, 1, 1), D(2026, 12, 31)) == 12
    assert months_between(D(2026, 7, 1), D(2027, 12, 31)) == 18
    assert months_between(D(2026, 7, 15), D(2027, 12, 31)) == 18
    assert months_between(D(2026, 6, 15), D(2027, 12, 31)) == 19


@pytest.mark.parametrize(
    "start, end, ok",
    [
        (D(2026, 1, 1), D(2026, 12, 31), True),
        (D(2025, 7, 1), D(2026, 12, 31), True),  # a first year of 18 months
        (D(2025, 6, 1), D(2026, 12, 31), False),  # 19 months
        (D(2026, 12, 1), D(2026, 12, 31), True),  # one month
        (D(2026, 12, 31), D(2026, 12, 1), False),
    ],
)
def test_year_length(db, start, end, ok):
    year = FiscalYear(start=start, end=end)
    if ok:
        year.full_clean()
    else:
        with pytest.raises(ValidationError):
            year.full_clean()


def test_years_follow_each_other(year):
    gap = FiscalYear(start=D(2027, 2, 1), end=D(2028, 1, 31))
    with pytest.raises(ValidationError, match="day after"):
        gap.full_clean()
    overlap = FiscalYear(start=D(2026, 6, 1), end=D(2027, 5, 31))
    with pytest.raises(ValidationError, match="overlaps"):
        overlap.full_clean()
    FiscalYear(start=D(2027, 1, 1), end=D(2027, 12, 31)).full_clean()


def test_retention_dates():
    calendar = FiscalYear(start=D(2026, 1, 1), end=D(2026, 12, 31))
    assert calendar.books_kept_until == D(2036, 12, 31)
    assert calendar.vouchers_kept_until == D(2032, 12, 31)
    # A year ending in June: vouchers count from the end of that calendar year.
    split = FiscalYear(start=D(2026, 7, 1), end=D(2027, 6, 30))
    assert split.books_kept_until == D(2037, 6, 30)
    assert split.vouchers_kept_until == D(2033, 12, 31)


def test_chart_templates_have_unique_numbers_and_kinds():
    from metra_bookkeeping import countries

    kinds = {choice for choice, _ in Account.Kind.choices}
    for chart in countries.get("fi").CHARTS.values():
        numbers = [account.number for account in chart.accounts]
        assert len(numbers) == len(set(numbers))
        assert all(account.kind in kinds for account in chart.accounts)
        assert all(set(account.names) == {"fi", "sv", "en"} for account in chart.accounts)


def test_chart_in_language(db):
    from metra_bookkeeping import countries

    Account.create_chart(countries.get("fi").CHARTS["cooperative"], "sv")
    assert Account.objects.get(number="1910").name == "Bankkonto"
    assert Account.objects.get(number="2000").name == "Andelskapital"


def test_posting_numbers_without_gaps(make_voucher, year, chart):
    first = make_voucher([("7100", "100.00", "0"), ("1910", "0", "100.00")])
    dropped = make_voucher([("7100", "5.00", "0"), ("1910", "0", "5.00")])
    second = make_voucher([("7400", "250.00", "0"), ("1910", "0", "250.00")])
    first.post()
    dropped.delete()  # a draft has no number, so this leaves no gap
    second.post()
    assert (first.number, second.number) == (1, 2)
    assert first.display_number == "1"
    assert first.posted_at is not None


def test_numbers_restart_each_year_and_series(make_voucher, chart):
    FiscalYear.objects.create(start=D(2027, 1, 1), end=D(2027, 12, 31))
    other = VoucherSeries.objects.create(code="K", name="Cash")
    a = make_voucher([("7100", "1", "0"), ("1900", "0", "1")]).post()
    b = make_voucher([("7100", "1", "0"), ("1900", "0", "1")], series=other).post()
    c = make_voucher([("7100", "1", "0"), ("1900", "0", "1")], date=D(2027, 1, 5)).post()
    assert (a.number, b.number, c.number) == (1, 1, 1)
    assert b.display_number == "K1"


def test_unbalanced_voucher_cannot_be_posted(make_voucher):
    voucher = make_voucher([("7100", "100.00", "0"), ("1910", "0", "90.00")])
    with pytest.raises(ValidationError, match="differ"):
        voucher.post()
    voucher.refresh_from_db()
    assert voucher.is_draft and voucher.number is None


def test_single_line_or_zero_voucher_cannot_be_posted(make_voucher):
    with pytest.raises(ValidationError, match="two lines"):
        make_voucher([("7100", "0", "0")]).post()


def test_date_outside_year_or_closed_year(make_voucher, year):
    voucher = make_voucher([("7100", "10", "0"), ("1910", "0", "10")])
    Voucher.objects.filter(pk=voucher.pk).update(date=D(2027, 1, 1))
    with pytest.raises(ValidationError, match="outside"):
        voucher.post()
    Voucher.objects.filter(pk=voucher.pk).update(date=D(2026, 5, 1))
    FiscalYear.objects.filter(pk=year.pk).update(status=FiscalYear.Status.CLOSED)
    with pytest.raises(ValidationError, match="closed"):
        voucher.post()


def test_inactive_account_cannot_be_posted_to(make_voucher, chart):
    voucher = make_voucher([("7100", "10", "0"), ("1910", "0", "10")])
    Account.objects.filter(number="7100").update(active=False)
    with pytest.raises(ValidationError, match="not in use"):
        voucher.post()


def test_posted_voucher_is_locked(make_voucher, chart):
    voucher = make_voucher([("7100", "10", "0"), ("1910", "0", "10")]).post()
    voucher.description = "Changed"
    with pytest.raises(LockedError):
        voucher.save()
    with pytest.raises(LockedError):
        voucher.delete()
    line = voucher.lines.first()
    line.debit = Decimal("11")
    with pytest.raises(LockedError):
        line.save()
    with pytest.raises(LockedError):
        line.delete()
    with pytest.raises(LockedError):
        VoucherLine.objects.create(voucher=voucher, account=chart["7400"], debit=1)
    with pytest.raises(LockedError, match="already posted"):
        voucher.post()


def test_line_is_one_side_only(make_voucher, chart):
    voucher = make_voucher([("7100", "10", "0"), ("1910", "0", "10")])
    for debit, credit in (("5", "5"), ("-5", "0"), ("0", "0")):
        line = VoucherLine(voucher=voucher, account=chart["7100"], debit=debit, credit=credit)
        with pytest.raises(ValidationError):
            line.full_clean()


def test_reversal(make_voucher, chart):
    original = make_voucher([("7100", "120.00", "0"), ("1910", "0", "120.00")]).post()
    reversal = original.reverse(note="Wrong account", date=D(2026, 3, 5))
    assert reversal.kind == Voucher.Kind.REVERSAL
    assert reversal.reverses == original
    assert reversal.number == 2
    assert "Wrong account" in reversal.description
    lines = {(line.account.number, line.debit, line.credit) for line in reversal.lines.all()}
    assert lines == {("7100", 0, Decimal("120.00")), ("1910", Decimal("120.00"), 0)}
    assert original.reversed_by == reversal
    assert not original.can_be_reversed()
    assert not reversal.can_be_reversed()
    with pytest.raises(ValidationError):
        original.reverse()


def test_reversal_of_closed_year_goes_to_open_year(make_voucher, year):
    original = make_voucher([("7100", "10", "0"), ("1910", "0", "10")]).post()
    FiscalYear.objects.filter(pk=year.pk).update(status=FiscalYear.Status.CLOSED)
    with pytest.raises(ValidationError, match="open financial year"):
        original.reverse(date=D(2026, 12, 1))
    later = FiscalYear.objects.create(start=D(2027, 1, 1), end=D(2027, 12, 31))
    reversal = original.reverse(date=D(2027, 1, 10))
    assert reversal.year == later


def test_account_with_entries_keeps_number_and_cannot_be_deleted(make_voucher, chart):
    make_voucher([("7100", "10", "0"), ("1910", "0", "10")]).post()
    account = chart["7100"]
    account.number = "7101"
    with pytest.raises(ValidationError, match="number and kind"):
        account.full_clean()
    account.refresh_from_db()
    account.name = "Power"
    account.full_clean()
    with pytest.raises(LockedError):
        account.delete()
    with pytest.raises(ProtectedError):
        Account.objects.filter(pk=account.pk).delete()
    chart["7900"].delete()


def test_posting_is_in_the_audit_log(make_voucher):
    from auditlog.models import LogEntry

    voucher = make_voucher([("7100", "10", "0"), ("1910", "0", "10")]).post()
    entries = LogEntry.objects.get_for_object(voucher)
    assert any(entry.changes_dict.get("status") == ["draft", "posted"] for entry in entries)


def test_timing_due_date():
    assert timing.due_date(D(2026, 1, 15)) == D(2026, 5, 31)
    assert timing.due_date(D(2026, 8, 31)) == D(2026, 12, 31)
    assert timing.due_date(D(2026, 10, 1)) == D(2027, 2, 28)


def test_late_drafts(make_voucher):
    late = make_voucher([("7100", "10", "0"), ("1910", "0", "10")], date=D(2026, 1, 15))
    make_voucher([("7100", "10", "0"), ("1910", "0", "10")], date=D(2026, 5, 1))
    assert timing.late_drafts(today=D(2026, 6, 1)) == [late]
