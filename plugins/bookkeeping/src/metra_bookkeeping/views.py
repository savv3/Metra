import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, ProtectedError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import get_language, ngettext
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.plugins import api

from . import countries, exports, postings, reports, statements, timing, vat
from .forms import (
    AccountForm,
    BalanceSheetForm,
    BudgetForm,
    FiscalYearForm,
    IncomeStatementForm,
    LineFormSet,
    PostingSettingsForm,
    ReceiptForm,
    ReportForm,
    ReverseForm,
    SalesAccountsForm,
    SetupForm,
    VatRegistrationForm,
    VatSummaryForm,
    VoucherForm,
    VoucherSeriesForm,
    YearStaffForm,
)
from .models import (
    Account,
    FiscalYear,
    Posting,
    PostingSettings,
    Receipt,
    VatRegistration,
    Voucher,
    VoucherSeries,
)

P = "metra_bookkeeping"


def _errors(error):
    return error.messages if isinstance(error, ValidationError) else [str(error)]


# Overview and setup


@login_required
@permission_required(f"{P}.view_voucher", raise_exception=True)
def index(request):
    year = FiscalYear.current()
    if year is None:
        can_setup = request.user.has_perm(f"{P}.add_fiscalyear") and request.user.has_perm(
            f"{P}.add_account"
        )
        return render(
            request,
            "metra_bookkeeping/index.html",
            {"year": None, "setup_form": SetupForm() if can_setup else None},
        )
    vouchers = Voucher.objects.filter(year=year).select_related("series")
    posting_settings = PostingSettings.current()
    waiting = postings.waiting(posting_settings)
    return render(
        request,
        "metra_bookkeeping/index.html",
        {
            "year": year,
            "posting_settings": posting_settings,
            "waiting": waiting[:20],
            "waiting_count": len(waiting),
            "drafts": vouchers.filter(status=Voucher.Status.DRAFT).order_by("date", "pk"),
            "recent": vouchers.filter(status=Voucher.Status.POSTED).order_by("-posted_at", "-pk")[
                :10
            ],
            "late": timing.late_drafts(),
            "posted_count": vouchers.filter(status=Voucher.Status.POSTED).count(),
        },
    )


@login_required
@permission_required([f"{P}.add_fiscalyear", f"{P}.add_account"], raise_exception=True)
@require_POST
def setup(request):
    if FiscalYear.objects.exists():
        return redirect(f"{P}:index")
    form = SetupForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            year = form.save()
            if not Account.objects.exists():
                Account.create_chart(countries.get().CHARTS[year.chart], get_language())
            VoucherSeries.default()
        messages.success(
            request,
            _("The books are started. Enter the opening balances as the first voucher."),
        )
        return redirect(f"{P}:index")
    return render(request, "metra_bookkeeping/index.html", {"year": None, "setup_form": form})


# Financial years


@login_required
@permission_required(f"{P}.view_fiscalyear", raise_exception=True)
def year_list(request):
    years = FiscalYear.objects.annotate(voucher_count=Count("vouchers"))
    return render(request, "metra_bookkeeping/year_list.html", {"years": years})


@login_required
@permission_required(f"{P}.add_fiscalyear", raise_exception=True)
def year_create(request):
    latest = FiscalYear.objects.order_by("-end").first()
    initial = {}
    if latest is not None:
        start = latest.end + datetime.timedelta(days=1)
        initial = {
            "start": start,
            "end": start.replace(year=start.year + 1) - datetime.timedelta(1),
        }
    form = FiscalYearForm(
        request.POST or None,
        initial=initial,
        # A new year keeps the kind of organisation of the one before.
        instance=FiscalYear(chart=latest.chart) if latest else None,
    )
    if request.method == "POST" and form.is_valid():
        year = form.save()
        messages.success(request, _("The financial year %(year)s was added.") % {"year": year})
        return redirect(year)
    return render(request, "metra_bookkeeping/year_form.html", {"form": form, "year": None})


