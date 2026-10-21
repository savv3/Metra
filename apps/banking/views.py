from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.formats import date_format
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, ngettext
from django.views.decorators.http import require_POST

from apps.invoicing.models import BillingSettings

from . import importers, matching
from .models import BankStatement, BankTransaction

Status = BankTransaction.Status


class UploadForm(forms.Form):
    file = forms.FileField(
        label=gettext_lazy("Bank file"),
        help_text=gettext_lazy(
            "The XML file from your online bank: camt.054 for reference payments, "
            "or camt.053, the account statement."
        ),
    )


def _with_counts(statements):
    return statements.annotate(
        lines=Count("transactions"),
        matched=Count("transactions", filter=Q(transactions__status=Status.MATCHED)),
        to_review=Count("transactions", filter=Q(transactions__status=Status.REVIEW)),
        received=Sum("transactions__amount", filter=Q(transactions__amount__gt=0)),
    )


@login_required
@permission_required("banking.view_bankstatement", raise_exception=True)
def statement_list(request, form=None):
    return render(
        request,
        "banking/statement_list.html",
        {
            "form": form or UploadForm(),
            "statements": _with_counts(BankStatement.objects.select_related("imported_by")),
            "formats": importers.importers(),
        },
    )


@login_required
@permission_required(["banking.add_bankstatement", "invoicing.add_payment"], raise_exception=True)
@require_POST
def statement_upload(request):
    form = UploadForm(request.POST, request.FILES)
    if form.is_valid():
        upload = form.cleaned_data["file"]
        try:
            statement = matching.import_file(upload.name, upload.read(), request.user)
        except matching.AlreadyImported as error:
            messages.error(
                request,
                _("This file was imported on %(date)s. Nothing was changed.")
                % {"date": date_format(error.statement.imported_at, "SHORT_DATE_FORMAT")},
            )
            return redirect(error.statement)
        except importers.StatementError as error:
            form.add_error("file", str(error))
        else:
            _report(request, statement)
            return redirect(statement)
    return statement_list(request, form)


def _report(request, statement):
    lines = statement.transactions.all()
    matched = lines.filter(status=Status.MATCHED).count()
    review = lines.filter(status=Status.REVIEW).count()
    messages.success(
        request,
        ngettext(
            "Imported the file: %(matched)s payment was recorded on its invoice.",
            "Imported the file: %(matched)s payments were recorded on their invoices.",
            matched,
        )
        % {"matched": matched},
    )
    if review:
        messages.warning(
            request,
            ngettext(
                "%(count)s payment needs checking by hand.",
                "%(count)s payments need checking by hand.",
                review,
            )
            % {"count": review},
        )
    if statement.skipped:
        messages.info(
            request,
            ngettext(
                "%(count)s line was skipped because an earlier file had it.",
                "%(count)s lines were skipped because earlier files had them.",
                statement.skipped,
            )
            % {"count": statement.skipped},
        )
    ours = BillingSettings.current().iban.replace(" ", "").upper()
    if ours and statement.account and statement.account != ours:
        messages.warning(
            request,
            _(
                "The file is for the account %(account)s, not the one on invoices "
                "(%(ours)s). Payments were matched by reference all the same."
            )
            % {"account": statement.account, "ours": ours},
        )


@login_required
@permission_required("banking.view_bankstatement", raise_exception=True)
def statement_detail(request, pk):
    statement = get_object_or_404(
        _with_counts(BankStatement.objects.select_related("imported_by")), pk=pk
    )
    lines = statement.transactions.select_related("invoice", "payment")
    show = request.GET.get("show", "")
    if show in Status.values:
        lines = lines.filter(status=show)
    return render(
        request,
        "banking/statement_detail.html",
        {"statement": statement, "lines": lines, "show": show, "statuses": Status.choices},
    )
