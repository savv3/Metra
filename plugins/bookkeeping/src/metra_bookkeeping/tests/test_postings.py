import datetime
from decimal import Decimal

import pytest
from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.plugins import api
from metra_bookkeeping import postings
from metra_bookkeeping.models import (
    Account,
    FiscalYear,
    Posting,
    PostingSettings,
    SalesAccount,
    VatRegistration,
    Voucher,
    VoucherLine,
    VoucherSeries,
)

D = datetime.date
TODAY = timezone.localdate()


def entries(voucher):
    """{account number: (debit, credit, VAT)} of a voucher."""
    return {
        line.account.number: (line.debit, line.credit, line.vat_display)
        for line in voucher.lines.select_related("account")
    }


def balance(number):
    lines = VoucherLine.objects.filter(
        account__number=number, voucher__status=Voucher.Status.POSTED
    )
    return sum((line.debit - line.credit for line in lines), Decimal("0.00"))


def voucher_of(invoice, source="invoice"):
    return Posting.objects.get(invoice=invoice, source=source).voucher


def test_an_invoice_without_vat_is_booked_and_posted(books, make_invoice):
    invoice = make_invoice([("Grundavgift", "1", "120", "25.5"), ("Vatten", "40", "1.5", "25.5")])

    voucher = voucher_of(invoice)
    assert voucher.status == Voucher.Status.POSTED
    assert voucher.display_number == "L1"
    assert voucher.date == invoice.issue_date
    assert entries(voucher) == {
        "1700": (Decimal("180.00"), 0, ""),
        "3000": (0, Decimal("180.00"), ""),
    }
    assert voucher.warnings() == []  # the invoice is the evidence; no receipt asked for
    # In the organisation's language (Swedish here), whoever issued it.
    assert voucher.description == f"Faktura {invoice.number}, Byvägen 4"


def test_vat_goes_to_its_own_account_with_the_rate_on_each_line(
    books, vat_registered, make_invoice
):
    invoice = make_invoice([("Vatten", "100", "1.10", "25.5"), ("Bok", "1", "20", "13.5")])

    voucher = voucher_of(invoice)
    assert invoice.total == Decimal("130.00") + Decimal("28.05") + Decimal("2.70")
    lines = {
        (line.account.number, line.vat_rate): (line.debit, line.credit, line.vat_code)
        for line in voucher.lines.select_related("account")
    }
    assert lines == {
        ("1700", None): (invoice.total, 0, ""),
        ("3000", Decimal("25.50")): (0, Decimal("110.00"), "sales"),
        ("3000", Decimal("13.50")): (0, Decimal("20.00"), "sales"),
        ("2935", Decimal("25.50")): (0, Decimal("28.05"), "sales"),
        ("2935", Decimal("13.50")): (0, Decimal("2.70"), "sales"),
    }
    assert voucher.status == Voucher.Status.POSTED
    assert voucher.warnings() == []


def test_sales_accounts_per_fee_line_then_rate(books, vat_registered, make_invoice, household):
    plan = api.FeePlan.objects.create(name="Medlemsavgift", unit_type=household)
    fee = api.FeeLine.objects.create(plan=plan, description="Medlemsavgift", unit_price=10)
    chart = {account.number: account for account in Account.objects.all()}
    SalesAccount.objects.create(fee_line=fee, account=chart["6000"])
    SalesAccount.objects.create(vat_rate=Decimal("13.5"), account=chart["3200"])

    invoice = make_invoice(
        [
            ("Medlemsavgift", "1", "10", "0"),
            ("Bok", "1", "20", "13.5"),
            ("Vatten", "1", "5", "25.5"),
        ],
        fee_line=fee,
    )

    numbers = {number for number in entries(voucher_of(invoice))}
    assert numbers == {"1700", "6000", "3200", "3000", "2935"}