@login_required
@permission_required(f"{P}.view_fiscalyear", raise_exception=True)
def year_detail(request, pk):
    year = get_object_or_404(FiscalYear, pk=pk)
    counts = dict(
        year.vouchers.values_list("status").annotate(n=Count("pk")).values_list("status", "n")
    )
    return render(
        request,
        "metra_bookkeeping/year_detail.html",
        {
            "year": year,
            "chart_name": getattr(countries.get(year.country).CHARTS.get(year.chart), "name", ""),
            "posted": counts.get(Voucher.Status.POSTED, 0),
            "drafts": counts.get(Voucher.Status.DRAFT, 0),
            "can_edit": year.is_open,
            "dates_fixed": bool(counts.get(Voucher.Status.POSTED)),
        },
    )


@login_required
@permission_required(f"{P}.change_fiscalyear", raise_exception=True)
def year_edit(request, pk):
    year = get_object_or_404(FiscalYear, pk=pk)
    if not year.is_open:
        messages.error(request, _("The financial year %(year)s is closed.") % {"year": year})
        return redirect(year)
    # A year with posted vouchers keeps its dates; only its staff can change.
    posted = year.vouchers.filter(status=Voucher.Status.POSTED).exists()
    form = (YearStaffForm if posted else FiscalYearForm)(request.POST or None, instance=year)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("The financial year was saved."))
        return redirect(year)
    return render(request, "metra_bookkeeping/year_form.html", {"form": form, "year": year})


# Chart of accounts and voucher series


@login_required
@permission_required(f"{P}.view_account", raise_exception=True)
def account_list(request):
    accounts = Account.objects.annotate(entry_count=Count("lines"))
    return render(
        request,
        "metra_bookkeeping/account_list.html",
        {"accounts": accounts, "series": VoucherSeries.objects.all()},
    )


@login_required
@permission_required(f"{P}.add_account", raise_exception=True)
def account_create(request):
    form = AccountForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        account = form.save()
        messages.success(request, _("The account %(account)s was added.") % {"account": account})
        return redirect(f"{P}:account_list")
    return render(request, "metra_bookkeeping/account_form.html", {"form": form, "account": None})


@login_required
@permission_required(f"{P}.change_account", raise_exception=True)
def account_edit(request, pk):
    account = get_object_or_404(Account, pk=pk)
    form = AccountForm(request.POST or None, instance=account)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("The account was saved."))
        return redirect(f"{P}:account_list")
    return render(
        request, "metra_bookkeeping/account_form.html", {"form": form, "account": account}
    )


@login_required
@permission_required(f"{P}.delete_account", raise_exception=True)
@require_POST
def account_delete(request, pk):
    account = get_object_or_404(Account, pk=pk)
    try:
        account.delete()
    except (ValidationError, ProtectedError):
        messages.error(
            request, _("An account with entries cannot be deleted. Stop using it instead.")
        )
    else:
        messages.success(request, _("The account was deleted."))
    return redirect(f"{P}:account_list")


@login_required
@permission_required(f"{P}.add_voucherseries", raise_exception=True)
def series_create(request):
    form = VoucherSeriesForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("The voucher series was added."))
        return redirect(f"{P}:account_list")
    return render(request, "metra_bookkeeping/series_form.html", {"form": form, "series": None})


@login_required
@permission_required(f"{P}.change_voucherseries", raise_exception=True)
def series_edit(request, pk):
    series = get_object_or_404(VoucherSeries, pk=pk)
    form = VoucherSeriesForm(request.POST or None, instance=series)
    if series.vouchers.filter(status=Voucher.Status.POSTED).exists():
        form.fields["code"].disabled = True
        form.fields["code"].help_text = _("The series has posted vouchers, so its code stays.")
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("The voucher series was saved."))
        return redirect(f"{P}:account_list")
    return render(request, "metra_bookkeeping/series_form.html", {"form": form, "series": series})


# Vouchers


