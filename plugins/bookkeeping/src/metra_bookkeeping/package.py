"""The year-end package for the auditor (tilintarkastaja or
toiminnantarkastaja), as one PDF: the financial statements (income
statement, balance sheet, notes and signature page), the balance sheet
specifications (tase-erittelyt), the list of books and material (luettelo
kirjanpidoista ja aineistoista), the chart of accounts, the journal and the
general ledger.

Only the package of a closed year is the financial statements; that of an
open year says on every part that it is preliminary. Its words are the
country module's own, in Finnish or Swedish (English marked as a
translation), never the interface's machine translations (KPL 3 ch.).
"""

from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.utils import formats, timezone

from . import countries, reports, statements, yearend
from .models import Account, ChartEntry, FiscalYear, FixedAsset, Voucher, VoucherSeries


@dataclass
class Note:
    key: str
    name: str
    default: str


def _text(texts, language):
    return texts.get(language) or texts["en"]


def notes(year, language, size_key):
    """The note headings of the year's size class, with their suggested
    texts in ``language``."""
    rules = countries.get(year.country)
    found = []
    for note in rules.NOTES:
        if size_key not in note["sizes"]:
            continue
        default = note["default"]
        if "fi" not in default:  # by size class
            default = default.get(size_key) or default["small"]
        text = _text(default, language).format(
            staff=formats.number_format(Decimal(year.staff).normalize())
        )
        found.append(Note(note["key"], _text(note["name"], language), text))
    return found


def _plan(asset, texts, language):
    if asset.method == FixedAsset.Method.STRAIGHT:
        return _text(texts["plan_straight"], language).format(years=asset.years)
    if asset.method == FixedAsset.Method.REDUCING:
        percent = formats.number_format(asset.percent.normalize())
        return _text(texts["plan_reducing"], language).format(percent=percent)
    return _text(texts["plan_none"], language)


def written_notes(year, language, size_key):
    """[(heading, [paragraphs])] for the notes: the treasurer's text, else
    the suggested one; the valuation note lists the depreciation plans, and
    corrections of earlier years booked in the year are listed."""
    rules = countries.get(year.country)
    texts = rules.PACKAGE_TEXTS
    saved = dict(year.notes.filter(language=language).values_list("key", "text"))
    plans = {note["key"] for note in rules.NOTES if note.get("plans")}
    result = []
    for note in notes(year, language, size_key):
        text = saved.get(note.key, note.default)
        paragraphs = [part for part in text.split("\n\n") if part.strip()]
        if note.key in plans:
            assets = FixedAsset.objects.filter(acquired__lte=year.end).exclude(
                disposed__lt=year.start
            )
            paragraphs += [f"{asset.name}: {_plan(asset, texts, language)}" for asset in assets]
        if paragraphs:
            result.append((note.name, paragraphs))
    corrections = year.vouchers.filter(
        status=Voucher.Status.POSTED, corrects__isnull=False
    ).select_related("series", "corrects")
    if corrections:
        corrects = _text(texts["corrects"], language)
        result.append(
            (
                _text(texts["corrections"], language),
                [
                    f"{voucher.display_number} {_short(voucher.date)}: {voucher.description} "
                    f"({corrects} {voucher.corrects})"
                    for voucher in corrections
                ],
            )
        )
    return result


def _short(date):
    return f"{date.day}.{date.month}.{date.year}"


def chart(year):
    """The chart of accounts: as it was at closing for a closed year."""
    if not year.is_open:
        return list(ChartEntry.objects.filter(year=year))
    return list(Account.objects.all())


def list_of_books(year, texts, language):
    """[(book or material, kept as, kept until)]."""

    def t(key, **values):
        return _text(texts[key], language).format(**values)

    books, vouchers = _short(year.books_kept_until), _short(year.vouchers_kept_until)
    electronic = t("electronic")
    rows = [
        (t("book_statements"), t("signed_paper"), books),
        (t("book_specifications"), electronic, books),
        (t("book_journal"), electronic, books),
        (t("book_ledger"), electronic, books),
        (t("book_chart"), electronic, books),
    ]
    for series in VoucherSeries.objects.all():
        numbers = year.vouchers.filter(series=series, status=Voucher.Status.POSTED).values_list(
            "number", flat=True
        )
        if numbers:
            name = f"{series.code} {series.name}".strip()
            label = t("book_series", series=name, first=min(numbers), last=max(numbers))
            rows.append((label, electronic, vouchers))
    if year.vouchers.filter(posting__isnull=False).exists():
        rows.append((t("book_invoicing"), electronic, vouchers))
    rows.append((t("book_bank"), t("bank_kept"), vouchers))
    return rows


def build(year, language="fi", compare=True, micro=False, statements_only=False):
    """Everything the package template shows."""
    rules = countries.get(year.country)
    texts = {key: _text(value, language) for key, value in rules.PACKAGE_TEXTS.items()}
    size = statements.size_class(year)
    micro = micro and size.is_micro
    income = statements.income_statement(year, year.start, year.end, language, compare, micro)
    balance = statements.balance_sheet(year, year.end, language, compare, micro)
    problems = list(dict.fromkeys(income.problems + balance.problems))
    version = getattr(settings, "METRA_VERSION", "")
    context = {
        "year": year,
        "language": language,
        "texts": texts,
        "statement_texts": income.texts,
        "income": income,
        "balance": balance,
        "problems": problems,
        "size": size,
        "statements_only": statements_only,
        "notes": written_notes(year, language, "micro" if micro else size.key),
        "signers": [name for name in year.signers.splitlines() if name.strip()],
        "due": texts["due"].format(day=_short(year.statements_due)),
        "cooperative": year.chart == "cooperative",
        "period": f"{_short(year.start)}–{_short(year.end)}",
        "translation": income.texts.get("translation", ""),
        "printed_at": timezone.localtime(),
    }
    if statements_only:
        return context
    reason = {
        FiscalYear.Length.FIRST: "length_first",
        FiscalYear.Length.LAST: "length_last",
        FiscalYear.Length.CHANGE: "length_change",
    }.get(year.length_reason)
    vouchers, debit, credit = reports.journal(year, year.start, year.end)
    kinds = {kind: texts[f"kind_{kind}"] for kind in Account.Kind.values}
    context |= {
        "balances": [
            (account, amount)
            for account, amount in sorted(
                yearend.closing_balances(year).items(), key=lambda item: item[0].number
            )
        ],
        "bank_rows": yearend.bank_rows(year),
        "asset_accounts": yearend.asset_accounts(year),
        "receivables": yearend.receivables_rows(year),
        "books": list_of_books(year, rules.PACKAGE_TEXTS, language),
        "books_text": texts["books_text"].format(version=version),
        "software": texts["software"].format(version=version),
        "length": texts["length"].format(reason=texts[reason]) if reason else "",
        "chart": [(entry, kinds.get(entry.kind, entry.kind)) for entry in chart(year)],
        "chart_note": texts["chart_note"] if not year.is_open else "",
        "vouchers": vouchers,
        "debit": debit,
        "credit": credit,
        "accounts": reports.ledger(year, year.start, year.end),
        "start": year.start,
        "end": year.end,
    }
    year.apply_chart([account for account, _amount in context["balances"]])
    return context
