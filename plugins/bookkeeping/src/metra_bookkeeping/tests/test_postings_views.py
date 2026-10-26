from decimal import Decimal

from django.urls import reverse

from apps.plugins import api
from metra_bookkeeping.models import (
    Account,
    Posting,
    PostingSettings,
    SalesAccount,
    VatRegistration,
    Voucher,
    VoucherSeries,
)

URL = "metra_bookkeeping:"
SETTINGS = reverse(f"{URL}posting_settings")


def settings_data(start, **changes):
    chart = {account.number: account.pk for account in Account.objects.all()}
    data = {
        "start": start,
        "receivables": chart["1700"],
        "bank": chart["1910"],
        "sales": chart["3000"],
        "reminder_fees": chart["3100"],
        "sales_vat": chart["2935"],
        "purchase_vat": chart["1765"],
        "vat_settlement": chart["2939"],
        "invoice_series": "",
        "payment_series": "",
    }
    return data | changes


def test_settings_are_suggested_from_the_chart(treasurer, this_year, chart):
    page = treasurer.get(SETTINGS).content.decode()

    assert 'value="{}" selected'.format(chart["1700"].pk) in page
    assert "New series: L Sales invoices" in page
    assert PostingSettings.objects.count() == 0  # nothing saved by looking


def test_turning_postings_on_makes_the_series(treasurer, this_year, chart):
    response = treasurer.post(SETTINGS, settings_data(this_year.start.isoformat()))

    assert response.status_code == 302
    settings = PostingSettings.current()
    assert settings.is_on
    assert (settings.invoice_series.code, settings.payment_series.code) == ("L", "S")
    assert VoucherSeries.objects.count() == 2


def test_the_vat_accounts_must_differ(treasurer, this_year, chart):
    data = settings_data(this_year.start.isoformat(), purchase_vat=chart["2935"].pk)

    page = treasurer.post(SETTINGS, data).content.decode()

    assert "accounts of their own" in page
    assert not PostingSettings.objects.exists()


def test_postings_start_in_an_open_year(treasurer, this_year, chart):
    page = treasurer.post(SETTINGS, settings_data("1999-01-01")).content.decode()

    assert "open financial year" in page


def test_sales_accounts_per_fee_line_and_rate(treasurer, books, household):
    plan = api.FeePlan.objects.create(name="Medlemsavgift", unit_type=household)
    fee = api.FeeLine.objects.create(plan=plan, description="Avgift", unit_price=10)
    data = settings_data(books.start.isoformat())
    data |= {"invoice_series": books.invoice_series.pk, "payment_series": books.payment_series.pk}
    data |= {f"fee_{fee.pk}": Account.objects.get(number="6000").pk}
    data |= {"rate_13.50": Account.objects.get(number="3200").pk}

    treasurer.post(SETTINGS, data)

    assert SalesAccount.objects.get(fee_line=fee).account.number == "6000"
    assert SalesAccount.objects.get(vat_rate=Decimal("13.5")).account.number == "3200"
    data.pop(f"fee_{fee.pk}")
    treasurer.post(SETTINGS, data)
    assert not SalesAccount.objects.filter(fee_line=fee).exists()


def test_vat_registration_periods(treasurer, this_year):
    treasurer.post(reverse(f"{URL}vat_registration_add"), {"start": "2025-01-01"})
    registration = VatRegistration.objects.get()
    treasurer.post(
        reverse(f"{URL}vat_registration_edit", args=[registration.pk]),
        {"start": "2025-01-01", "end": "2025-12-31"},
    )
    registration.refresh_from_db()
    assert str(registration.end) == "2025-12-31"
    treasurer.post(reverse(f"{URL}vat_registration_delete", args=[registration.pk]))
    assert not VatRegistration.objects.exists()


def test_only_the_treasurer_and_admin_change_the_settings(login, this_year):
    assert login("board", "Board").get(SETTINGS).status_code == 403
    assert login("reader", "Read-only").get(SETTINGS).status_code == 403
    assert login("admin", "Admin").get(SETTINGS).status_code == 200
    board = login("board2", "Board")
    assert board.post(reverse(f"{URL}post_waiting")).status_code == 403
    assert board.post(reverse(f"{URL}vat_registration_add"), {}).status_code == 403


def test_post_what_is_waiting_from_the_overview(treasurer, books, make_invoice):
    PostingSettings.objects.update(start=None)
    invoice = make_invoice([("Grundavgift", "1", "120", "0")])
    PostingSettings.objects.update(start=books.start)

    page = treasurer.get(reverse(f"{URL}index")).content.decode()
    assert "Waiting from invoicing" in page and str(invoice) in page

    response = treasurer.post(reverse(f"{URL}post_waiting"), follow=True)
    assert "1 voucher was made" in response.content.decode()
    assert Posting.objects.get().voucher.posted_by == treasurer.user


def test_invoice_and_voucher_point_to_each_other(treasurer, books, make_invoice):
    invoice = make_invoice([("Grundavgift", "1", "120", "0")])
    voucher = Voucher.objects.get()

    page = treasurer.get(invoice.get_absolute_url()).content.decode()
    assert voucher.get_absolute_url() in page and "Voucher L1" in page

    page = treasurer.get(voucher.get_absolute_url()).content.decode()
    assert "Booked from" in page and invoice.get_absolute_url() in page


def test_the_invoice_page_hides_the_books_from_others(login, books, make_invoice, make_user):
    from django.contrib.auth.models import Permission

    invoice = make_invoice([("Grundavgift", "1", "120", "0")])
    client = login("clerk")
    client.user.user_permissions.add(Permission.objects.get(codename="view_invoice"))

    page = client.get(invoice.get_absolute_url()).content.decode()

    assert "Voucher L1" not in page


def test_a_voucher_line_with_vat(treasurer, year, chart, series):
    VatRegistration.objects.create(start=year.start)
    from metra_bookkeeping.tests.test_views import lines_data

    data = {"date": "2026-03-01", "description": "Pipes", "series": series.pk, "kind": "normal"}
    data |= lines_data(
        (chart["4000"], "100", ""), (chart["1765"], "13.50", ""), (chart["1910"], "", "113.50")
    )
    data |= {"lines-0-vat": "purchases:13.5", "lines-1-vat": "purchases:13.5"}

    treasurer.post(reverse(f"{URL}voucher_create"), data | {"post": "1"})

    voucher = Voucher.objects.get()
    assert not voucher.is_draft
    vat = [line.vat_display for line in voucher.lines.all()]
    assert vat == ["Purchases 13.5 %", "Purchases 13.5 %", ""]
    page = treasurer.get(reverse(f"{URL}voucher_create")).content.decode()
    assert "Purchases 14 %" not in page  # not in force in the open year


def test_older_books_get_the_accounts_postings_need(treasurer, this_year, chart):
    Account.objects.filter(number__in=["2935", "1765", "3100"]).delete()

    page = treasurer.get(SETTINGS).content.decode()
    assert "2935" in page and "Add them" in page

    treasurer.post(reverse(f"{URL}posting_accounts_add"))

    assert Account.objects.get(number="2935").kind == "liability"
    assert Account.objects.get(number="3100").name == "Reminder fees"
    assert "Add them" not in treasurer.get(SETTINGS).content.decode()