@login_required
@permission_required(f"{P}.view_voucher", raise_exception=True)
def voucher_list(request):
    form = ReportForm(request.GET or None)
    year, start, end = form.period()
    vouchers = Voucher.objects.none()
    if year is not None:
        vouchers = (
            Voucher.objects.filter(year=year, date__range=(start, end))
            .select_related("series")
            .order_by("status", "date", "series__code", "number", "pk")
        )
    return render(
        request,
        "metra_bookkeeping/voucher_list.html",
        {"form": form, "year": year, "vouchers": vouchers},
    )


def _voucher_form(request, voucher):
    form = VoucherForm(request.POST or None, instance=voucher)
    formset = LineFormSet(request.POST or None, instance=voucher or Voucher(), prefix="lines")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            saved = form.save(commit=False)
            if voucher is None:
                saved.created_by = request.user
            saved.save()
            formset.instance = saved
            lines = formset.save(commit=False)
            for removed in formset.deleted_objects:
                removed.delete()
            for order, line in enumerate(lines, start=1):
                line.order = line.order or order
                line.save()
        if request.POST.get("post") and request.user.has_perm(f"{P}.post_voucher"):
            return _post(request, saved)
        messages.success(request, _("The draft voucher was saved."))
        return redirect(saved)
    return render(
        request,
        "metra_bookkeeping/voucher_form.html",
        {"form": form, "formset": formset, "voucher": voucher},
    )


@login_required
@permission_required(f"{P}.add_voucher", raise_exception=True)
def voucher_create(request):
    if not FiscalYear.objects.filter(status=FiscalYear.Status.OPEN).exists():
        messages.error(request, _("Add a financial year first."))
        return redirect(f"{P}:index")
    return _voucher_form(request, None)


def _draft(pk):
    voucher = get_object_or_404(Voucher.objects.select_related("year", "series"), pk=pk)
    if not voucher.is_draft:
        raise Http404
    return voucher


@login_required
@permission_required(f"{P}.change_voucher", raise_exception=True)
def voucher_edit(request, pk):
    voucher = get_object_or_404(Voucher, pk=pk)
    if not voucher.is_draft:
        messages.error(
            request, _("A posted voucher cannot change. Correct it with a reversing voucher.")
        )
        return redirect(voucher)
    return _voucher_form(request, voucher)


@login_required
@permission_required(f"{P}.view_voucher", raise_exception=True)
def voucher_detail(request, pk):
    voucher = get_object_or_404(
        Voucher.objects.select_related(
            "year", "series", "reverses__series", "created_by", "posted_by"
        ),
        pk=pk,
    )
    debit, credit = voucher.totals()
    posting = (
        Posting.objects.filter(voucher=voucher)
        .select_related("invoice", "payment", "reminder")
        .first()
    )
    return render(
        request,
        "metra_bookkeeping/voucher_detail.html",
        {
            "voucher": voucher,
            "posting": posting,
            "lines": voucher.lines.select_related("account"),
            "receipts": voucher.receipts.all(),
            "reversals": voucher.reversals.select_related("series"),
            "debit": debit,
            "credit": credit,
            "problems": voucher.problems() if voucher.is_draft else [],
            "warnings": voucher.warnings(),
            "receipt_form": ReceiptForm(),
        },
    )


def _post(request, voucher):
    try:
        voucher.post(request.user)
    except ValidationError as error:
        for message in _errors(error):
            messages.error(request, message)
    else:
        messages.success(
            request,
            _("Voucher %(number)s was posted.") % {"number": voucher.display_number},
        )
    return redirect(voucher)


@login_required
@permission_required(f"{P}.post_voucher", raise_exception=True)
@require_POST
def voucher_post(request, pk):
    return _post(request, _draft(pk))


@login_required
@permission_required(f"{P}.delete_voucher", raise_exception=True)
def voucher_delete(request, pk):
    voucher = _draft(pk)
    if request.method == "POST":
        voucher.delete()
        messages.success(request, _("The draft voucher was deleted."))
        return redirect(f"{P}:voucher_list")
    return render(request, "metra_bookkeeping/voucher_confirm_delete.html", {"voucher": voucher})


