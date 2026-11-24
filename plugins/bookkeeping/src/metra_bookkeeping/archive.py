"""A financial year as files, so an accountant can take the books into their
own software and the books can be kept outside Metra: a ZIP with the chart
of accounts and balances and every posted voucher line as CSV, the receipts,
and the year in SIE 4, the Nordic text format for moving books between
programs.

Only posted vouchers are books; drafts are left out. The files are written
in the language the books are kept in. A closed year's accounts have the
names they had when it was closed.
"""

import csv
import io
import tempfile
import zipfile
from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.utils import timezone, translation
from django.utils.text import get_valid_filename
from django.utils.translation import gettext as _

from apps.plugins import api

from . import exports, package
from .models import Account, FiscalYear, Receipt, Voucher

ZERO = Decimal("0.00")
BALANCE_KINDS = (Account.Kind.ASSET, Account.Kind.LIABILITY, Account.Kind.EQUITY)
# SIE account types: T assets, S debts (liabilities and equity), I income,
# K costs.
SIE_TYPES = {
    Account.Kind.ASSET: "T",
    Account.Kind.LIABILITY: "S",
    Account.Kind.EQUITY: "S",
    Account.Kind.INCOME: "I",
    Account.Kind.EXPENSE: "K",
}


def books_language():
    return settings.LANGUAGE_CODE


def _iso(day):
    return day.isoformat() if day else ""


def posted_vouchers(year):
    vouchers = (
        Voucher.objects.filter(year=year, status=Voucher.Status.POSTED)
        .select_related("series", "reverses__series", "corrects", "posting__invoice")
        .prefetch_related("lines__account", "receipts")
        .order_by("date", "series__code", "number")
    )
    vouchers = list(vouchers)
    year.apply_chart(line.account for voucher in vouchers for line in voucher.lines.all())
    return vouchers


def opening_vouchers(year, vouchers):
    """The vouchers that are the year's opening balances: posted opening
    vouchers on the first day, on balance sheet accounts only, that no
    posted voucher reverses."""
    reversed_ids = {voucher.reverses_id for voucher in vouchers if voucher.reverses_id}
    return [
        voucher
        for voucher in vouchers
        if voucher.kind == Voucher.Kind.OPENING
        and voucher.date == year.start
        and voucher.pk not in reversed_ids
        and all(line.account.kind in BALANCE_KINDS for line in voucher.lines.all())
    ]


def chart(year):
    """[(number, name, kind)] of the year's chart of accounts, by number."""
    return sorted(
        ((entry.number, entry.name, entry.kind) for entry in package.chart(year)),
        key=lambda item: item[0],
    )


def account_totals(year, vouchers):
    """{account number: (opening, debit, credit)}; the opening balances are
    the opening vouchers' lines, the rest the year's other entries."""
    opening = {voucher.pk for voucher in opening_vouchers(year, vouchers)}
    totals = defaultdict(lambda: [ZERO, ZERO, ZERO])
    for voucher in vouchers:
        for line in voucher.lines.all():
            item = totals[line.account.number]
            if voucher.pk in opening:
                item[0] += line.debit - line.credit
            else:
                item[1] += line.debit
                item[2] += line.credit
    return {number: tuple(values) for number, values in totals.items()}


# CSV


def _csv(header, rows):
    buffer = io.StringIO()
    buffer.write("﻿")
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow([exports._safe(value) for value in header])
    for row in rows:
        writer.writerow([exports._safe(value) for value in row])
    return buffer.getvalue().encode("utf-8")


def accounts_csv(year, vouchers):
    kinds = dict(Account.Kind.choices)
    totals = account_totals(year, vouchers)
    header = [
        _("Account"),
        _("Account name"),
        _("Kind"),
        _("Opening balance"),
        _("Debit"),
        _("Credit"),
        _("Closing balance"),
    ]
    rows = []
    for number, name, kind in chart(year):
        opening, debit, credit = totals.get(number, (ZERO, ZERO, ZERO))
        closing = opening + debit - credit
        rows.append(
            [
                number,
                name,
                str(kinds.get(kind, kind)),
                exports.amount(opening),
                exports.amount(debit),
                exports.amount(credit),
                exports.amount(closing),
            ]
        )
    return _csv(header, rows)


def _source(voucher):
    posting = getattr(voucher, "posting", None)
    if posting is None:
        return ""
    return _("%(source)s, invoice %(number)s") % {
        "source": posting.get_source_display(),
        "number": posting.invoice.number,
    }


