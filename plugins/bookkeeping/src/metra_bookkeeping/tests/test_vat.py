import datetime
from decimal import Decimal

from django.utils import timezone

from metra_bookkeeping import vat
from metra_bookkeeping.models import (
    Account,
    FiscalYear,
    VatRegistration,
    Voucher,
    VoucherLine,
    VoucherSeries,
)

D = datetime.date
TODAY = timezone.localdate()
Y = TODAY.year


def period(summary, day):
    return next(p for p in summary.periods if p.start <= day <= p.end)


def hand(date, lines, rate="25.5"):
    """A draft voucher entered by hand, with (account, debit, credit, VAT code) lines."""
    voucher = Voucher.objects.create(
        year=FiscalYear.for_date(date),
        series=VoucherSeries.default(),
        date=date,
        description="Pump parts",
    )
    for order, (number, debit, credit, code) in enumerate(lines, start=1):
        VoucherLine.objects.create(
            voucher=voucher,
            account=Account.objects.get(number=number),
            debit=Decimal(debit),
            credit=Decimal(credit),
            vat_code=code,
            vat_rate=Decimal(rate) if code else None,
            order=order,
        )
    return voucher


def purchase(date, net, tax, rate="25.5"):
    """A receipt entered by hand: an expense with purchase VAT."""
    total = str(Decimal(net) + Decimal(tax))
    lines = [("4000", net, "0", "purchases"), ("1765", tax, "0", "purchases")]
    return hand(date, [*lines, ("1910", "0", total, "")], rate)


def test_periods_and_due_dates():
    assert vat.period_of(D(2026, 5, 14), "month") == (D(2026, 5, 1), D(2026, 5, 31))
    assert vat.period_of(D(2026, 5, 14), "quarter") == (D(2026, 4, 1), D(2026, 6, 30))
    assert vat.period_of(D(2026, 5, 14), "year") == (D(2026, 1, 1), D(2026, 12, 31))
    assert vat.due_date(D(2026, 5, 31), "month") == D(2026, 7, 12)
    assert vat.due_date(D(2026, 12, 31), "month") == D(2027, 2, 12)
    assert vat.due_date(D(2026, 12, 31), "quarter") == D(2027, 2, 12)
    assert vat.due_date(D(2026, 12, 31), "year") == D(2027, 2, 28)


def test_periods_follow_the_registration(db):
    VatRegistration.objects.create(start=D(2026, 3, 15), end=D(2026, 9, 30), period="quarter")
    found = vat.periods(D(2026, 1, 1), D(2026, 12, 31))
    assert [(p.start, p.end) for p in found] == [
        (D(2026, 3, 15), D(2026, 3, 31)),
        (D(2026, 4, 1), D(2026, 6, 30)),
        (D(2026, 7, 1), D(2026, 9, 30)),
    ]
    summary = vat.summary(D(2025, 1, 1), D(2025, 12, 31))
    assert not summary.registered and not summary.ready


def test_an_invoice_counts_at_the_end_of_its_supply_period(books, vat_registered, make_invoice):
    supplied = (D(Y, 1, 1), D(Y, 12, 31))
    invoice = make_invoice([("Vatten", "100", "1", "25.5")], supplied=supplied)
    summary = vat.summary(D(Y, 1, 1), D(Y, 12, 31))
    december = period(summary, D(Y, 12, 1))
    assert december.sales_rows == [
        (Decimal("25.50"), vat.Amounts(Decimal("100.00"), Decimal("25.50")))
    ]
    assert december.payable == Decimal("25.50")
    others = [p for p in summary.periods if p is not december]
    assert all(p.is_empty for p in others)
    assert invoice.issue_date == TODAY


def test_a_payment_before_the_supply_is_an_advance(books, vat_registered, make_invoice, pay):
    """Annual fees billed in advance: the VAT on what is paid before the
    supply period ends is due for the month paid (AVL 15 §)."""
    invoice = make_invoice(
        [("Grundavgift", "1", "200", "25.5")], supplied=(D(Y + 1, 1, 1), D(Y + 1, 12, 31))
    )
    assert invoice.total == Decimal("251.00")
    pay(invoice, "125.50", paid_on=TODAY)  # half

    summary = vat.summary(D(Y, 1, 1), D(Y + 1, 12, 31))
    paid_month = period(summary, TODAY)
    supply_month = period(summary, D(Y + 1, 12, 31))
    assert dict(paid_month.sales)[Decimal("25.50")] == vat.Amounts(
        Decimal("100.00"), Decimal("25.50")
    )
    assert dict(supply_month.sales)[Decimal("25.50")] == vat.Amounts(
        Decimal("100.00"), Decimal("25.50")
    )
    assert summary.rate_warnings == []


def test_hand_entries_count_on_their_date_and_reversals_where_the_original_did(
    books, vat_registered
):
    first = purchase(D(Y, 1, 10), "100.00", "25.50")
    first.post()
    january = period(vat.summary(D(Y, 1, 1), D(Y, 12, 31)), D(Y, 1, 10))
    assert january.purchase_rows == [
        (Decimal("25.50"), vat.Amounts(Decimal("100.00"), Decimal("25.50")))
    ]
    assert january.payable == Decimal("-25.50")

    first.reverse(date=D(Y, 3, 1), note="Wrong supplier")
    summary = vat.summary(D(Y, 1, 1), D(Y, 12, 31))
    january = period(summary, D(Y, 1, 10))
    assert january.purchase_vat == 0
    assert period(summary, D(Y, 3, 1)).is_empty
    # Posted after January ended: a January return filed before needs correcting.
    if TODAY > D(Y, 1, 31):
        assert {v.kind for v in january.late} == {"normal", "reversal"}


def test_entries_on_vat_accounts_without_a_code_make_it_not_ready(books, vat_registered):
    voucher = hand(D(Y, 2, 1), [("1765", "24.00", "0", ""), ("1910", "0", "24.00", "")])
    summary = vat.summary(D(Y, 1, 1), D(Y, 12, 31))
    assert summary.drafts == [] and not summary.uncoded  # no VAT code: not a VAT draft
    voucher.post()
    summary = vat.summary(D(Y, 1, 1), D(Y, 12, 31))
    assert summary.uncoded == [voucher]
    assert not summary.ready


def test_the_vat_settlement_is_not_an_uncoded_entry(books, vat_registered):
    lines = [("2935", "100.00", "0", ""), ("1765", "0", "30.00", ""), ("2939", "0", "70.00", "")]
    hand(D(Y, 2, 1), lines).post()
    summary = vat.summary(D(Y, 1, 1), D(Y, 12, 31))
    assert summary.uncoded == []


def test_drafts_with_vat_make_it_not_ready(books, vat_registered):
    purchase(D(Y, 1, 10), "100.00", "25.50")
    summary = vat.summary(D(Y, 1, 1), D(Y, 12, 31))
    assert len(summary.drafts) == 1
    assert not summary.ready
