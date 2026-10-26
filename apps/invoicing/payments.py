"""Recording payments and sending payment reminders.

Payment reminders follow the Finnish Debt Collection Act (laki saatavien
perinnästä): a reminder may carry a reasonable fee, for consumers at most
5 €, and gives the debtor at least 14 days before any further steps. The fee
and the days are settings; this module does not decide when to remind.
"""

import datetime
import inspect

from django.db import transaction
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
from apps.plugins import events

from .delivery import filename
from .models import BillingSettings, Payment, PaymentReminder
from .pdf import PDFUnavailable, render_pdf


@transaction.atomic
def record_payment(invoice, amount, paid_on, reference="", note="", user=None):
    payment = Payment(
        invoice=invoice,
        amount=amount,
        paid_on=paid_on,
        reference=reference,
        note=note,
        recorded_by=user,
    )
    payment.full_clean()
    payment.save()
    invoice.refresh_payment_status()
    events.send_on_commit(events.payment_recorded, Payment, payment=payment)
    return payment


def _date(value):
    return f"{value.day}.{value.month}.{value.year}" if value else ""


def reminder_placeholders(invoice, reminder):
    person = invoice.person
    return organisation_placeholders() | {
        "first_name": person.first_name,
        "name": person.full_name,
        "number": invoice.number,
        "amount": f"{invoice.outstanding():.2f}".replace(".", ","),
        "fee": f"{reminder.fee:.2f}".replace(".", ","),
        "due_date": _date(invoice.due_date),
        "new_due_date": _date(reminder.new_due_date),
        "reference": invoice.reference_display,
        "iban": invoice.seller.get("iban", ""),
        "unit": invoice.unit.name,
    }


def channel_for(person):
    """The person's preferred channel, then the other one, else a printed
    letter (see apps.messaging.preference). An email has the reminder PDF."""
    return next(iter(channel_order(person)), Channel.LETTER)


def send_reminders(batch, invoices, user=None):
    """One reminder per overdue invoice; records the fee, the new due date and
    the message. Invoices no longer overdue (paid meanwhile) are skipped."""
    billing = BillingSettings.current()
    batch.status = MessageBatch.Status.SENDING
    batch.save(update_fields=["status"])
    with translation.override(translation.get_language() or "sv"):
        for invoice in invoices:
            if not invoice.is_overdue:
                continue
            with transaction.atomic():
                reminder = PaymentReminder.objects.create(
                    invoice=invoice,
                    fee=billing.reminder_fee,
                    new_due_date=timezone.localdate()
                    + datetime.timedelta(days=max(billing.reminder_days, 14)),
                    channel=channel_for(invoice.person),
                    sent_by=user,
                )
                events.send_on_commit(events.reminder_sent, PaymentReminder, reminder=reminder)
            _deliver(batch, invoice, reminder)
    batch.status = MessageBatch.Status.DONE
    batch.finished_at = timezone.now()
    batch.save(update_fields=["status", "finished_at"])
    notify_failures(batch)


def _deliver(batch, invoice, reminder):
    person = invoice.person
    channel = reminder.channel
    message = Message(batch=batch, person=person, unit=invoice.unit, channel=channel)
    if channel == Channel.LETTER:
        message.status = Message.Status.TO_PRINT
        message.subject = str(invoice)
        message.save()
        _link(reminder, message)
        return
    template = MessageTemplate.objects.filter(purpose="payment_reminder", channel=channel).first()
    provider = provider_for(channel)
    values = reminder_placeholders(invoice, reminder)
    message.recipient = person.email if channel == EMAIL else person.phone
    message.subject = MessageTemplate.fill(template.subject, values) if template else ""
    message.body = MessageTemplate.fill(template.body, values) if template else ""
    message.provider = provider.name
    message.save()
    try:
        if template is None:
            raise ProviderError(_("There is no message template for this. Add one under Settings."))
        extra = {}
        if channel == EMAIL:
            pdf = render_pdf([invoice], reminders={invoice.pk: reminder})
            if "attachments" in inspect.signature(provider.send).parameters:
                extra["attachments"] = [(filename(invoice), pdf, "application/pdf")]
        result = provider.send(message.recipient, message.body, subject=message.subject, **extra)
    except (ProviderError, PDFUnavailable) as error:
        message.status = Message.Status.FAILED
        message.error = str(error)
    else:
        message.status = result.status
        message.provider_id = result.provider_id
        message.sent_at = timezone.now()
    message.status_changed_at = timezone.now()
    message.save()
    _link(reminder, message)


def _link(reminder, message):
    # The reminder is a locked record: link its message with a plain update.
    PaymentReminder.objects.filter(pk=reminder.pk).update(message=message)