def test_receivables_equal_what_is_outstanding(
    books, make_invoice, pay, remind, django_capture_on_commit_callbacks
):
    first = make_invoice([("Grundavgift", "1", "120", "0")])
    second = make_invoice([("Grundavgift", "1", "80", "0")])
    note = first.make_credit_note()
    api.InvoiceLine.objects.filter(invoice=note).update(quantity=Decimal("-0.5"))
    with django_capture_on_commit_callbacks(execute=True):
        note.issue()
    remind(second, "5")
    pay(first, "60")
    pay(second, "50")
    pay(second, "-10")  # undoing a payment recorded by mistake

    outstanding = sum(invoice.outstanding() for invoice in api.Invoice.objects.all())
    assert outstanding == Decimal("45.00")  # 120 - 60 - 60, and 80 + 5 - 50 + 10
    assert balance("1700") == outstanding
    assert balance("1910") == Decimal("100.00")
    assert balance("3100") == Decimal("-5.00")
    credit = voucher_of(note, "credit_note")
    assert entries(credit) == {"1700": (0, Decimal("60.00"), ""), "3000": (Decimal("60.00"), 0, "")}
    assert credit.description.startswith(f"Kreditnota {note.number} för faktura {first.number}")
    undo = Posting.objects.get(payment__amount=Decimal("-10")).voucher
    assert entries(undo) == {"1910": (0, Decimal("10.00"), ""), "1700": (Decimal("10.00"), 0, "")}
    assert undo.series == books.payment_series
    assert Posting.objects.get(source="reminder").voucher.series == books.invoice_series


def test_nothing_is_booked_until_postings_are_on(this_year, chart, make_invoice):
    invoice = make_invoice([("Grundavgift", "1", "120", "0")])

    assert not Posting.objects.exists()
    assert postings.waiting() == []
    assert Posting.objects.filter(invoice=invoice).count() == 0


def test_records_before_the_start_are_left_to_the_opening_balances(books, make_invoice, pay):
    books.start = TODAY + datetime.timedelta(days=1)
    books.save()

    invoice = make_invoice([("Grundavgift", "1", "120", "0")])
    pay(invoice, "120")

    assert not Posting.objects.exists()
    assert postings.waiting() == []


def test_records_missed_wait_and_are_booked_once(books, make_invoice, pay):
    PostingSettings.objects.update(start=None)  # postings off while invoicing goes on
    invoice = make_invoice([("Grundavgift", "1", "120", "0")])
    pay(invoice, "100")
    PostingSettings.objects.update(start=books.start)

    assert [record.source for record in postings.waiting()] == ["invoice", "payment"]
    made, left = postings.book_waiting()
    assert len(made) == 2 and left == 0
    assert postings.book_waiting() == ([], 0)
    assert Posting.objects.count() == 2
    assert balance("1700") == Decimal("20.00")


def test_a_voucher_that_cannot_be_posted_stays_a_draft(books, make_invoice):
    Account.objects.filter(number="3000").update(active=False)

    invoice = make_invoice([("Grundavgift", "1", "120", "0")])

    voucher = voucher_of(invoice)
    assert voucher.is_draft
    assert "not in use" in voucher.problems()[0]
    assert postings.waiting() == []  # it has its draft voucher
    voucher.delete()  # deleting the draft puts the invoice back in the queue
    assert [record.invoice for record in postings.waiting()] == [invoice]


def test_no_open_year_leaves_the_record_waiting(books, make_invoice):
    FiscalYear.objects.update(status=FiscalYear.Status.CLOSED)

    make_invoice([("Grundavgift", "1", "120", "0")])

    assert not Voucher.objects.exists()
    assert len(postings.waiting()) == 1


def test_vat_rates_are_dated(year, chart, make_voucher):
    VatRegistration.objects.create(start=D(2025, 1, 1))

    def voucher(rate, date):
        made = make_voucher([("4000", "100", "0"), ("1765", "14", "0"), ("1910", "0", "114")], date)
        made.lines.exclude(account__number="1910").update(vat_code="purchases", vat_rate=rate)
        return made

    old_rate = voucher(Decimal("14"), D(2026, 3, 1))
    assert "14 % is not in force" in " ".join(old_rate.problems())
    new_rate = voucher(Decimal("13.5"), D(2026, 3, 1))
    assert new_rate.problems() == []
    new_rate.post()


def test_vat_only_while_registered(year, chart, make_voucher):
    VatRegistration.objects.create(start=D(2026, 6, 1))
    made = make_voucher([("4000", "100", "0"), ("1765", "25.5", "0"), ("1910", "0", "125.5")])
    made.lines.exclude(account__number="1910").update(vat_code="purchases", vat_rate="25.5")

    assert "not VAT registered" in " ".join(made.problems())


