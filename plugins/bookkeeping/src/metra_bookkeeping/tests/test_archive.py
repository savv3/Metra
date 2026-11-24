import datetime
import io
import zipfile
from decimal import Decimal

import pytest
from auditlog.models import LogEntry
from django.core.files.base import ContentFile
from django.urls import reverse

from apps.plugins import api
from metra_bookkeeping import archive, countries
from metra_bookkeeping.models import FiscalYear, Posting, Receipt, Voucher

D = datetime.date


@pytest.fixture
def year_books(year, make_voucher, seller):
    """2026 with opening balances, two posted vouchers (one with a receipt)
    and a draft."""
    make_voucher(
        [("1910", "1000", "0"), ("2050", "0", "1000")],
        date=year.start,
        description="Opening balances",
        kind=Voucher.Kind.OPENING,
    ).post()
    paid = make_voucher(
        [("4400", "200", "0"), ("1910", "0", "200")],
        date=D(2026, 3, 1),
        description='Snow ploughing "Ab Plog", Västerby',
    )
    receipt = Receipt(voucher=paid, name="plog kvitto.pdf", size=4, content_type="application/pdf")
    receipt.file.save("plog.pdf", ContentFile(b"%PDF"), save=True)
    paid.post()
    make_voucher([("1910", "50", "0"), ("3000", "0", "50")], date=D(2026, 5, 2)).post()
    make_voucher([("4400", "9", "0"), ("1910", "0", "9")], description="Draft").save()
    return year


def sie_lines(year):
    return archive.sie4(year, today=D(2027, 1, 15)).decode("cp437").splitlines()


def test_sie4_has_the_chart_balances_and_vouchers(year_books):
    lines = sie_lines(year_books)
    assert lines[:4] == ["#FLAGGA 0", "#FORMAT PC8", "#SIETYP 4", lines[3]]
    assert lines[3].startswith('#PROGRAM "Metra"')
    assert "#GEN 20270115" in lines
    assert '#FNAMN "Västerby vattenandelslag"' in lines
    assert '#ORGNR "1234567-8"' in lines
    assert "#RAR 0 20260101 20261231" in lines
    assert "#VALUTA EUR" in lines
    assert '#KONTO 1910 "Bank account"' in lines
    assert "#KTYP 1910 T" in lines and "#KTYP 2050 S" in lines
    assert "#KTYP 3000 I" in lines and "#KTYP 4400 K" in lines
    # The opening voucher is the opening balances, not a voucher.
    assert "#IB 0 1910 1000.00" in lines and "#IB 0 2050 -1000.00" in lines
    assert "#UB 0 1910 850.00" in lines and "#UB 0 2050 -1000.00" in lines
    assert "#RES 0 4400 200.00" in lines and "#RES 0 3000 -50.00" in lines
    vouchers = [line for line in lines if line.startswith("#VER")]
    assert len(vouchers) == 2  # the draft is not in the books
    assert vouchers[0].startswith('#VER "" 2 20260301 "Snow ploughing \\"Ab Plog\\", Västerby"')
    start = lines.index(vouchers[0])
    assert lines[start + 1 : start + 5] == [
        "{",
        "   #TRANS 4400 {} 200.00",
        "   #TRANS 1910 {} -200.00",
        "}",
    ]


def test_sie4_balances_add_up(year_books):
    total = Decimal(0)
    for line in sie_lines(year_books):
        if line.startswith(("#UB 0", "#RES 0")):
            total += Decimal(line.split()[-1])
    assert total == 0


def test_sie4_encodes_what_pc8_cannot_hold(year_books):
    Voucher.objects.filter(description="Draft").update(description="Kaffe 5 €")
    voucher = Voucher.objects.get(description="Kaffe 5 €")
    voucher.post()
    assert any('"Kaffe 5 ?"' in line for line in sie_lines(year_books))


def test_a_reversed_opening_voucher_stays_a_voucher(year, make_voucher, seller):
    opening = make_voucher(
        [("1910", "1000", "0"), ("2050", "0", "1000")], date=year.start, kind=Voucher.Kind.OPENING
    )
    opening.post()
    opening.reverse(date=D(2026, 1, 2), note="Wrong amount")
    lines = sie_lines(year)
    assert not [line for line in lines if line.startswith("#IB")]
    assert len([line for line in lines if line.startswith("#VER")]) == 2
    assert "#UB 0 1910 0.00" in lines


def read_zip(year):
    output = archive.year_zip(year, today=D(2027, 1, 15))
    return zipfile.ZipFile(io.BytesIO(output.read()))


def rows(data):
    text = data.decode("utf-8-sig")
    return [line.split(";") for line in text.strip().splitlines()]


def test_the_zip_holds_csv_receipts_sie_and_a_readme(year_books, settings):
    settings.LANGUAGE_CODE = "en"
    files = read_zip(year_books)
    receipt = Receipt.objects.get()
    voucher = receipt.voucher
    receipt_path = f"receipts/{voucher.display_number}/{receipt.pk}-plog_kvitto.pdf"
    assert sorted(files.namelist()) == sorted(
        ["README.txt", "accounts.csv", "vouchers.csv", "books.se", receipt_path]
    )
    assert files.read(receipt_path) == b"%PDF"
    assert files.read("books.se") == archive.sie4(year_books, today=D(2027, 1, 15))

    lines = rows(files.read("vouchers.csv"))
    assert lines[0][:4] == ["Voucher", "Series", "Number", "Date"]
    assert len(lines) == 1 + 6  # three posted vouchers of two lines; no draft
    ploughing = [line for line in lines if line[3] == "2026-03-01"]
    assert ploughing[0][10:15] == ["4400", "Purchased services", "", "200,00", ""]
    assert ploughing[0][-1] == receipt_path

    accounts = {line[0]: line for line in rows(files.read("accounts.csv"))[1:]}
    assert accounts["1910"][3:] == ["1000,00", "50,00", "200,00", "850,00"]
    assert accounts["4400"][3:] == ["0,00", "200,00", "0,00", "200,00"]

    readme = files.read("README.txt").decode()
    assert "2026-01-01 to 2026-12-31" in readme
    assert "still open" in readme
    assert "until at least 2036-12-31" in readme and "until at least 2032-12-31" in readme


