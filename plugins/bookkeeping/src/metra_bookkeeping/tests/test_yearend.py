import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.template.loader import render_to_string
from django.urls import reverse

from metra_bookkeeping import package, postings, reports, yearend
from metra_bookkeeping.models import (
    Account,
    BankBalance,
    ChartEntry,
    FiscalYear,
    FixedAsset,
    PostingSettings,
    Voucher,
    VoucherSeries,
)

D = datetime.date
AFTER = D(2026, 2, 1)  # "today" when 2025 is closed


@pytest.fixture
def y2025(db):
    return FiscalYear.objects.create(start=D(2025, 1, 1), end=D(2025, 12, 31))


@pytest.fixture
def booked(y2025, year, make_voucher):
    """2025 with opening balances, an expense and an income: a result of 300."""
    make_voucher(
        [("1910", "1000", "0"), ("2250", "0", "1000")],
        date=D(2025, 1, 1),
        description="Opening",
        kind=Voucher.Kind.OPENING,
    ).post()
    make_voucher([("4400", "200", "0"), ("1910", "0", "200")], date=D(2025, 3, 1)).post()
    make_voucher(
        [("1910", "500", "0"), ("3000", "0", "500")], date=D(2025, 6, 1), description="Sales"
    ).post()
    y2025.refresh_from_db()
    return y2025


def _raw(sql, params=()):
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(sql, params)


# Locking


def test_a_locked_period_takes_no_postings(booked, make_voucher):
    yearend.lock(booked, D(2025, 3, 31))
    draft = make_voucher([("4400", "10", "0"), ("1910", "0", "10")], date=D(2025, 3, 15))
    with pytest.raises(ValidationError, match="locked up to"):
        draft.post()
    later = make_voucher([("4400", "10", "0"), ("1910", "0", "10")], date=D(2025, 4, 1))
    later.post()
    assert later.number


def test_the_database_refuses_posting_into_a_locked_period(booked, make_voucher):
    draft = make_voucher([("4400", "10", "0"), ("1910", "0", "10")], date=D(2025, 3, 15))
    FiscalYear.objects.filter(pk=booked.pk).update(locked_until=D(2025, 3, 31))
    with pytest.raises(IntegrityError, match="locked"):
        Voucher.objects.filter(pk=draft.pk).update(status="posted", number=99)


def test_a_lock_only_moves_forward(booked):
    yearend.lock(booked, D(2025, 6, 30))
    with pytest.raises(ValidationError):
        yearend.lock(booked, D(2025, 3, 31))
    with pytest.raises(IntegrityError, match="cannot be opened again"):
        FiscalYear.objects.filter(pk=booked.pk).update(locked_until=None)


def test_drafts_in_the_period_stop_a_lock(booked, make_voucher):
    make_voucher([("4400", "10", "0"), ("1910", "0", "10")], date=D(2025, 2, 1))
    with pytest.raises(ValidationError, match="draft"):
        yearend.lock(booked, D(2025, 3, 31))


def test_month_ends_offered_are_those_passed(booked):
    ends = yearend.month_ends(booked, today=D(2025, 4, 10))
    assert ends == [D(2025, 1, 31), D(2025, 2, 28), D(2025, 3, 31)]
    yearend.lock(booked, D(2025, 2, 28))
    booked.refresh_from_db()
    assert yearend.month_ends(booked, today=D(2025, 4, 10)) == [D(2025, 3, 31)]


def test_a_year_with_posted_vouchers_keeps_its_dates(booked):
    with pytest.raises(IntegrityError, match="keeps its dates"):
        FiscalYear.objects.filter(pk=booked.pk).update(end=D(2025, 11, 30))


# Closing


def test_closing_carries_the_balances_and_the_result(booked, year):
    following = yearend.close(booked, today=AFTER)
    assert following == year
    booked.refresh_from_db()
    assert not booked.is_open
    assert booked.locked_until == booked.end
    assert booked.retained_earnings.number == "2250"
    opening = year.vouchers.get(kind=Voucher.Kind.OPENING)
    assert opening.status == Voucher.Status.POSTED
    lines = {line.account.number: line.debit - line.credit for line in opening.lines.all()}
    # Bank 1000 - 200 + 500; earlier results 1000 + the result of 300.
    assert lines == {"1910": Decimal("1300.00"), "2250": Decimal("-1300.00")}
    assert opening.date == year.start


