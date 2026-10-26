import datetime
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from metra_bookkeeping.models import Account, FiscalYear, Receipt, Voucher

D = datetime.date
URL = "metra_bookkeeping:"


@pytest.fixture(autouse=True)
def media_in_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"


def lines_data(*lines, extra=3):
    data = {
        "lines-TOTAL_FORMS": str(len(lines) + extra),
        "lines-INITIAL_FORMS": "0",
        "lines-MIN_NUM_FORMS": "0",
        "lines-MAX_NUM_FORMS": "1000",
    }
    for i, (account, debit, credit) in enumerate(lines):
        data |= {
            f"lines-{i}-account": account.pk,
            f"lines-{i}-debit": debit,
            f"lines-{i}-credit": credit,
            f"lines-{i}-description": "",
        }
    return data


def test_start_the_books(treasurer):
    page = treasurer.get(reverse(f"{URL}index"))
    assert b"Start the books" in page.content
    response = treasurer.post(
        reverse(f"{URL}setup"),
        {"start": "2026-01-01", "end": "2026-12-31", "chart": "cooperative"},
    )
    assert response.status_code == 302
    assert FiscalYear.objects.count() == 1
    assert Account.objects.get(number="2000").name == "Share capital"
    page = treasurer.get(reverse(f"{URL}index"))
    assert b"New voucher" in page.content


def test_enter_and_post_a_voucher(treasurer, year, chart, series):
    data = {"date": "2026-03-01", "description": "Electricity, March", "series": series.pk}
    data |= {"kind": "normal"}
    data |= lines_data((chart["7100"], "84.50", ""), (chart["1910"], "", "84.50"))
    response = treasurer.post(reverse(f"{URL}voucher_create"), data | {"post": "1"})
    voucher = Voucher.objects.get()
    assert response.status_code == 302
    assert voucher.number == 1 and not voucher.is_draft
    assert voucher.posted_by == treasurer.user
    assert voucher.total == Decimal("84.50")
    page = treasurer.get(voucher.get_absolute_url())
    assert b"Voucher 1" in page.content and b"84.50" in page.content
    assert b"Reverse" in page.content
    # The edit page refuses a posted voucher.
    response = treasurer.get(reverse(f"{URL}voucher_edit", args=[voucher.pk]))
    assert response.status_code == 302


def test_unbalanced_draft_is_kept_with_problems(treasurer, year, chart, series):
    data = {"date": "2026-03-01", "description": "Fuel", "series": series.pk, "kind": "normal"}
    data |= lines_data((chart["7900"], "50", ""), (chart["1910"], "", "40"))
    treasurer.post(reverse(f"{URL}voucher_create"), data | {"post": "1"})
    voucher = Voucher.objects.get()
    assert voucher.is_draft
    page = treasurer.get(voucher.get_absolute_url())
    assert b"differ" in page.content


def test_date_must_be_in_an_open_year(treasurer, year, chart, series):
    data = {"date": "2025-12-31", "description": "Fuel", "series": series.pk, "kind": "normal"}
    data |= lines_data((chart["7900"], "50", ""), (chart["1910"], "", "50"))
    page = treasurer.post(reverse(f"{URL}voucher_create"), data)
    assert page.status_code == 200
    assert b"No financial year covers this date" in page.content
    assert not Voucher.objects.exists()


def test_reverse_through_the_page(treasurer, make_voucher):
    voucher = make_voucher([("7100", "10", "0"), ("1910", "0", "10")]).post()
    response = treasurer.post(
        reverse(f"{URL}voucher_reverse", args=[voucher.pk]),
        {"date": "2026-03-02", "note": "Wrong account"},
    )
    reversal = Voucher.objects.get(reverses=voucher)
    assert response.url == reversal.get_absolute_url()
    assert reversal.number == 2