@login_required
@permission_required([f"{P}.post_voucher", f"{P}.add_voucher"], raise_exception=True)
def voucher_reverse(request, pk):
    voucher = get_object_or_404(Voucher.objects.select_related("series"), pk=pk)
    if not voucher.can_be_reversed():
        messages.error(request, _("This voucher cannot be reversed."))
        return redirect(voucher)
    form = ReverseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reversal = voucher.reverse(
                request.user, form.cleaned_data["date"], form.cleaned_data["note"]
            )
        except ValidationError as error:
            for message in _errors(error):
                messages.error(request, message)
            return redirect(voucher)
        messages.success(
            request,
            _("Voucher %(number)s reverses it. Enter the right entry as a new voucher.")
            % {"number": reversal.display_number},
        )
        return redirect(reversal)
    return render(
        request, "metra_bookkeeping/voucher_reverse.html", {"voucher": voucher, "form": form}
    )


# Receipts


@login_required
@permission_required(f"{P}.change_voucher", raise_exception=True)
@require_POST
def receipt_upload(request, pk):
    voucher = get_object_or_404(Voucher, pk=pk)
    if not voucher.year.is_open:
        messages.error(
            request, _("The financial year %(year)s is closed.") % {"year": voucher.year}
        )
        return redirect(voucher)
    form = ReceiptForm(request.POST, request.FILES)
    if form.is_valid():
        upload = form.cleaned_data["file"]
        Receipt.objects.create(
            voucher=voucher,
            file=upload,
            name=upload.name[:200],
            size=upload.size,
            content_type=form.content_type(upload.name),
            uploaded_by=request.user,
        )
        messages.success(request, _("The receipt was added."))
    else:
        for errors in form.errors.values():
            for message in errors:
                messages.error(request, message)
    return redirect(voucher)


@login_required
@permission_required(f"{P}.view_voucher", raise_exception=True)
def receipt_download(request, pk, receipt_pk):
    receipt = get_object_or_404(Receipt, pk=receipt_pk, voucher_id=pk)
    response = FileResponse(
        receipt.file.open("rb"),
        as_attachment=False,
        filename=receipt.name,
        content_type=receipt.content_type,
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "sandbox"
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@permission_required(f"{P}.change_voucher", raise_exception=True)
@require_POST
def receipt_delete(request, pk, receipt_pk):
    receipt = get_object_or_404(Receipt, pk=receipt_pk, voucher_id=pk)
    try:
        receipt.delete()
    except ValidationError as error:
        for message in _errors(error):
            messages.error(request, message)
    else:
        messages.success(request, _("The receipt was removed."))
    return redirect(receipt.voucher)


# Postings from invoicing


@login_required
@permission_required(f"{P}.change_postingsettings", raise_exception=True)
def posting_settings(request):
    settings_row = PostingSettings.current()
    form = PostingSettingsForm(request.POST or None, instance=settings_row)
    accounts_form = SalesAccountsForm(request.POST or None)
    if request.method == "POST" and form.is_valid() and accounts_form.is_valid():
        with transaction.atomic():
            form.save()
            accounts_form.save()
        messages.success(request, _("The posting settings were saved."))
        return redirect(f"{P}:posting_settings")
    return render(
        request,
        "metra_bookkeeping/posting_settings.html",
        {
            "form": form,
            "accounts_form": accounts_form,
            "registrations": VatRegistration.objects.all(),
            "registration_form": VatRegistrationForm(),
            "waiting_count": len(postings.waiting(settings_row)),
            "template_missing": PostingSettings.template_accounts_missing(),
            "opening": postings.opening_receivables(settings_row),
        },
    )


@login_required
@permission_required(f"{P}.add_account", raise_exception=True)
@require_POST
def posting_accounts_add(request):
    """Add the accounts postings need from the chart template, for books
    started before the template had them."""
    added = [
        Account.objects.create(number=account.number, name=account.name(), kind=account.kind)
        for account in PostingSettings.template_accounts_missing()
    ]
    if added:
        messages.success(
            request,
            _("Added the accounts %(accounts)s.")
            % {"accounts": ", ".join(str(account) for account in added)},
        )
    return redirect(f"{P}:posting_settings")


@login_required
@permission_required(f"{P}.add_vatregistration", raise_exception=True)
@require_POST
def vat_registration_add(request):
    form = VatRegistrationForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, _("The VAT registration was saved."))
    else:
        for errors in form.errors.values():
            for message in errors:
                messages.error(request, message)
    return redirect(f"{P}:posting_settings")