def test_closing_opens_the_next_year_when_there_is_none(y2025, chart, series, make_voucher):
    FiscalYear.objects.filter(start=D(2026, 1, 1)).delete()
    make_voucher(
        [("1910", "50", "0"), ("2250", "0", "50")],
        date=D(2025, 1, 1),
        kind=Voucher.Kind.OPENING,
    ).post()
    following = yearend.close(y2025, today=AFTER)
    assert (following.start, following.end) == (D(2026, 1, 1), D(2026, 12, 31))
    assert following.chart == y2025.chart


def test_what_stops_a_closing(booked, make_voucher):
    assert "The year has not ended yet." in yearend.problems(booked, today=D(2025, 12, 31))
    make_voucher([("4400", "10", "0"), ("1910", "0", "10")], date=D(2025, 9, 1))
    found = yearend.problems(booked, today=AFTER)
    assert any("draft" in problem for problem in found)
    with pytest.raises(ValidationError):
        yearend.close(booked, today=AFTER)


def test_the_years_close_in_order(booked, year):
    assert any("first" in problem for problem in yearend.problems(year, today=D(2027, 2, 1)))


def test_opening_balances_are_not_typed_when_a_previous_year_exists(booked, make_voucher):
    voucher = make_voucher(
        [("1910", "10", "0"), ("2250", "0", "10")],
        date=D(2026, 1, 1),
        kind=Voucher.Kind.OPENING,
    )
    assert any("carried over" in problem for problem in voucher.problems())


def test_typed_opening_balances_in_the_next_year_stop_the_closing(booked, year, make_voucher):
    # Typed before this rule, say: they must be reversed first.
    voucher = make_voucher(
        [("1910", "10", "0"), ("2250", "0", "10")],
        date=D(2026, 1, 1),
        kind=Voucher.Kind.OPENING,
    )
    Voucher.objects.filter(pk=voucher.pk).update(status="posted", number=1)
    assert any("Reverse" in problem for problem in yearend.problems(booked, today=AFTER))
    voucher.refresh_from_db()
    voucher.reverse(date=D(2026, 1, 2), note="carried instead")
    assert yearend.problems(booked, today=AFTER) == []


def test_a_closed_year_keeps_its_chart(booked, chart):
    yearend.close(booked, today=AFTER)
    assert ChartEntry.objects.filter(year=booked).count() == Account.objects.count()
    bank = chart["1910"]
    bank.name = "Renamed"
    bank.save()
    vouchers, *_totals = reports.journal(booked, booked.start, booked.end)
    names = {line.account.name for voucher in vouchers for line in voucher.lines.all()}
    assert "Renamed" not in names and "Bank account" in names
    ledger = {item.account.number: item.account.name for item in reports.ledger(*_whole(booked))}
    assert ledger["1910"] == "Bank account"
    following = booked.following()
    ledger = {item.account.number: item.account.name for item in reports.ledger(*_whole(following))}
    assert ledger["1910"] == "Renamed"


def _whole(year):
    return year, year.start, year.end


def test_a_closed_year_never_changes(booked, series):
    yearend.close(booked, today=AFTER)
    attempts = [
        (lambda: FiscalYear.objects.filter(pk=booked.pk).update(status="open"), "closed"),
        (
            lambda: _raw("DELETE FROM metra_bookkeeping_fiscalyear WHERE id = %s", [booked.pk]),
            "cannot be deleted",
        ),
        (
            lambda: Voucher.objects.create(
                year=booked, series=series, date=D(2025, 5, 5), description="x"
            ),
            "no new vouchers",
        ),
        (lambda: ChartEntry.objects.filter(year=booked).update(name="x"), "closed"),
    ]
    for attempt, message in attempts:
        with pytest.raises(IntegrityError, match=message), transaction.atomic():
            attempt()


def test_closing_reverses_accruals_in_the_next_year(booked, year, make_voucher):
    accrual = make_voucher(
        [("7500", "40", "0"), ("2960", "0", "40")],
        date=D(2025, 12, 31),
        description="Interest for December",
        kind=Voucher.Kind.ACCRUAL,
    )
    accrual.post()
    yearend.close(booked, today=AFTER)
    reversal = accrual.reversals.get()
    assert reversal.year == year and reversal.date == year.start
    opening = year.vouchers.get(kind=Voucher.Kind.OPENING)
    lines = {line.account.number: line.debit - line.credit for line in opening.lines.all()}
    assert lines["2960"] == Decimal("-40.00")
    assert lines["2250"] == Decimal("-1260.00")  # result 300 - 40