def test_the_zip_says_when_a_receipt_file_is_missing(year_books):
    receipt = Receipt.objects.get()
    receipt.file.storage.delete(receipt.file.name)
    names = read_zip(year_books).namelist()
    assert any(name.endswith(".missing.txt") for name in names)


def test_a_closed_year_exports_its_chart_as_closed(year_books, chart):
    from metra_bookkeeping.models import ChartEntry

    for account in chart.values():
        ChartEntry.objects.create(
            year=year_books,
            account=account,
            number=account.number,
            name=account.name,
            kind=account.kind,
        )
    year_books.status = FiscalYear.Status.CLOSED
    year_books.save()
    chart["1910"].name = "Renamed later"
    chart["1910"].save()
    lines = sie_lines(year_books)
    assert '#KONTO 1910 "Bank account"' in lines


# Pages


def test_export_page_and_downloads(year_books, treasurer):
    url = reverse("metra_bookkeeping:year_export", args=[year_books.pk])
    page = treasurer.get(url)
    assert page.status_code == 200
    assert b"Download the ZIP" in page.content

    response = treasurer.get(url, {"format": "zip"})
    assert response.status_code == 200
    assert response["Content-Type"] == "application/zip"
    assert "attachment" in response["Content-Disposition"]
    assert zipfile.ZipFile(io.BytesIO(b"".join(response.streaming_content))).testzip() is None

    response = treasurer.get(url, {"format": "sie"})
    assert response.content.startswith(b"#FLAGGA 0")
    assert '.se"' in response["Content-Disposition"]

    exports = LogEntry.objects.filter(action=LogEntry.Action.ACCESS, object_pk=str(year_books.pk))
    assert sorted(entry.additional_data["export"] for entry in exports) == ["sie4", "zip"]


def test_the_auditor_can_export_and_others_cannot(year_books, login):
    url = reverse("metra_bookkeeping:year_export", args=[year_books.pk])
    assert login("auditor", "Read-only").get(url, {"format": "zip"}).status_code == 200
    assert login("nobody").get(url, {"format": "zip"}).status_code == 403


# Retention


def test_retention_counts_from_the_right_days():
    rules = countries.get("fi").RETENTION
    # A financial year ending in June: books 10 years from its end,
    # vouchers 6 years from the end of that calendar year (KPL 2:10).
    year = FiscalYear(start=D(2026, 7, 1), end=D(2027, 6, 30))
    assert year.books_kept_until == D(2037, 6, 30) == rules.books_until(year.end)
    assert year.vouchers_kept_until == D(2033, 12, 31)


def test_retention_page(db, treasurer, year_books):
    FiscalYear.objects.create(start=D(2010, 1, 1), end=D(2010, 12, 31))
    FiscalYear.objects.create(start=D(2018, 1, 1), end=D(2018, 12, 31))
    page = treasurer.get(reverse("metra_bookkeeping:retention"))
    assert page.status_code == 200
    states = [row["state"] for row in page.context["rows"]]
    assert states == ["passed", "vouchers_passed", "keep"]
    assert page.context["rows"][-1]["receipts"] == 1
    assert b"Nothing is removed automatically" in page.content


def test_retention_page_needs_the_permission(db, login):
    assert login("nobody").get(reverse("metra_bookkeeping:retention")).status_code == 403


# Erasure


def test_changing_or_archiving_the_person_leaves_the_books_as_booked(
    books, make_invoice, unit, person, settings
):
    invoice = make_invoice([("Grundavgift", "1", "120", "0")])
    voucher = Posting.objects.get(invoice=invoice).voucher
    booked = voucher.description
    exported = archive.sie4(voucher.year)

    person.first_name, person.last_name, person.street_address = "X", "Y", ""
    person.save()
    unit.name = "Erased"
    unit.save()
    person.archive()

    voucher.refresh_from_db()
    assert voucher.description == booked
    assert archive.sie4(voucher.year).split(b"#VER")[1:] == exported.split(b"#VER")[1:]
    invoice.refresh_from_db()
    assert invoice.buyer["unit"] == "Byvägen 4"
    assert api.Invoice.objects.filter(pk=invoice.pk).exists()


def test_receipt_names_cannot_leave_their_folder(year_books, make_voucher):
    voucher = make_voucher([("4400", "5", "0"), ("1910", "0", "5")], date=D(2026, 6, 1))
    for name in ("../../etc/passwd", ".."):
        receipt = Receipt(voucher=voucher, name=name, size=1, content_type="text/plain")
        receipt.file.save("x.txt", ContentFile(b"x"), save=True)
    voucher.post()
    names = read_zip(year_books).namelist()
    receipts = [name for name in names if name.startswith("receipts/")]
    assert len(receipts) == 3
    assert all(name.count("/") == 2 and ".." not in name.split("/") for name in receipts)