def test_receipts(treasurer, make_voucher):
    voucher = make_voucher([("7100", "10", "0"), ("1910", "0", "10")])
    upload = SimpleUploadedFile("bill.pdf", b"%PDF-1.4 bill", content_type="application/pdf")
    treasurer.post(reverse(f"{URL}receipt_upload", args=[voucher.pk]), {"file": upload})
    receipt = Receipt.objects.get()
    assert receipt.content_type == "application/pdf"
    response = treasurer.get(reverse(f"{URL}receipt_download", args=[voucher.pk, receipt.pk]))
    assert b"".join(response.streaming_content) == b"%PDF-1.4 bill"
    assert response["Content-Security-Policy"] == "sandbox"

    bad = SimpleUploadedFile("run.exe", b"MZ", content_type="application/octet-stream")
    treasurer.post(reverse(f"{URL}receipt_upload", args=[voucher.pk]), {"file": bad})
    assert Receipt.objects.count() == 1

    voucher.post()
    treasurer.post(reverse(f"{URL}receipt_delete", args=[voucher.pk, receipt.pk]))
    assert Receipt.objects.filter(pk=receipt.pk).exists()


def test_delete_draft_only(treasurer, make_voucher):
    draft = make_voucher([("7100", "10", "0"), ("1910", "0", "10")])
    treasurer.post(reverse(f"{URL}voucher_delete", args=[draft.pk]))
    assert not Voucher.objects.filter(pk=draft.pk).exists()
    posted = make_voucher([("7100", "10", "0"), ("1910", "0", "10")]).post()
    response = treasurer.post(reverse(f"{URL}voucher_delete", args=[posted.pk]))
    assert response.status_code == 404
    assert Voucher.objects.filter(pk=posted.pk).exists()


@pytest.mark.parametrize("name", ["journal", "ledger", "trial_balance", "voucher_list"])
def test_reports_render(treasurer, make_voucher, year, name):
    make_voucher([("7100", "84.50", "0"), ("1910", "0", "84.50")]).post()
    page = treasurer.get(reverse(f"{URL}{name}"), {"year": year.pk})
    assert page.status_code == 200
    assert b"84.50" in page.content


def test_account_pages(treasurer, chart, make_voucher):
    make_voucher([("7100", "84.50", "0"), ("1910", "0", "84.50")]).post()
    assert treasurer.get(reverse(f"{URL}account_list")).status_code == 200
    page = treasurer.get(chart["7100"].get_absolute_url())
    assert b"84.50" in page.content
    response = treasurer.post(
        reverse(f"{URL}account_edit", args=[chart["7100"].pk]),
        {"number": "7101", "name": "Power", "kind": "expense", "active": "on"},
    )
    assert response.status_code == 302
    chart["7100"].refresh_from_db()
    assert (chart["7100"].number, chart["7100"].name) == ("7100", "Power")


@pytest.mark.parametrize(
    "role, can_view, can_post",
    [
        ("Admin", True, True),
        ("Treasurer", True, True),
        ("Board", True, False),
        ("Read-only", True, False),
        (None, False, False),
    ],
)
def test_roles(login, make_voucher, role, can_view, can_post):
    client = login("someone", role)
    voucher = make_voucher([("7100", "10", "0"), ("1910", "0", "10")])
    assert (client.get(reverse(f"{URL}journal")).status_code == 200) == can_view
    response = client.post(reverse(f"{URL}voucher_post", args=[voucher.pk]))
    assert (response.status_code == 302) == can_post
    if not can_post:
        assert response.status_code == 403


def test_add_on_stays_on_once_books_have_posted_vouchers(login, make_voucher, settings):
    settings.REQUIRE_MFA = False
    from apps.plugins.models import PluginState

    admin = login("admin", "Admin")
    admin.user.is_staff = True
    admin.user.save()
    voucher = make_voucher([("7100", "10", "0"), ("1910", "0", "10")])
    page = admin.get(reverse("plugins:list"))
    assert b"must be kept readable" not in page.content
    voucher.post()
    page = admin.get(reverse("plugins:list"))
    assert b"must be kept readable" in page.content
    admin.post(reverse("plugins:toggle", args=["bookkeeping"]), {"enabled": "0"})
    assert not PluginState.objects.filter(name="bookkeeping", enabled=False).exists()