def test_a_carried_balance_on_an_account_out_of_use(booked, chart):
    chart["1910"].active = False
    chart["1910"].save()
    yearend.close(booked, today=AFTER)
    assert booked.following().vouchers.get(kind=Voucher.Kind.OPENING).is_draft is False


def test_corrections_of_a_closed_year(booked, year, make_voucher):
    yearend.close(booked, today=AFTER)
    correction = make_voucher(
        [("2250", "25", "0"), ("1910", "0", "25")],
        date=D(2026, 2, 3),
        description="Bank charge missed in 2025",
        corrects=booked,
    )
    correction.post()
    notes = dict(package.written_notes(year, "fi", "micro"))
    assert any(
        "Bank charge missed" in text
        for text in notes["Edellisten tilikausien virheiden korjaukset"]
    )
    open_year = make_voucher(
        [("2250", "1", "0"), ("1910", "0", "1")], date=D(2026, 2, 3), corrects=year
    )
    assert "Only a closed earlier year can be corrected." in open_year.problems()


# Year-end entries


@pytest.fixture
def network(chart, y2025):
    pipes = Account.objects.create(number="1170", name="Pipe network", kind="asset")
    chart["1170"] = pipes
    return FixedAsset.objects.create(
        name="Pipes",
        account=pipes,
        depreciation_account=chart["5800"],
        acquired=D(2025, 7, 15),
        cost=Decimal("12000"),
        method=FixedAsset.Method.STRAIGHT,
        years=10,
    )


def test_straight_line_depreciation_by_months(network, y2025, year):
    assert network.depreciation(y2025) == Decimal("600.00")  # July to December
    assert network.depreciation(year) == Decimal("1200.00")
    assert network.book_value(D(2026, 12, 31)) == Decimal("10200.00")


def test_reducing_balance_and_assets_older_than_the_books(chart, y2025):
    asset = FixedAsset.objects.create(
        name="Pump house",
        account=chart["1160"],
        depreciation_account=chart["5800"],
        acquired=D(2023, 1, 1),
        cost=Decimal("10000"),
        method=FixedAsset.Method.REDUCING,
        percent=Decimal("10"),
    )
    # 2023: 1000, 2024: 900, 2025: 810.
    assert asset.depreciation(y2025) == Decimal("810.00")
    assert asset.book_value(y2025.end) == Decimal("7290.00")


def test_land_is_not_depreciated(chart, y2025):
    land = FixedAsset(
        name="Plot", account=chart["1160"], acquired=D(2020, 1, 1), cost=Decimal("5000")
    )
    land.method = FixedAsset.Method.NONE
    land.full_clean()
    land.save()
    assert yearend.depreciation_plan(y2025) == []
    assert land.book_value(y2025.end) == Decimal("5000")


def test_the_depreciation_voucher_and_the_register_against_the_books(
    network, y2025, year, make_voucher
):
    make_voucher(
        [("1170", "12000", "0"), ("1910", "0", "12000")], date=D(2025, 7, 15), description="Pipes"
    ).post()
    voucher = yearend.make_depreciation(y2025)
    assert voucher.kind == Voucher.Kind.DEPRECIATION and voucher.is_draft
    assert voucher.date == y2025.end
    lines = {line.account.number: line.debit - line.credit for line in voucher.lines.all()}
    assert lines == {"5800": Decimal("600.00"), "1170": Decimal("-600.00")}
    with pytest.raises(ValidationError):
        yearend.make_depreciation(y2025)
    (item,) = yearend.asset_accounts(y2025)
    assert item.difference == Decimal("600.00")  # not posted yet
    voucher.post()
    (item,) = yearend.asset_accounts(y2025)
    assert item.difference == 0
    assert "The depreciation by plan is not booked." not in yearend.warnings(y2025, today=AFTER)


def test_bank_balances_against_the_books(booked):
    (row,) = yearend.bank_rows(booked)
    assert row.statement is None and row.books == Decimal("1300.00")
    BankBalance.objects.create(
        year=booked, account=row.account, balance=Decimal("1290"), reference="12/2025"
    )
    (row,) = yearend.bank_rows(booked)
    assert row.difference == Decimal("10.00")
    assert any("differs from the bank statement" in w for w in yearend.warnings(booked, AFTER))


