from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.messaging.models import MessageBatch
from apps.register import csv_io
from apps.register.history import log_view, object_history

from . import payments
from .delivery import channel_for, filename, unsent
from .forms import InvoiceForm, LineFormSet, PaymentForm, PaymentsExportForm, RunForm
from .models import (
    BillingSettings,
    Invoice,
    InvoiceDelivery,
    InvoiceRun,
    Payment,
    PaymentReminder,
)
from .pdf import PDFUnavailable, render_pdf
from .runs import build_run, rebuild_invoice
from .tasks import send_invoices_task, send_reminders_task

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
        "deliveries": invoice.deliveries.select_related("message"),
        "payments": invoice.payments.select_related("recorded_by"),
        "reminders": invoice.reminders.select_related("message"),
        "outstanding": invoice.outstanding(),
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
    if invoice.kind == Invoice.Kind.INVOICE and not invoice.is_draft:
        context["payment_form"] = PaymentForm(
            initial={
                "amount": max(context["outstanding"], 0) or None,
                "paid_on": timezone.localdate(),
                "reference": invoice.reference,
            }
        )
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
        "unsent": unsent(run.invoices.all()).count(),
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


# PDFs and sending


def pdf_response(pdf, name, inline=True):
    response = HttpResponse(pdf, content_type="application/pdf")
    disposition = "inline" if inline else "attachment"
    response["Content-Disposition"] = f'{disposition}; filename="{name}"'
    response["Cache-Control"] = "private, no-store"
    return response


def _pdf_or_message(request, invoices, name, fallback):
    try:
        pdf = render_pdf(invoices)
    except PDFUnavailable as error:
        messages.error(request, str(error))
        return redirect(fallback)
    return pdf_response(pdf, name)


