"""Vouchers from invoicing: issued invoices and credit notes (on the accrual
basis, dated the invoice date), payments (dated the day paid) and reminder
fees (dated the day the reminder was made).

Each record is booked once, in a voucher of its own that points to it (see
Posting); the record is the voucher's evidence. The voucher is posted at
once. When it cannot be (an account no longer in use, say), it stays a
draft for the treasurer to fix and post. Records dated in no open financial
year, or made while the add-on was off, are listed as waiting and can be
posted from the overview.

    invoice      receivables Dr total; sales Cr net, per account and VAT
                 rate; VAT on sales Cr the VAT of each rate
    credit note  the same, with the sides turned (its amounts are negative)
    payment      bank Dr amount; receivables Cr amount (a negative payment,
                 which undoes one, turns the sides)
    reminder     receivables Dr fee; reminder fees Cr fee, without VAT (a
                 reminder fee compensates collection costs; it is not a sale)

So the receivables account always equals what is outstanding on the
invoices posted, as Metra counts it: invoices less credit notes and
payments, plus reminder fees.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass

from django.conf import settings as django_settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from apps.plugins import api

from .models import ZERO, FiscalYear, Posting, PostingSettings, VatCode, Voucher, VoucherLine

logger = logging.getLogger(__name__)

INVOICES = (Posting.Source.INVOICE, Posting.Source.CREDIT_NOTE)


@dataclass
class Entry:
    account: object
    amount: object  # debit positive, credit negative
    description: str = ""
    vat_code: str = ""
    vat_rate: object = None


@dataclass
class Record:
    """Something from invoicing to book: its kind, the invoice, the payment or
    reminder (if any) and its date."""

    source: str
    invoice: object
    payment: object = None
    reminder: object = None

    @property
    def date(self):
        if self.payment is not None:
            return self.payment.paid_on
        if self.reminder is not None:
            return timezone.localdate(self.reminder.created_at)
        return self.invoice.issue_date

    @property
    def user(self):
        if self.payment is not None:
            return self.payment.recorded_by
        if self.reminder is not None:
            return self.reminder.sent_by
        return self.invoice.issued_by

    @property
    def order(self):
        """Invoices before reminders before payments on the same day."""
        return {"invoice": 0, "credit_note": 0, "reminder": 1, "payment": 2}[self.source]

    def booked(self):
        postings = Posting.objects.all()
        if self.payment is not None:
            return postings.filter(payment=self.payment).exists()
        if self.reminder is not None:
            return postings.filter(reminder=self.reminder).exists()
        return postings.filter(invoice=self.invoice, source__in=INVOICES).exists()


def for_invoice(invoice):
    is_note = invoice.kind == api.Invoice.Kind.CREDIT_NOTE
    return Record(Posting.Source.CREDIT_NOTE if is_note else Posting.Source.INVOICE, invoice)


def for_payment(payment):
    return Record(Posting.Source.PAYMENT, payment.invoice, payment=payment)


def for_reminder(reminder):
    return Record(Posting.Source.REMINDER, reminder.invoice, reminder=reminder)


# What each record books


def _invoice_entries(record, settings):
    invoice = record.invoice
    registered = invoice.vat_registered
    sales = defaultdict(lambda: ZERO)
    texts = defaultdict(list)
    for line in invoice.lines.all():
        rate = line.vat_rate if registered else None
        account = settings.sales_account(line.fee_line_id, line.vat_rate)
        sales[(account, rate)] += line.net
        if line.description not in texts[(account, rate)]:
            texts[(account, rate)].append(line.description)
    entries = [Entry(settings.receivables, invoice.total, invoice.number)]
    for (account, rate), net in sales.items():
        code = VatCode.SALES if rate is not None else ""
        description = "; ".join(texts[(account, rate)])[:200]
        entries.append(Entry(account, -net, description, code, rate))
    if registered:
        for rate, _base, vat in invoice.vat_breakdown():
            entries.append(Entry(settings.sales_vat, -vat, "", VatCode.SALES, rate))
    return entries


def _payment_entries(record, settings):
    amount = record.payment.amount
    number = record.invoice.number
    return [Entry(settings.bank, amount, number), Entry(settings.receivables, -amount, number)]


def _reminder_entries(record, settings):
    fee = record.reminder.fee
    number = record.invoice.number
    return [Entry(settings.receivables, fee, number), Entry(settings.reminder_fees, -fee, number)]


ENTRIES = {
    Posting.Source.INVOICE: _invoice_entries,
    Posting.Source.CREDIT_NOTE: _invoice_entries,
    Posting.Source.PAYMENT: _payment_entries,
    Posting.Source.REMINDER: _reminder_entries,
}


def _description(record):
    invoice = record.invoice
    values = {"number": invoice.number, "unit": invoice.buyer.get("unit", "")}
    if record.source == Posting.Source.CREDIT_NOTE:
        values["credited"] = invoice.credits.number if invoice.credits_id else ""
        text = _("Credit note %(number)s for invoice %(credited)s, %(unit)s")
    elif record.source == Posting.Source.PAYMENT:
        text = _("Payment of invoice %(number)s, %(unit)s")
    elif record.source == Posting.Source.REMINDER:
        text = _("Reminder fee for invoice %(number)s, %(unit)s")
    else:
        text = _("Invoice %(number)s, %(unit)s")
    return (text % values)[:200]


# Booking


def book(record, settings=None, user=None):
    """Make, and post, the voucher for ``record``. Returns the voucher, or
    None when there is nothing to book: postings are off for its date, it is
    booked already, it is for nothing, or no open year covers its date."""
    settings = settings or PostingSettings.current()
    date = record.date
    if not settings.applies(date):
        return None
    year = FiscalYear.for_date(date)
    if year is None or not year.is_open or record.booked():
        return None
    entries = [entry for entry in ENTRIES[record.source](record, settings) if entry.amount]
    if not entries:
        return None
    series = settings.payment_series if record.source == "payment" else settings.invoice_series
    user = user or record.user
    # The books are kept in the organisation's language, whoever's request
    # made the record.
    with translation.override(django_settings.LANGUAGE_CODE):
        description = _description(record)
    try:
        with transaction.atomic():
            voucher = Voucher.objects.create(
                year=year, series=series, date=date, description=description, created_by=user
            )
            VoucherLine.objects.bulk_create(
                [
                    VoucherLine(
                        voucher=voucher,
                        account=entry.account,
                        debit=max(entry.amount, ZERO),
                        credit=max(-entry.amount, ZERO),
                        description=entry.description,
                        vat_code=entry.vat_code,
                        vat_rate=entry.vat_rate,
                        order=order,
                    )
                    for order, entry in enumerate(entries, start=1)
                ]
            )
            Posting.objects.create(
                voucher=voucher,
                source=record.source,
                invoice=record.invoice,
                payment=record.payment,
                reminder=record.reminder,
            )
    except IntegrityError:
        # Booked meanwhile by another request or worker.
        return None
    try:
        voucher.post(user)
    except ValidationError as error:
        logger.warning("Voucher %s from %s left as a draft: %s", voucher.pk, record, error)
    return voucher


def waiting(settings=None, invoice=None):
    """Records dated on or after the start of postings that have no voucher,
    oldest first; only those of ``invoice`` when given."""
    settings = settings or PostingSettings.current()
    if not settings.is_on:
        return []
    start = settings.start
    postings = Posting.objects.all()
    invoices = (
        api.Invoice.objects.issued()
        .filter(issue_date__gte=start)
        .exclude(total=ZERO)
        .exclude(pk__in=postings.filter(source__in=INVOICES).values("invoice_id"))
    )
    payments = (
        api.Payment.objects.filter(paid_on__gte=start)
        .exclude(pk__in=postings.exclude(payment=None).values("payment_id"))
        .select_related("invoice")
    )
    reminders = (
        api.PaymentReminder.objects.filter(fee__gt=ZERO, created_at__date__gte=start)
        .exclude(pk__in=postings.exclude(reminder=None).values("reminder_id"))
        .select_related("invoice")
    )
    if invoice is not None:
        invoices = invoices.filter(pk=invoice.pk)
        payments = payments.filter(invoice=invoice)
        reminders = reminders.filter(invoice=invoice)
    records = [
        *(for_invoice(invoice) for invoice in invoices),
        *(for_payment(payment) for payment in payments),
        *(for_reminder(reminder) for reminder in reminders),
    ]
    return sorted(records, key=lambda record: (record.date, record.order))


def book_waiting(user=None):
    """Book what is waiting. Returns (vouchers made, records left waiting)."""
    settings = PostingSettings.current()
    made = []
    for record in waiting(settings):
        voucher = book(record, settings, user=user)
        if voucher is not None:
            made.append(voucher)
    return made, len(waiting(settings))


def invoice_panel(request, invoice):
    """The vouchers of an invoice and its payments and reminders, for the
    invoice page."""
    postings = Posting.objects.filter(invoice=invoice).select_related(
        "voucher__series", "payment", "reminder"
    )
    return {"postings": postings, "waiting": waiting(invoice=invoice)}


# Receivers: book each record as Metra makes it.


def _safely(record):
    try:
        book(record)
    except Exception:
        # Never let the books break invoicing; the record stays waiting.
        logger.exception("Could not book %s", record)


def on_invoice_issued(sender, invoice, **kwargs):
    _safely(for_invoice(invoice))


def on_payment_recorded(sender, payment, **kwargs):
    _safely(for_payment(payment))


def on_reminder_sent(sender, reminder, **kwargs):
    _safely(for_reminder(reminder))


def connect():
    api.events.invoice_issued.connect(on_invoice_issued, dispatch_uid="bookkeeping.invoice")
    api.events.payment_recorded.connect(on_payment_recorded, dispatch_uid="bookkeeping.payment")
    api.events.reminder_sent.connect(on_reminder_sent, dispatch_uid="bookkeeping.reminder")
