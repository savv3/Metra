from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.register.history import log_view, object_history

from .forms import InvoiceForm, LineFormSet, RunForm
from .models import BillingSettings, Invoice, InvoiceRun
from .runs import build_run, rebuild_invoice

STATUS_FILTERS = ["draft", "issued", "overdue", "credited", "credit_notes"]


def _filtered(params):
    invoices = Invoice.objects.select_related("unit", "person", "run")
    status = params.get("status", "")
    if status == "overdue":
        invoices = invoices.overdue()
    elif status == "credit_notes":
        invoices = invoices.filter(kind=Invoice.Kind.CREDIT_NOTE)
    elif status in Invoice.Status.values:
        invoices = invoices.filter(status=status)
    if (run := params.get("run", "")).isdigit():
        invoices = invoices.filter(run_id=run)
    if q := params.get("q", "").strip():
        invoices = invoices.filter(
            Q(number__icontains=q)
            | Q(unit__name__icontains=q)
            | Q(person__first_name__icontains=q)
            | Q(person__last_name__icontains=q)
        )
    filters = {"status": status, "run": params.get("run", ""), "q": q}
    return invoices, filters


@login_required
@permission_required("invoicing.view_invoice", raise_exception=True)
def invoice_list(request):
    invoices, filters = _filtered(request.GET)
    context = {
        "page": Paginator(invoices, 50).get_page(request.GET.get("page")),
        "filters": filters,
        "runs": InvoiceRun.objects.all(),
        "totals": invoices.aggregate(total=Sum("total"), count=Count("pk")),
    }
    if request.headers.get("HX-Target") == "results":
        return render(request, "invoicing/_invoice_results.html", context)
    return render(request, "invoicing/invoice_list.html", context)


@login_required
@permission_required("invoicing.view_invoice", raise_exception=True)
def invoice_detail(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related("unit", "person", "run", "credits"), pk=pk
    )
    context = {
        "invoice": invoice,
        "lines": invoice.lines.all(),
        "breakdown": invoice.vat_breakdown(),
        "credit_notes": invoice.credit_notes.all(),
        "can_issue_problems": invoice.check_can_issue() if invoice.is_draft else [],
    }
    can_edit = request.user.has_perm("invoicing.change_invoice") and invoice.is_draft
    if can_edit:
        formset = LineFormSet(request.POST or None, instance=invoice, prefix="lines")
        form = InvoiceForm(request.POST or None, instance=invoice)
        if request.method == "POST" and formset.is_valid() and form.is_valid():
            form.save()
            formset.save()
            invoice.compute_totals()
            invoice.save()
            messages.success(request, _("Saved the draft."))
            return redirect(invoice)
        context |= {"formset": formset, "form": form}
    log_view(invoice)
    if request.user.has_perm("auditlog.view_logentry"):
        context["history"] = object_history(invoice)
    return render(request, "invoicing/invoice_detail.html", context)


@login_required
@permission_required("invoicing.issue_invoice", raise_exception=True)
@require_POST
def invoice_issue(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    try:
        invoice.issue(request.user)
    except ValidationError as error:
        for message in error.messages:
            messages.error(request, message)
    else:
        messages.success(request, _("Issued %(invoice)s.") % {"invoice": invoice})
    return redirect(invoice)


@login_required
@permission_required("invoicing.change_invoice", raise_exception=True)
@require_POST
def invoice_rebuild(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    rebuild_invoice(invoice)
    messages.success(request, _("Rebuilt the draft from the fee plans and readings."))
    return redirect(invoice)


@login_required
@permission_required("invoicing.delete_invoice", raise_exception=True)
@require_POST
def invoice_delete(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk, status=Invoice.Status.DRAFT)
    run = invoice.run
    invoice.delete()
    messages.success(request, _("Deleted the draft."))
    return redirect(run or "invoicing:invoice_list")


@login_required
@permission_required(["invoicing.add_invoice", "invoicing.issue_invoice"], raise_exception=True)
@require_POST
def invoice_credit(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    try:
        note = invoice.make_credit_note(request.user)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
        return redirect(invoice)
    messages.success(
        request, _("A draft credit note was made. Change it to credit only part, then issue it.")
    )
    return redirect(note)


# Runs


@login_required
@permission_required("invoicing.view_invoicerun", raise_exception=True)
def run_list(request):
    runs = InvoiceRun.objects.annotate(
        drafts=Count("invoices", filter=Q(invoices__status=Invoice.Status.DRAFT)),
        issued=Count("invoices", filter=~Q(invoices__status=Invoice.Status.DRAFT)),
        total=Sum("invoices__total"),
    )
    return render(
        request,
        "invoicing/run_list.html",
        {"runs": runs, "settings_missing": not BillingSettings.current().iban},
    )


@login_required
@permission_required(["invoicing.add_invoicerun", "invoicing.add_invoice"], raise_exception=True)
def run_create(request):
    form = RunForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        run = form.save(commit=False)
        run.created_by = request.user
        run.save()
        form.save_m2m()
        created, _rebuilt, skipped = build_run(run)
        messages.success(request, _("Made %(count)s draft invoices.") % {"count": created})
        for unit in skipped:
            messages.warning(
                request, _("%(unit)s has no contact person, so no invoice.") % {"unit": unit}
            )
        return redirect(run)
    return render(request, "invoicing/run_form.html", {"form": form})


@login_required
@permission_required("invoicing.view_invoicerun", raise_exception=True)
def run_detail(request, pk):
    run = get_object_or_404(InvoiceRun, pk=pk)
    invoices = run.invoices.select_related("unit", "person").order_by("unit__name")
    drafts = [i for i in invoices if i.is_draft]
    context = {
        "run": run,
        "invoices": invoices,
        "drafts": len(drafts),
        "with_problems": [i for i in drafts if i.problems],
        "totals": invoices.aggregate(total=Sum("total"), vat=Sum("total_vat")),
    }
    return render(request, "invoicing/run_detail.html", context)


@login_required
@permission_required("invoicing.change_invoice", raise_exception=True)
@require_POST
def run_rebuild(request, pk):
    run = get_object_or_404(InvoiceRun, pk=pk)
    created, rebuilt, skipped = build_run(run)
    messages.success(
        request,
        _("Rebuilt %(rebuilt)s drafts and made %(created)s new ones.")
        % {"rebuilt": rebuilt, "created": created},
    )
    return redirect(run)


@login_required
@permission_required("invoicing.issue_invoice", raise_exception=True)
@require_POST
def run_issue(request, pk):
    """Issue every draft of the run that has nothing left to check."""
    run = get_object_or_404(InvoiceRun, pk=pk)
    issued, held = 0, 0
    for invoice in run.invoices.filter(status=Invoice.Status.DRAFT).order_by("unit__name", "pk"):
        if invoice.problems or invoice.check_can_issue():
            held += 1
            continue
        invoice.issue(request.user)
        issued += 1
    messages.success(request, _("Issued %(count)s invoices.") % {"count": issued})
    if held:
        messages.warning(
            request,
            _("%(count)s drafts were not issued: check them first.") % {"count": held},
        )
    return redirect(run)