# Postings into locked periods and closed years


@pytest.fixture
def last_year(this_year, chart):
    start = this_year.start.replace(year=this_year.start.year - 1)
    return FiscalYear.objects.create(start=start, end=this_year.start - datetime.timedelta(1))


def test_a_payment_dated_in_a_closed_year_is_booked_late(
    books, last_year, this_year, make_invoice, pay
):
    PostingSettings.objects.filter(pk=books.pk).update(start=last_year.start)
    invoice = make_invoice([("Water", "1", "100", "0")])
    FiscalYear.objects.filter(pk=last_year.pk).update(status="closed", locked_until=last_year.end)
    pay(invoice, "100", paid_on=last_year.end)
    posting = postings.Posting.objects.get(payment__isnull=False)
    assert posting.voucher.year == this_year
    assert posting.voucher.date == this_year.start
    # In the books' language (Swedish in the tests), with its own date.
    assert "bokförd i efterhand" in posting.voucher.description


def _lines(voucher):
    return {line.account.number: line.debit - line.credit for line in voucher.lines.all()}


def test_invoices_issued_after_the_year_are_accrued(books, last_year, this_year, make_invoice):
    supplied = (last_year.end.replace(month=7, day=1), last_year.end)
    make_invoice([("Water", "2", "50", "0")], supplied=supplied)
    make_invoice([("Water", "1", "10", "0")])  # this year's
    (row,) = yearend.accrual_rows(last_year)
    assert row.kind == "accrue" and row.total == Decimal("100.00")
    voucher = yearend.make_accruals(last_year)
    assert _lines(voucher) == {"1760": Decimal("100.00"), "3000": Decimal("-100.00")}
    assert voucher.kind == Voucher.Kind.INCOME_ACCRUAL
    assert yearend.make_accruals(last_year) is None


def test_a_supply_across_the_year_end_is_accrued_by_days(books, last_year, this_year, make_invoice):
    # 31 days in the closed year, 31 in this one: half belongs to last year.
    supplied = (last_year.end.replace(day=1), this_year.start.replace(day=31))
    make_invoice([("Water", "1", "100", "0")], supplied=supplied)
    (row,) = yearend.accrual_rows(last_year)
    assert (row.days, row.total_days, row.total) == (31, 62, Decimal("50.00"))


def test_income_invoiced_for_the_next_year_is_deferred(books, this_year, make_invoice):
    # Issued this year for the last month of it and the first two of the next.
    start = this_year.end.replace(day=1)
    end = this_year.end.replace(year=this_year.end.year + 1, month=2, day=28)
    make_invoice([("Water", "1", "90", "0")], supplied=(start, end))
    (row,) = yearend.accrual_rows(this_year)
    assert row.kind == "defer" and row.days == 59 and row.total_days == 90
    voucher = yearend.make_accruals(this_year)
    assert _lines(voucher) == {"3000": Decimal("59.00"), "2960": Decimal("-59.00")}


def test_an_invoice_after_the_accrual_voucher_is_warned_about_and_topped_up(
    books, last_year, this_year, make_invoice
):
    supplied = (last_year.end.replace(month=7, day=1), last_year.end)
    make_invoice([("Water", "1", "100", "0")], supplied=supplied)
    yearend.make_accruals(last_year).post()
    assert not any("accrued or deferred" in w for w in yearend.warnings(last_year))
    make_invoice([("Water", "1", "40", "0")], supplied=supplied)
    (warning,) = [w for w in yearend.warnings(last_year) if "accrued or deferred" in w]
    assert "40,00" in warning or "40.00" in warning
    top_up = yearend.make_accruals(last_year)
    assert _lines(top_up) == {"1760": Decimal("40.00"), "3000": Decimal("-40.00")}


def test_receivables_by_invoice(books, this_year, make_invoice, pay):
    first = make_invoice([("Water", "1", "100", "0")])
    make_invoice([("Water", "1", "40", "0")])
    pay(first, "60")
    receivables = yearend.receivables_rows(this_year)
    assert [amount for _invoice, amount in receivables.rows] == [Decimal("40.00")] * 2
    assert receivables.difference == 0


# The package