@login_required
@permission_required(f"{P}.change_vatregistration", raise_exception=True)
def vat_registration_edit(request, pk):
    registration = get_object_or_404(VatRegistration, pk=pk)
    form = VatRegistrationForm(request.POST or None, instance=registration)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("The VAT registration was saved."))
        return redirect(f"{P}:posting_settings")
    return render(
        request,
        "metra_bookkeeping/vat_registration_form.html",
        {"form": form, "registration": registration},
    )


@login_required
@permission_required(f"{P}.delete_vatregistration", raise_exception=True)
@require_POST
def vat_registration_delete(request, pk):
    get_object_or_404(VatRegistration, pk=pk).delete()
    messages.success(request, _("The VAT registration was removed."))
    return redirect(f"{P}:posting_settings")


@login_required
@permission_required([f"{P}.add_voucher", f"{P}.post_voucher"], raise_exception=True)
@require_POST
def post_waiting(request):
    made, left = postings.book_waiting(request.user)
    drafts = sum(1 for voucher in made if voucher.is_draft)
    if made:
        messages.success(
            request,
            ngettext(
                "%(count)s voucher was made from invoicing.",
                "%(count)s vouchers were made from invoicing.",
                len(made),
            )
            % {"count": len(made)},
        )
    if drafts:
        messages.warning(
            request,
            ngettext(
                "%(count)s of them could not be posted; it is among the drafts.",
                "%(count)s of them could not be posted; they are among the drafts.",
                drafts,
            )
            % {"count": drafts},
        )
    if left:
        messages.warning(
            request,
            ngettext(
                "%(count)s record is still waiting: no open financial year covers its date.",
                "%(count)s records are still waiting: no open financial year covers their date.",
                left,
            )
            % {"count": left},
        )
    return redirect(f"{P}:index")


# Reports


def _query(request, **changes):
    query = request.GET.copy()
    for key, value in changes.items():
        query[key] = value
    return f"?{query.urlencode()}"


def _deliver(request, template, context, name, csv_rows=None, pdf_template=None):
    """The report as a page, or as a CSV or PDF file (``?format=``)."""
    context.setdefault("printed_at", timezone.localtime())
    wanted = request.GET.get("format")
    if context.get("year") is not None or context.get("summary") is not None:
        if wanted == "csv" and csv_rows is not None:
            header, rows = csv_rows(context)
            return exports.csv_response(name, header, rows)
        if wanted == "pdf":
            try:
                statement = context.get("statement")
                return exports.pdf_response(
                    request,
                    pdf_template or "metra_bookkeeping/pdf/report.html",
                    context,
                    name,
                    statement.language if statement else None,
                )
            except api.PDFUnavailable:
                messages.error(request, _("PDFs cannot be made on this server."))
    context["csv_url"] = _query(request, format="csv") if csv_rows is not None else ""
    context["pdf_url"] = _query(request, format="pdf")
    return render(request, template, context)


def _report(request, template, make, title, csv_rows, body):
    form = ReportForm(request.GET or None)
    year, start, end = form.period()
    context = {"form": form, "year": year, "start": start, "end": end, "title": title}
    if year is not None:
        context |= make(year, start, end)
    context["body"] = body
    return _deliver(request, template, context, f"{title} {year or ''}", csv_rows)


A = exports.amount


def _day(date):
    return date.isoformat() if date else ""


