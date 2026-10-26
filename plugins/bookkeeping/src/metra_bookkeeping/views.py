import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, ProtectedError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import countries, reports, timing
from .forms import (
    AccountForm,
    FiscalYearForm,
    LineFormSet,
    ReceiptForm,
    ReportForm,
    ReverseForm,
    SetupForm,
    VoucherForm,
    VoucherSeriesForm,
)
from .models import Account, FiscalYear, Receipt, Voucher, VoucherSeries

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
    return render(
        request,
        "metra_bookkeeping/index.html",
        {
            "year": year,
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
            form.save()
            if "chart" in form.cleaned_data:
                chart = countries.get().CHARTS[form.cleaned_data["chart"]]
                Account.create_chart(chart, get_language())
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
    form = FiscalYearForm(request.POST or None, initial=initial)
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
            "posted": counts.get(Voucher.Status.POSTED, 0),
            "drafts": counts.get(Voucher.Status.DRAFT, 0),
            "can_edit": year.is_open and not counts.get(Voucher.Status.POSTED),
        },
    )


@login_required
@permission_required(f"{P}.change_fiscalyear", raise_exception=True)
def year_edit(request, pk):
    year = get_object_or_404(FiscalYear, pk=pk)
    if not year.is_open or year.vouchers.filter(status=Voucher.Status.POSTED).exists():
        messages.error(request, _("A year with posted vouchers keeps its dates."))
        return redirect(year)
    form = FiscalYearForm(request.POST or None, instance=year)
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
    return render(
        request,
        "metra_bookkeeping/voucher_detail.html",
        {
            "voucher": voucher,
            "lines": voucher.lines.select_related("account"),
            "receipts": voucher.receipts.all(),
            "reversals": voucher.reversals.select_related("series"),
            "debit": debit,
            "credit": credit,
            "problems": voucher.problems() if voucher.is_draft else [],
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


# Reports


def _report(request, template, make):
    form = ReportForm(request.GET or None)
    year, start, end = form.period()
    context = {"form": form, "year": year, "start": start, "end": end}
    if year is not None:
        context |= make(year, start, end)
    context["printed_at"] = timezone.localtime()
    return render(request, template, context)


@login_required
@permission_required(f"{P}.view_voucher", raise_exception=True)
def journal(request):
    def make(year, start, end):
        vouchers, debit, credit = reports.journal(year, start, end)
        return {"vouchers": vouchers, "debit": debit, "credit": credit}

    return _report(request, "metra_bookkeeping/journal.html", make)


@login_required
@permission_required(f"{P}.view_voucher", raise_exception=True)
def ledger(request):
    return _report(
        request,
        "metra_bookkeeping/ledger.html",
        lambda year, start, end: {"accounts": reports.ledger(year, start, end)},
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
    )


@login_required
@permission_required(f"{P}.view_voucher", raise_exception=True)
def trial_balance(request):
    def make(year, start, end):
        rows, totals = reports.trial_balance(year, start, end)
        return {"rows": rows, "totals": totals}

    return _report(request, "metra_bookkeeping/trial_balance.html", make)
