import datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.plugins import api
from metra_bookkeeping.models import Budget, Voucher

D = datetime.date
URL = "metra_bookkeeping:"
REPORTS = [
    "journal",
    "ledger",
    "trial_balance",
    "income_statement",
    "balance_sheet",
    "budget",
    "vat_summary",
]


def weasyprint_or_skip():
    try:
        api.render_pdf("<p>x</p>")
    except api.PDFUnavailable:
        pytest.skip("WeasyPrint's Pango library is not installed here")


@pytest.fixture
def booked(make_voucher, year):
    make_voucher(
        [("1910", "1000.00", "0"), ("2250", "0", "1000.00")],
        date=D(2026, 1, 1),
        kind=Voucher.Kind.OPENING,
    ).post()
    make_voucher([("1910", "500.00", "0"), ("6000", "0", "500.00")], date=D(2026, 1, 20)).post()
    return year


@pytest.mark.parametrize("name", REPORTS)
def test_every_report_is_a_page_a_csv_and_a_pdf(treasurer, booked, name):
    url = reverse(URL + name)
    page = treasurer.get(url, {"year": booked.pk})
    assert page.status_code == 200
    assert b"format=pdf" in page.content

    csv = treasurer.get(url, {"year": booked.pk, "format": "csv"})
    assert csv["Content-Type"] == "text/csv; charset=utf-8"
    assert csv.content.startswith("﻿".encode())
    assert b";" in csv.content

    weasyprint_or_skip()
    pdf = treasurer.get(url, {"year": booked.pk, "format": "pdf"})
    assert pdf["Content-Type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")


def test_the_statements_show_the_decrees_words(treasurer, booked):
    page = treasurer.get(reverse(URL + "income_statement"), {"year": booked.pk, "language": "sv"})
    assert "Medelanskaffning" in page.content.decode()
    assert "Räkenskapsperiodens överskott (underskott)" in page.content.decode()

    english = treasurer.get(reverse(URL + "balance_sheet"), {"year": booked.pk, "language": "en"})
    assert "this English version is not for filing" in english.content.decode()

    csv = treasurer.get(
        reverse(URL + "balance_sheet"), {"year": booked.pk, "language": "fi", "format": "csv"}
    ).content.decode("utf-8-sig")
    assert "Rahat ja pankkisaamiset;1500,00" in csv
    assert "Tilikauden voitto (tappio);500,00" in csv


def test_the_board_reads_the_statements_and_budget_but_does_not_budget(login, booked):
    board = login("board", "Board")
    for name in ("income_statement", "balance_sheet", "budget", "vat_summary"):
        assert board.get(reverse(URL + name)).status_code == 200
    assert board.get(reverse(URL + "budget_edit", args=[booked.pk])).status_code == 403


def test_the_treasurer_enters_the_budget(treasurer, booked, chart):
    url = reverse(URL + "budget_edit", args=[booked.pk])
    page = treasurer.get(url)
    assert page.status_code == 200
    response = treasurer.post(
        url, {f"account_{chart['6000'].pk}": "800", f"account_{chart['4610'].pk}": ""}
    )
    assert response.status_code == 302
    assert Budget.objects.get(year=booked, account=chart["6000"]).amount == Decimal("800")

    report = treasurer.get(reverse(URL + "budget"), {"year": booked.pk}).content.decode()
    assert "62 %" in report or "63 %" in report  # 500 of 800

    treasurer.post(url, {f"account_{chart['6000'].pk}": ""})
    assert not Budget.objects.exists()


def test_a_year_with_vouchers_still_takes_its_staff(treasurer, booked):
    url = reverse(URL + "year_edit", args=[booked.pk])
    response = treasurer.post(url, {"staff": "2.5", "start": "2027-01-01"})
    assert response.status_code == 302
    booked.refresh_from_db()
    assert booked.staff == Decimal("2.5")
    assert booked.start == D(2026, 1, 1)  # the dates stay


def test_a_preliminary_statement_says_so_on_the_file(treasurer, booked, chart):
    """An open year, left-out accounts or an unbalanced sheet are printed on
    the CSV and PDF too, not only on the screen."""
    csv = treasurer.get(
        reverse(URL + "income_statement"), {"year": booked.pk, "language": "fi", "format": "csv"}
    ).content.decode("utf-8-sig")
    assert "KESKENERÄINEN" in csv
    assert "Tilikausi on vielä avoinna." in csv
    assert "Tämä ei ole allekirjoitettava tilinpäätös." in csv

    swedish = treasurer.get(
        reverse(URL + "balance_sheet"), {"year": booked.pk, "language": "sv", "format": "csv"}
    ).content.decode("utf-8-sig")
    assert "PRELIMINÄR" in swedish
    assert "ännu inte granskade mot förordningens svenska text" in swedish


def test_left_out_accounts_are_a_reason(make_voucher, booked):
    from metra_bookkeeping import statements
    from metra_bookkeeping.models import Account

    booked.status = booked.Status.CLOSED  # as if closed, to see the other reasons
    statement = statements.income_statement(booked, booked.start, booked.end)
    assert statement.problems == []
    odd = Account.objects.create(number="39999", name="Odd", kind="income")
    statement.unmapped = [odd]
    assert statement.problems == ["Kaikki tilit eivät sisälly laskelmaan: 39999 Odd"]