def vouchers_csv(year, vouchers, receipt_paths):
    kinds = dict(Voucher.Kind.choices)
    header = [
        _("Voucher"),
        _("Series"),
        _("Number"),
        _("Date"),
        _("Kind"),
        _("Description"),
        _("Reverses"),
        _("Corrects the year"),
        _("From invoicing"),
        _("Line"),
        _("Account"),
        _("Account name"),
        _("Line description"),
        _("Debit"),
        _("Credit"),
        _("VAT"),
        _("VAT rate (%)"),
        _("Receipts"),
    ]
    rows = []
    for voucher in vouchers:
        receipts = " | ".join(receipt_paths.get(r.pk, r.name) for r in voucher.receipts.all())
        for order, line in enumerate(voucher.lines.all(), start=1):
            rows.append(
                [
                    voucher.display_number,
                    voucher.series.code,
                    voucher.number,
                    _iso(voucher.date),
                    str(kinds.get(voucher.kind, voucher.kind)),
                    voucher.description,
                    voucher.reverses.display_number if voucher.reverses_id else "",
                    str(voucher.corrects) if voucher.corrects_id else "",
                    _source(voucher),
                    order,
                    line.account.number,
                    line.account.name,
                    line.description,
                    exports.amount(line.debit or ""),
                    exports.amount(line.credit or ""),
                    line.vat_code,
                    exports.amount(line.vat_rate) if line.vat_rate is not None else "",
                    receipts,
                ]
            )
    return _csv(header, rows)


# SIE 4


def _sie_text(value):
    """A quoted SIE string: no line breaks, quotes and backslashes escaped."""
    text = " ".join(str(value or "").split())
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _sie_amount(value):
    return f"{Decimal(value):.2f}"


def _sie_date(day):
    return day.strftime("%Y%m%d")


def sie4(year, vouchers=None, today=None):
    """The year as an SIE 4 file (type 4, transactions), in the PC8 (code
    page 437) encoding the format prescribes. Opening balances are #IB,
    the other posted vouchers #VER, and the balances at the end #UB (balance
    sheet accounts, without the year's result) and #RES (income and
    expenses). Amounts are debit positive, in euros."""
    vouchers = posted_vouchers(year) if vouchers is None else vouchers
    today = today or timezone.localdate()
    organisation = api.Organisation.current()
    opening = {voucher.pk for voucher in opening_vouchers(year, vouchers)}
    totals = account_totals(year, vouchers)
    lines = [
        "#FLAGGA 0",
        "#FORMAT PC8",
        "#SIETYP 4",
        f"#PROGRAM {_sie_text('Metra')} {_sie_text(getattr(settings, 'METRA_VERSION', ''))}",
        f"#GEN {_sie_date(today)}",
        f"#FNAMN {_sie_text(organisation.name if organisation else '')}",
    ]
    if organisation and organisation.business_id:
        lines.append(f"#ORGNR {_sie_text(organisation.business_id)}")
    lines += [
        f"#RAR 0 {_sie_date(year.start)} {_sie_date(year.end)}",
        "#VALUTA EUR",
    ]
    accounts = chart(year)
    for number, name, kind in accounts:
        lines.append(f"#KONTO {number} {_sie_text(name)}")
        lines.append(f"#KTYP {number} {SIE_TYPES[kind]}")
    for number, _name, kind in accounts:
        opening_balance, debit, credit = totals.get(number, (ZERO, ZERO, ZERO))
        if kind in BALANCE_KINDS:
            if opening_balance:
                lines.append(f"#IB 0 {number} {_sie_amount(opening_balance)}")
            closing = opening_balance + debit - credit
            if closing or opening_balance or debit or credit:
                lines.append(f"#UB 0 {number} {_sie_amount(closing)}")
        elif debit - credit:
            lines.append(f"#RES 0 {number} {_sie_amount(debit - credit)}")
    for voucher in vouchers:
        if voucher.pk in opening:
            continue
        registered = timezone.localdate(voucher.posted_at) if voucher.posted_at else voucher.date
        lines.append(
            f"#VER {_sie_text(voucher.series.code)} {voucher.number} {_sie_date(voucher.date)} "
            f"{_sie_text(voucher.description)} {_sie_date(registered)}"
        )
        lines.append("{")
        for line in voucher.lines.all():
            transaction = f"   #TRANS {line.account.number} {{}} {_sie_amount(line.amount)}"
            if line.description:
                transaction += f" {_sie_text('')} {_sie_text(line.description)}"
            lines.append(transaction)
        lines.append("}")
    text = "\r\n".join(lines) + "\r\n"
    return text.encode("cp437", errors="replace")