@login_required
@permission_required("invoicing.view_invoice", raise_exception=True)
def invoice_pdf(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    log_view(invoice)
    name = filename(invoice) if invoice.number else "draft.pdf"
    return _pdf_or_message(request, [invoice], name, invoice)


@login_required
@permission_required("invoicing.view_invoice", raise_exception=True)
def run_print(request, pk):
    """One PDF with every issued invoice of the run that goes by post."""
    run = get_object_or_404(InvoiceRun, pk=pk)
    invoices = [
        invoice
        for invoice in run.invoices.issued().select_related("person", "unit").order_by("sequence")
        if channel_for(invoice) == InvoiceDelivery.Channel.LETTER
    ]
    if not invoices:
        messages.info(request, _("No invoices in this run go by post."))
        return redirect(run)
    return _pdf_or_message(request, invoices, f"invoices-{run.period_label}-post.pdf", run)


@login_required
@permission_required("invoicing.view_invoice", raise_exception=True)
def batch_print(request, pk):
    """The letters of a send-out of invoices, as one PDF to print."""
    batch = get_object_or_404(
        MessageBatch,
        pk=pk,
        kind__in=[MessageBatch.Kind.INVOICES, MessageBatch.Kind.PAYMENT_REMINDERS],
    )
    reminders = None
    if batch.kind == MessageBatch.Kind.PAYMENT_REMINDERS:
        found = PaymentReminder.objects.filter(
            message__batch=batch, channel="letter"
        ).select_related("invoice")
        reminders = {reminder.invoice_id: reminder for reminder in found}
        invoices = [reminder.invoice for reminder in found]
    else:
        invoices = list(
            Invoice.objects.filter(
                deliveries__message__batch=batch,
                deliveries__channel=InvoiceDelivery.Channel.LETTER,
            ).order_by("sequence")
        )
    if not invoices:
        messages.info(request, _("There is nothing to print in this send-out."))
        return redirect(batch)
    try:
        pdf = render_pdf(invoices, reminders=reminders)
    except PDFUnavailable as error:
        messages.error(request, str(error))
        return redirect(batch)
    return pdf_response(pdf, f"post-{batch.pk}.pdf")


@login_required
@permission_required(["invoicing.issue_invoice", "invoicing.view_invoice"], raise_exception=True)
@require_POST
def run_send(request, pk):
    """Email the run's issued invoices that have not gone out yet; the rest are
    listed for printing on the send-out page."""
    run = get_object_or_404(InvoiceRun, pk=pk)
    invoices = list(unsent(run.invoices.all()).values_list("pk", flat=True))
    if not invoices:
        messages.info(request, _("All issued invoices of this run have been sent."))
        return redirect(run)
    batch = MessageBatch.objects.create(
        kind=MessageBatch.Kind.INVOICES,
        channels=MessageBatch.Channels.EMAIL,
        audience=str(run),
        created_by=request.user,
    )
    send_invoices_task(batch.pk, invoices)
    messages.success(request, _("Sending has started. This page shows how it goes."))
    return redirect(batch)


# Payments, reminders and exports


@login_required
@permission_required("invoicing.add_payment", raise_exception=True)
@require_POST
def invoice_pay(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    form = PaymentForm(request.POST)
    if form.is_valid():
        try:
            payments.record_payment(invoice, user=request.user, **form.cleaned_data)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, _("Recorded the payment."))
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return redirect(invoice)


@login_required
@permission_required("invoicing.view_invoice", raise_exception=True)
def overdue_list(request):
    invoices = list(
        Invoice.objects.overdue().select_related("unit", "person").order_by("due_date", "sequence")
    )
    today = timezone.localdate()
    for invoice in invoices:
        invoice.to_pay = invoice.outstanding()
        invoice.days_late = (today - invoice.current_due_date).days
        invoice.reminder_count = invoice.reminders.count()
    return render(
        request,
        "invoicing/overdue_list.html",
        {"invoices": invoices, "billing": BillingSettings.current()},
    )


@login_required
@permission_required(
    ["invoicing.add_paymentreminder", "invoicing.view_invoice"], raise_exception=True
)
@require_POST
def send_reminders(request):
    chosen = [pk for pk in request.POST.getlist("invoices") if pk.isdigit()]
    invoice_ids = list(Invoice.objects.overdue().filter(pk__in=chosen).values_list("pk", flat=True))
    if not invoice_ids:
        messages.error(request, _("Choose at least one overdue invoice."))
        return redirect("invoicing:overdue_list")
    batch = MessageBatch.objects.create(
        kind=MessageBatch.Kind.PAYMENT_REMINDERS,
        channels=MessageBatch.Channels.SMS_OR_EMAIL,
        audience=_("%(count)s overdue invoices") % {"count": len(invoice_ids)},
        created_by=request.user,
    )
    send_reminders_task(batch.pk, invoice_ids, request.user.pk)
    messages.success(request, _("Sending has started. This page shows how it goes."))
    return redirect(batch)


def _money(value):
    return f"{value:.2f}".replace(".", ",")


@login_required
@permission_required("invoicing.view_invoice", raise_exception=True)
def export_invoices(request):
    """The filtered invoice list as CSV, for the bookkeeping."""
    invoices, filters = _filtered(request.GET)
    invoices = list(invoices.exclude(status=Invoice.Status.DRAFT).order_by("sequence"))
    header = [
        _("Number"),
        _("Kind"),
        _("Invoice date"),
        _("Due date"),
        _("Recipient"),
        _("Unit"),
        _("Reference"),
        _("Without VAT"),
        _("VAT"),
        _("Total"),
        _("Credited"),
        _("Paid"),
        _("Reminder fees"),
        _("Outstanding"),
        _("Status"),
        _("Credits invoice"),
    ]
    rows = []
    for invoice in invoices:
        rows.append(
            [
                invoice.number,
                invoice.get_kind_display(),
                invoice.issue_date.isoformat() if invoice.issue_date else "",
                invoice.due_date.isoformat() if invoice.due_date else "",
                invoice.buyer.get("name", ""),
                invoice.buyer.get("unit", ""),
                invoice.reference_display,
                _money(invoice.total_net),
                _money(invoice.total_vat),
                _money(invoice.total),
                _money(invoice.credited_amount()),
                _money(invoice.paid_amount()),
                _money(invoice.fees_amount()),
                _money(invoice.outstanding()),
                invoice.get_status_display(),
                invoice.credits.number if invoice.credits else "",
            ]
        )
    csv_io.log_export(request, Invoice, invoices, filters)
    return csv_io.csv_response(f"invoices-{timezone.localdate():%Y-%m-%d}.csv", header, rows)


@login_required
@permission_required(["invoicing.view_payment", "invoicing.view_invoice"], raise_exception=True)
def export_payments(request):
    """Payments and reminder fees in a date range, as CSV for the bookkeeping."""
    form = PaymentsExportForm(request.GET or None)
    if not request.GET or not form.is_valid():
        return render(request, "invoicing/export_payments.html", {"form": form})
    start, end = form.cleaned_data["start"], form.cleaned_data["end"]
    found = Payment.objects.select_related("invoice", "recorded_by")
    fees = PaymentReminder.objects.select_related("invoice").exclude(fee=0)
    if start:
        found = found.filter(paid_on__gte=start)
        fees = fees.filter(created_at__date__gte=start)
    if end:
        found = found.filter(paid_on__lte=end)
        fees = fees.filter(created_at__date__lte=end)
    header = [
        _("Date"),
        _("Kind"),
        _("Invoice"),
        _("Reference"),
        _("Amount"),
        _("Note"),
        _("Recorded by"),
    ]
    rows = [
        [
            payment.paid_on.isoformat(),
            _("Payment"),
            payment.invoice.number,
            payment.reference or payment.invoice.reference_display,
            _money(payment.amount),
            payment.note,
            str(payment.recorded_by or ""),
        ]
        for payment in found
    ] + [
        [
            timezone.localdate(fee.created_at).isoformat(),
            _("Reminder fee"),
            fee.invoice.number,
            fee.invoice.reference_display,
            _money(fee.fee),
            "",
            str(fee.sent_by or ""),
        ]
        for fee in fees
    ]
    rows.sort(key=lambda row: row[0])
    csv_io.log_export(request, Payment, list(found), {"start": str(start), "end": str(end)})
    return csv_io.csv_response(f"payments-{timezone.localdate():%Y-%m-%d}.csv", header, rows)