def test_vat_registrations_do_not_overlap(db):
    from django.core.exceptions import ValidationError

    VatRegistration.objects.create(start=D(2025, 1, 1), end=D(2025, 12, 31))
    VatRegistration(start=D(2026, 1, 1)).full_clean()
    with pytest.raises(ValidationError, match="overlaps"):
        VatRegistration(start=D(2025, 6, 1)).full_clean()
    assert VatRegistration.covers(D(2025, 12, 31))
    assert not VatRegistration.covers(D(2026, 1, 1))


def test_an_invoice_at_a_rate_no_longer_in_force_is_booked_with_a_warning(
    books, vat_registered, make_invoice
):
    invoice = make_invoice([("Bok", "1", "100", "14")])

    voucher = voucher_of(invoice)
    assert voucher.status == Voucher.Status.POSTED  # booked as invoiced
    if TODAY >= D(2026, 1, 1):
        assert "not in force" in " ".join(voucher.warnings())


def test_vat_follows_the_supply_period_not_the_invoice_date(books, vat_registered, make_invoice):
    """Water for 2025 invoiced now: the 14 % rate of 2025 is right, and the
    VAT belongs to December 2025 (AVL 15 §), whatever the invoice date."""
    invoice = make_invoice(
        [("Vatten 2025", "1", "100", "14")], supplied=(D(2025, 1, 1), D(2025, 12, 31))
    )

    voucher = voucher_of(invoice)
    assert voucher.date == invoice.issue_date  # booked on the invoice date
    posting = voucher.posting
    assert (posting.supply_start, posting.supply_end) == (D(2025, 1, 1), D(2025, 12, 31))
    assert posting.vat_date == D(2025, 12, 31)
    assert voucher.warnings() == []
    this_year = make_invoice([("Vatten 2026", "1", "100", "14")], supplied=(None, D(2026, 6, 30)))
    assert "not in force" in " ".join(voucher_of(this_year).warnings())


def test_without_a_supply_period_the_invoice_date_counts(books, make_invoice):
    invoice = make_invoice([("Grundavgift", "1", "120", "0")])

    posting = voucher_of(invoice).posting
    assert posting.supply_start == posting.supply_end == invoice.issue_date


def test_an_invoice_without_vat_while_registered_is_pointed_out(books, seller, make_invoice):
    VatRegistration.objects.create(start=D(2020, 1, 1))

    invoice = make_invoice([("Grundavgift", "1", "120", "25.5")])

    assert "issued without VAT" in " ".join(voucher_of(invoice).warnings())


def test_a_reversal_keeps_the_vat(books, vat_registered, make_invoice):
    voucher = voucher_of(make_invoice([("Vatten", "1", "100", "25.5")]))

    reversal = voucher.reverse(note="Wrong account")

    rates = sorted(str(line.vat_rate) for line in reversal.lines.all() if line.vat_rate)
    assert rates == ["25.50", "25.50"]
    assert reversal.status == Voucher.Status.POSTED


def test_database_keeps_what_posted_entries_depend_on(books, make_invoice):
    voucher = voucher_of(make_invoice([("Grundavgift", "1", "120", "0")]))
    posting = voucher.posting
    attempts = [
        lambda: Account.objects.filter(number="3000").update(number="3001"),
        lambda: Account.objects.filter(number="1700").update(kind="expense"),
        lambda: Account.objects.filter(number="1700").delete(),
        lambda: VoucherSeries.objects.filter(code="L").update(code="X"),
        lambda: Posting.objects.filter(pk=posting.pk).update(source="payment"),
        lambda: Posting.objects.filter(pk=posting.pk).delete(),
        lambda: VoucherLine.objects.filter(voucher=voucher).update(vat_rate=1, vat_code="sales"),
        lambda: Posting.objects.filter(pk=posting.pk).update(supply_end=D(2020, 1, 1)),
    ]
    for attempt in attempts:
        with pytest.raises(DatabaseError), transaction.atomic():
            attempt()
    # Names can change, and unused accounts and series anything.
    Account.objects.filter(number="1700").update(name="Kundfordringar")
    Account.objects.filter(number="4000").update(number="4001")
    VoucherSeries.objects.filter(code="S").update(code="B")