@login_required
@permission_required(f"{P}.view_voucher", raise_exception=True)
def journal(request):
    def make(year, start, end):
        vouchers, debit, credit = reports.journal(year, start, end)
        return {"vouchers": vouchers, "debit": debit, "credit": credit}

    def rows(context):
        header = [_("Date"), _("Voucher"), _("Account"), _("Account name"), _("Description")]
        header += [_("Debit"), _("Credit")]
        lines = [
            [
                _day(voucher.date),
                voucher.display_number,
                line.account.number,
                line.account.name,
                ": ".join(text for text in (voucher.description, line.description) if text),
                A(line.debit or ""),
                A(line.credit or ""),
            ]
            for voucher in context["vouchers"]
            for line in voucher.lines.all()
        ]
        return header, lines

    return _report(
        request,
        "metra_bookkeeping/journal.html",
        make,
        _("Journal"),
        rows,
        "metra_bookkeeping/_journal_table.html",
    )


def _ledger_rows(context):
    header = [_("Account"), _("Account name"), _("Date"), _("Voucher"), _("Description")]
    header += [_("Debit"), _("Credit"), _("Balance")]
    rows = []
    for item in context["accounts"]:
        account = item.account
        start = [account.number, account.name, _day(context["start"]), ""]
        rows.append([*start, _("Balance brought forward"), "", "", A(item.opening)])
        for line, balance in item.entries:
            voucher = line.voucher
            text = ": ".join(t for t in (voucher.description, line.description) if t)
            rows.append(
                [
                    account.number,
                    account.name,
                    _day(voucher.date),
                    voucher.display_number,
                    text,
                    A(line.debit or ""),
                    A(line.credit or ""),
                    A(balance),
                ]
            )
    return header, rows


@login_required
@permission_required(f"{P}.view_voucher", raise_exception=True)
def ledger(request):
    return _report(
        request,
        "metra_bookkeeping/ledger.html",
        lambda year, start, end: {"accounts": reports.ledger(year, start, end)},
        _("General ledger"),
        _ledger_rows,
        "metra_bookkeeping/_ledger_table.html",
    )


@login_required
@permission_required(f"{P}.view_voucher", raise_exception=True)
def account_ledger(request, pk):
    account = get_object_or_404(Account, pk=pk)
    return _report(
        request,
        "metra_bookkeeping/ledger.html",
        lambda year, start, end: {
            "accounts": reports.ledger(year, start, end, account),
            "account": account,
        },
        str(account),
        _ledger_rows,
        "metra_bookkeeping/_ledger_table.html",
    )


@login_required
@permission_required(f"{P}.view_voucher", raise_exception=True)
def trial_balance(request):
    def make(year, start, end):
        rows, totals = reports.trial_balance(year, start, end)
        return {"rows": rows, "totals": totals}

    def rows(context):
        header = [_("Account"), _("Account name"), _("At the start"), _("Debit"), _("Credit")]
        header.append(_("At the end"))
        lines = [
            [
                row.account.number,
                row.account.name,
                A(row.opening),
                A(row.debit),
                A(row.credit),
                A(row.closing),
            ]
            for row in context["rows"]
        ]
        return header, lines

    return _report(
        request,
        "metra_bookkeeping/trial_balance.html",
        make,
        _("Trial balance"),
        rows,
        "metra_bookkeeping/_trial_balance_table.html",
    )


# Financial statements


def _statement_rows(context):
    statement = context["statement"]
    header = [statement.title] + [column.label for column in statement.columns]
    notes = []
    if problems := statement.problems:
        texts = statement.texts
        notes = [[texts["preliminary"]], *([reason] for reason in problems)]
        notes.append([texts["not_statements"]])
    if note := statement.texts.get("translation"):
        notes.append([note])
    rows = notes + [
        ["  " * row.depth + row.name]
        + ([A(amount) for amount in row.amounts] if row.show_amounts else [""] * len(row.amounts))
        for row in statement.rows
    ]
    return header, rows


def _statement_page(request, form, make, template, kind):
    period = form.period()
    year = period[0]
    context = {"form": form, "year": year}
    if year is not None:
        size = statements.size_class(year)
        language, compare, micro = form.options(size.is_micro)
        statement = make(*period, language, compare, micro)
        context |= {
            "statement": statement,
            "size": size,
            "start": period[1] if len(period) == 3 else year.start,
            "end": period[-1],
            "translation": statement.texts.get("translation", ""),
        }
        name = f"{statement.title} {statement.columns[0].label}"
    else:
        name = kind
    return _deliver(
        request, template, context, name, _statement_rows, "metra_bookkeeping/pdf/statement.html"
    )


