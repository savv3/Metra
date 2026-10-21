"""Sending issued invoices: by email with the PDF attached, or in a print batch.

A recipient whose preferred channel is post, or who has no email address,
gets a letter; so does everyone when email is not set up. Invoices do not
go by SMS, so a recipient who prefers SMS gets the email (see
apps.messaging.preference). Every email is a
message record in its send-out, so its status shows like any other message.
"""

import inspect

from django.utils import timezone, translation
from django.utils.translation import gettext as _

from apps.messaging.failures import notify_failures
from apps.messaging.models import (
    Channel,
    Message,
    MessageBatch,
    MessageTemplate,
    organisation_placeholders,
)
from apps.messaging.preference import channel_order
from apps.messaging.registry import EMAIL, ProviderError, provider_for

from .models import Invoice, InvoiceDelivery
from .pdf import PDFUnavailable, render_pdf


def channel_for(invoice):
    if channel_order(invoice.person, offered=(EMAIL,)):
        return InvoiceDelivery.Channel.EMAIL
    return InvoiceDelivery.Channel.LETTER


def unsent(invoices):
    """Issued invoices that have not been emailed or put in a print batch yet."""
    return invoices.issued().filter(deliveries__isnull=True)


def placeholders(invoice):
    person = invoice.person
    return organisation_placeholders() | {
        "first_name": person.first_name,
        "name": person.full_name,
        "number": invoice.number,
        "total": f"{invoice.total:.2f}".replace(".", ","),
        "due_date": (
            f"{invoice.due_date.day}.{invoice.due_date.month}.{invoice.due_date.year}"
            if invoice.due_date
            else ""
        ),
        "reference": invoice.reference_display,
        "unit": invoice.unit.name,
    }


def filename(invoice):
    prefix = _("credit-note") if invoice.kind == Invoice.Kind.CREDIT_NOTE else _("invoice")
    return f"{prefix}-{invoice.number}.pdf"


def send_invoices(batch, invoices):
    """Email or queue for printing each invoice; records a message per invoice."""
    batch.status = MessageBatch.Status.SENDING
    batch.save(update_fields=["status"])
    template = MessageTemplate.objects.filter(purpose="invoice", channel=Channel.EMAIL).first()
    provider = provider_for(EMAIL)
    with translation.override(translation.get_language() or "sv"):
        for invoice in invoices:
            if invoice.deliveries.exists():
                continue
            if channel_for(invoice) == InvoiceDelivery.Channel.LETTER or template is None:
                message = Message.objects.create(
                    batch=batch,
                    person=invoice.person,
                    unit=invoice.unit,
                    channel=Channel.LETTER,
                    status=Message.Status.TO_PRINT,
                    subject=str(invoice),
                )
                InvoiceDelivery.objects.create(
                    invoice=invoice, channel=InvoiceDelivery.Channel.LETTER, message=message
                )
                continue
            _email(batch, invoice, template, provider)
    batch.status = MessageBatch.Status.DONE
    batch.finished_at = timezone.now()
    batch.save(update_fields=["status", "finished_at"])
    notify_failures(batch)


def _email(batch, invoice, template, provider):
    values = placeholders(invoice)
    subject = MessageTemplate.fill(template.subject, values)
    body = MessageTemplate.fill(template.body, values)
    message = Message.objects.create(
        batch=batch,
        person=invoice.person,
        unit=invoice.unit,
        channel=Channel.EMAIL,
        recipient=invoice.person.email,
        subject=subject,
        body=body,
        provider=provider.name,
    )
    try:
        pdf = render_pdf([invoice])
        extra = {}
        if "attachments" in inspect.signature(provider.send).parameters:
            extra["attachments"] = [(filename(invoice), pdf, "application/pdf")]
        else:
            raise ProviderError(_("This email provider cannot attach the invoice PDF."))
        result = provider.send(invoice.person.email, body, subject=subject, **extra)
    except (ProviderError, PDFUnavailable) as error:
        message.status = Message.Status.FAILED
        message.error = str(error)
    else:
        message.status = result.status
        message.provider_id = result.provider_id
        message.sent_at = timezone.now()
        InvoiceDelivery.objects.create(
            invoice=invoice, channel=InvoiceDelivery.Channel.EMAIL, message=message
        )
    message.status_changed_at = timezone.now()
    message.save()