# The ZIP


def _safe_name(name, default):
    try:
        return get_valid_filename(name) or default
    except SuspiciousFileOperation:  # "." or ".."
        return default


def _receipt_paths(vouchers):
    """{receipt id: path in the ZIP}: receipts/<voucher>/<id>-<name>."""
    paths = {}
    for voucher in vouchers:
        folder = _safe_name(voucher.display_number, str(voucher.pk))
        for receipt in voucher.receipts.all():
            paths[receipt.pk] = (
                f"receipts/{folder}/{receipt.pk}-{_safe_name(receipt.name, 'receipt')}"
            )
    return paths


def _readme(year, vouchers, receipts, today):
    organisation = api.Organisation.current()
    values = {
        "organisation": organisation.name if organisation else "",
        "year": str(year),
        "start": _iso(year.start),
        "end": _iso(year.end),
        "status": str(year.get_status_display()),
        "made": _iso(today),
        "version": getattr(settings, "METRA_VERSION", ""),
        "vouchers": len(vouchers),
        "receipts": receipts,
        "books": _iso(year.books_kept_until),
        "kept": _iso(year.vouchers_kept_until),
    }
    parts = [
        _("The books of %(organisation)s for the financial year %(year)s (%(start)s to %(end)s).")
        % values,
        _("Status of the year: %(status)s. Exported from Metra %(version)s on %(made)s.") % values,
    ]
    if year.is_open:
        parts.append(
            _("The year is still open, so these books are preliminary and may still change.")
        )
    parts += [
        "",
        _(
            "accounts.csv: the chart of accounts with each account's opening balance, debits, "
            "credits and closing balance for the year."
        ),
        _(
            "vouchers.csv: every line of the %(vouchers)s posted vouchers in date order, with "
            "the voucher's number, date and description, the account and the amounts. Drafts "
            "are not part of the books and are left out."
        )
        % values,
        _("receipts/: the %(receipts)s attached receipts, in a folder per voucher.") % values,
        _(
            "books.se: the same year in SIE 4 for accounting software, encoded in PC8 (code page "
            "437). Opening balances are #IB, the other vouchers #VER."
        ),
        "",
        _(
            "The CSV files are UTF-8, separated by semicolons, with dates as YYYY-MM-DD and a "
            "comma for decimals. Balances are debits minus credits, in euros."
        ),
        "",
        _(
            "Keep the financial statements, journal, ledger, chart of accounts and list of books "
            "until at least %(books)s, and the vouchers and receipts until at least %(kept)s "
            "(KPL 2:10 §). The year-end package PDF in Metra holds the financial statements, "
            "journal and ledger."
        )
        % values,
    ]
    return ("\r\n".join(str(part) for part in parts) + "\r\n").encode("utf-8")


def year_zip(year, today=None):
    """The year's books as a ZIP in a temporary file, positioned at the
    start. The caller closes it."""
    today = today or timezone.localdate()
    with translation.override(books_language()):
        vouchers = posted_vouchers(year)
        paths = _receipt_paths(vouchers)
        output = tempfile.SpooledTemporaryFile(max_size=20 * 1024 * 1024)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("README.txt", _readme(year, vouchers, len(paths), today))
            archive.writestr("accounts.csv", accounts_csv(year, vouchers))
            archive.writestr("vouchers.csv", vouchers_csv(year, vouchers, paths))
            archive.writestr("books.se", sie4(year, vouchers, today))
            receipts = Receipt.objects.filter(pk__in=paths)
            for receipt in receipts:
                try:
                    source = receipt.file.open("rb")
                except FileNotFoundError:
                    # Said in the archive rather than left out silently.
                    archive.writestr(
                        paths[receipt.pk] + ".missing.txt",
                        _("The file of this receipt was not found on the server."),
                    )
                    continue
                with source, archive.open(paths[receipt.pk], "w") as to:
                    while chunk := source.read(1024 * 1024):
                        to.write(chunk)
    output.seek(0)
    return output


def filename(year, extension):
    return exports.filename(f"{_('Bookkeeping')} {year}", extension)


def log_export(request, year, kind):
    """Record in the audit log who exported which year's books."""
    from auditlog.models import LogEntry
    from django.contrib.contenttypes.models import ContentType

    LogEntry.objects.create(
        content_type=ContentType.objects.get_for_model(FiscalYear),
        object_pk=str(year.pk),
        object_id=year.pk,
        object_repr=str(year),
        action=LogEntry.Action.ACCESS,
        actor=request.user,
        additional_data={"export": kind},
    )