@login_required
@permission_required(f"{P}.view_voucher", raise_exception=True)
def income_statement(request):
    return _statement_page(
        request,
        IncomeStatementForm(request.GET or None),
        statements.income_statement,
        "metra_bookkeeping/income_statement.html",
        _("Income statement"),
    )


@login_required
@permission_required(f"{P}.view_voucher", raise_exception=True)
def balance_sheet(request):
    return _statement_page(
        request,
        BalanceSheetForm(request.GET or None),
        statements.balance_sheet,
        "metra_bookkeeping/balance_sheet.html",
        _("Balance sheet"),
    )


# Budget


@login_required
@permission_required(f"{P}.view_budget", raise_exception=True)
def budget(request):
    def make(year, start, end):
        income, expenses, totals = statements.budget_report(year, start, end)
        groups = [
            (_("Income"), income, totals["income"]),
            (_("Expenses"), expenses, totals["expenses"]),
        ]
        return {"income": income, "expenses": expenses, "totals": totals, "budget_groups": groups}

    def rows(context):
        header = [_("Account"), _("Account name"), _("Budget"), _("Actual"), _("Difference")]
        header.append(_("Of the budget (%)"))
        lines = []
        for group, total in (("income", _("Income")), ("expenses", _("Expenses"))):
            for row in context[group]:
                lines.append(
                    [
                        row.account.number,
                        row.account.name,
                        A(row.budget),
                        A(row.actual),
                        A(row.difference),
                        "" if row.used is None else row.used,
                    ]
                )
            item = context["totals"][group]
            lines.append(["", total, A(item.budget), A(item.actual), A(item.difference), ""])
        item = context["totals"]["result"]
        lines.append(["", _("Result"), A(item.budget), A(item.actual), A(item.difference), ""])
        return header, lines

    return _report(
        request,
        "metra_bookkeeping/budget.html",
        make,
        _("Budget follow-up"),
        rows,
        "metra_bookkeeping/_budget_table.html",
    )


@login_required
@permission_required(
    [f"{P}.add_budget", f"{P}.change_budget", f"{P}.delete_budget"], raise_exception=True
)
def budget_edit(request, pk):
    year = get_object_or_404(FiscalYear, pk=pk)
    form = BudgetForm(request.POST or None, year=year)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
        messages.success(request, _("The budget was saved."))
        return redirect(f"{reverse(f'{P}:budget')}?year={year.pk}")
    return render(request, "metra_bookkeeping/budget_form.html", {"form": form, "year": year})


# VAT


@login_required
@permission_required(f"{P}.view_voucher", raise_exception=True)
def vat_summary(request):
    form = VatSummaryForm(request.GET or None)
    start, end = form.period()
    summary = vat.summary(start, end)

    def rows(context):
        header = [_("From"), _("To"), _("VAT"), _("Rate (%)"), _("Base"), _("Tax")]
        lines = []
        for period in context["summary"].periods:
            dates = [_day(period.start), _day(period.end)]
            for rate, amounts in period.sales_rows:
                lines.append([*dates, _("Sales"), rate, A(amounts.base), A(amounts.vat)])
            for rate, amounts in period.purchase_rows:
                lines.append([*dates, _("Purchases"), rate, A(amounts.base), A(amounts.vat)])
            lines.append([*dates, _("To pay (to get back if negative)"), "", "", A(period.payable)])
        return header, lines

    context = {
        "form": form,
        "summary": summary,
        "start": start,
        "end": end,
        "title": _("VAT summary"),
    }
    context["body"] = "metra_bookkeeping/_vat_table.html"
    return _deliver(
        request,
        "metra_bookkeeping/vat_summary.html",
        context,
        f"{_('VAT summary')} {start.isoformat()} {end.isoformat()}",
        rows,
    )