def test_the_package_of_a_closed_year(booked, chart):
    BankBalance.objects.create(year=booked, account=chart["1910"], balance=Decimal("1300"))
    yearend.close(booked, today=AFTER)
    context = package.build(booked, "fi")
    assert context["problems"] == []
    html = render_to_string("metra_bookkeeping/pdf/package.html", context)
    for text in (
        "Tilinpäätös",
        "Tuloslaskelma",
        "Tase",
        "Liitetiedot",
        "Tilinpäätöksen allekirjoitus",
        "Tase-erittelyt",
        "Luettelo kirjanpidoista ja aineistoista",
        "Tililuettelo",
        "Päiväkirja",
        "Pääkirja",
        "Metra",
    ):
        assert text in html, text
    assert "KESKENERÄINEN" not in html


def test_the_package_of_an_open_year_is_preliminary(booked):
    context = package.build(booked, "sv")
    html = render_to_string("metra_bookkeeping/pdf/package.html", context)
    assert "PRELIMINÄR" in html and "Bokslut" in html
    only = package.build(booked, "sv", statements_only=True)
    html = render_to_string("metra_bookkeeping/pdf/package.html", only)
    assert "Huvudbok" not in html


def test_saved_notes_and_signers(booked, treasurer):
    url = reverse("metra_bookkeeping:year_notes", args=[booked.pk])
    page = treasurer.get(f"{url}?language=fi")
    assert page.status_code == 200
    data = {name: field.initial for name, field in page.context["form"].fields.items()}
    data["note_guarantees"] = "Pantattu talletus 1 000 €."
    data["signers"] = "Anna Andersson\nBo Berg"
    response = treasurer.post(f"{url}?language=fi", data)
    assert response.status_code == 302
    booked.refresh_from_db()
    notes = dict(package.written_notes(booked, "fi", "micro"))
    assert notes["Vakuudet ja vastuusitoumukset"] == ["Pantattu talletus 1 000 €."]
    assert package.build(booked, "fi", statements_only=True)["signers"] == [
        "Anna Andersson",
        "Bo Berg",
    ]


# Pages and permissions


def test_the_year_end_pages(booked, treasurer, login):
    for name in ("year_end", "year_package", "year_bank", "year_notes"):
        response = treasurer.get(reverse(f"metra_bookkeeping:{name}", args=[booked.pk]))
        assert response.status_code == 200, name
    assert treasurer.get(reverse("metra_bookkeeping:asset_list")).status_code == 200
    board = login("board", "Board")
    assert board.get(reverse("metra_bookkeeping:year_package", args=[booked.pk])).status_code == 200
    url = reverse("metra_bookkeeping:year_end", args=[booked.pk])
    assert board.post(url, {"confirm": "on"}).status_code == 403
    lock = reverse("metra_bookkeeping:year_lock", args=[booked.pk])
    assert board.post(lock, {"until": "2025-01-31"}).status_code == 403


def test_closing_from_the_page(booked, treasurer, chart):
    url = reverse("metra_bookkeeping:year_end", args=[booked.pk])
    response = treasurer.post(url, {"retained_earnings": chart["2250"].pk})
    assert response.status_code == 200  # the confirmation is required
    response = treasurer.post(url, {"retained_earnings": chart["2250"].pk, "confirm": "on"})
    assert response.status_code == 302
    booked.refresh_from_db()
    assert not booked.is_open and booked.closed_by == treasurer.user


def test_locking_from_the_page(booked, treasurer):
    url = reverse("metra_bookkeeping:year_lock", args=[booked.pk])
    response = treasurer.post(url, {"until": "2025-03-31"})
    assert response.status_code == 302
    booked.refresh_from_db()
    assert booked.locked_until == D(2025, 3, 31)


def test_the_package_pdf(booked, treasurer):
    url = reverse("metra_bookkeeping:year_package", args=[booked.pk])
    response = treasurer.get(f"{url}?format=pdf&language=fi")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"


def test_a_voucher_dated_in_a_locked_period_is_refused_on_the_form(booked, treasurer, chart):
    yearend.lock(booked, D(2025, 3, 31))
    response = treasurer.post(
        reverse("metra_bookkeeping:voucher_create"),
        {
            "date": "2025-03-10",
            "description": "Late",
            "series": VoucherSeries.default().pk,
            "kind": "normal",
            "lines-TOTAL_FORMS": "0",
            "lines-INITIAL_FORMS": "0",
        },
    )
    assert "locked up to" in response.content.decode()
