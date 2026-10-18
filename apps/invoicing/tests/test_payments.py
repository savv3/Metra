import csv
import datetime
import io
from decimal import Decimal as D

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.invoicing.models import Invoice, InvoiceRun, LockedError, Payment, PaymentReminder
from apps.invoicing.payments import record_payment, send_reminders
from apps.invoicing.runs import build_run
from apps.messaging import providers
from apps.messaging.models import MessageBatch

TODAY = timezone.localdate()


@pytest.fixture
def invoices(plan, rounds, make_household, billing):
    """Issued 2026 invoices of 183 € each (120 + 42 m³ × 1.50), all overdue."""
    last, current = rounds
    people = {
        "Bystigen 4": {"first_name": "Anna", "email": "anna@example.com"},
        "Bystigen 6": {"first_name": "Bo", "phone": "0401234567"},
        "Bystigen 8": {"first_name": "Cia", "preferred_channel": "post"},
    }
    for name, person in people.items():
        make_household(name, [(last, "300"), (current, "342")], **person)
    run = InvoiceRun.objects.create(period_label="2026")
    run.plans.add(plan)
    run.rounds.add(current)
    build_run(run)
    for invoice in run.invoices.order_by("unit__name"):
        invoice.issue()
    Invoice.objects.update(due_date=TODAY - datetime.timedelta(days=20))
    providers.outbox.clear()
    return {i.unit.name: i for i in Invoice.objects.all()}


def test_partial_then_full_payment(invoices):
    invoice = invoices["Bystigen 4"]

    record_payment(invoice, D("100"), TODAY)
    assert invoice.outstanding() == D("83.00")
    assert invoice.status == "issued" and invoice.is_overdue

    record_payment(invoice, D("83"), TODAY, reference=invoice.reference)
    invoice.refresh_from_db()
    assert invoice.outstanding() == 0
    assert invoice.status == "paid"
    assert not invoice.is_overdue
    assert invoice not in Invoice.objects.overdue()


def test_payments_are_locked_and_reversed_with_a_negative_one(invoices):
    invoice = invoices["Bystigen 4"]
    payment = record_payment(invoice, D("183"), TODAY)
    invoice.refresh_from_db()
    assert invoice.status == "paid"

    payment.amount = D("1")
    with pytest.raises(LockedError):
        payment.save()
    with pytest.raises(LockedError):
        payment.delete()

    record_payment(invoice, D("-183"), TODAY, note="Fel faktura")
    invoice.refresh_from_db()
    assert invoice.status == "issued"
    assert invoice.outstanding() == D("183.00")


def test_no_payments_on_drafts_or_credit_notes(invoices, plan, make_household):
    from django.core.exceptions import ValidationError

    note = invoices["Bystigen 4"].make_credit_note()
    with pytest.raises(ValidationError):
        record_payment(note, D("10"), TODAY)
    with pytest.raises(ValidationError):
        record_payment(invoices["Bystigen 4"], D("0"), TODAY)


def test_credit_note_and_payment_together_settle_an_invoice(invoices):
    invoice = invoices["Bystigen 4"]
    record_payment(invoice, D("120"), TODAY)
    note = invoice.make_credit_note()
    note.lines.filter(description__startswith="Grundavgift").delete()
    note.compute_totals()
    note.save()
    note.issue()

    invoice.refresh_from_db()
    assert invoice.outstanding() == 0
    assert invoice.status == "paid"


def test_reminders_go_by_email_sms_or_letter_with_fee(invoices):
    batch = MessageBatch.objects.create(kind=MessageBatch.Kind.PAYMENT_REMINDERS)

    send_reminders(batch, Invoice.objects.order_by("sequence"))

    channels = dict(PaymentReminder.objects.values_list("invoice__unit__name", "channel"))
    assert channels == {"Bystigen 4": "email", "Bystigen 6": "sms", "Bystigen 8": "letter"}
    reminder = PaymentReminder.objects.get(invoice=invoices["Bystigen 4"])
    assert reminder.fee == D("5.00")
    assert reminder.new_due_date == TODAY + datetime.timedelta(days=14)
    invoice = invoices["Bystigen 4"]
    assert invoice.outstanding() == D("188.00")
    assert not invoice.is_overdue  # the new due date is in the future
    sms = providers.outbox[0]["body"]
    assert "188,00 €" in sms and invoices["Bystigen 6"].reference_display in sms
    assert mail.outbox[0].subject == f"Betalningspåminnelse: faktura {invoice.number}"
    assert batch.messages.get(channel="letter").status == "to_print"


def test_paid_invoices_get_no_reminder(invoices):
    record_payment(invoices["Bystigen 4"], D("183"), TODAY)
    batch = MessageBatch.objects.create(kind=MessageBatch.Kind.PAYMENT_REMINDERS)

    send_reminders(batch, Invoice.objects.all())

    assert not PaymentReminder.objects.filter(invoice=invoices["Bystigen 4"]).exists()
    assert PaymentReminder.objects.count() == 2


def test_reminder_fee_can_be_off(invoices, billing):
    billing.reminder_fee = D("0")
    billing.save()
    batch = MessageBatch.objects.create(kind=MessageBatch.Kind.PAYMENT_REMINDERS)

    send_reminders(batch, Invoice.objects.filter(unit__name="Bystigen 6"))

    assert PaymentReminder.objects.get().fee == 0
    assert invoices["Bystigen 6"].outstanding() == D("183.00")


def test_reminder_pdf_shows_the_new_amount_and_due_date(invoices):
    from apps.invoicing.pdf import invoice_html
    from apps.invoicing.reference import virtual_barcode

    invoice = invoices["Bystigen 4"]
    record_payment(invoice, D("100"), TODAY)
    reminder = PaymentReminder.objects.create(
        invoice=invoice,
        fee=D("5"),
        new_due_date=TODAY + datetime.timedelta(days=14),
        channel="letter",
    )

    html = invoice_html([invoice], reminders={invoice.pk: reminder})

    assert "PAYMENT REMINDER" in html
    assert "88.00 €" in html or "88,00 €" in html
    expected = virtual_barcode(
        invoice.seller["iban"], D("88"), invoice.reference, reminder.new_due_date
    )
    assert expected in html


def test_overdue_page_and_sending_reminders(treasurer_client, invoices):
    page = treasurer_client.get(reverse("invoicing:overdue_list"), HTTP_ACCEPT_LANGUAGE="en")
    response = treasurer_client.post(
        reverse("invoicing:send_reminders"), {"invoices": [invoices["Bystigen 6"].pk]}
    )

    assert len(page.context["invoices"]) == 3
    assert page.context["invoices"][0].to_pay == D("183.00")
    batch = MessageBatch.objects.get(kind="payment_reminders")
    assert response.url == batch.get_absolute_url()
    assert PaymentReminder.objects.get().invoice == invoices["Bystigen 6"]


def test_record_payment_from_the_invoice_page(treasurer_client, invoices):
    invoice = invoices["Bystigen 4"]
    page = treasurer_client.get(invoice.get_absolute_url())

    assert page.context["payment_form"].initial["amount"] == D("183.00")
    treasurer_client.post(
        reverse("invoicing:invoice_pay", args=[invoice.pk]),
        {"amount": "183,00", "paid_on": TODAY.isoformat(), "reference": invoice.reference},
    )
    invoice.refresh_from_db()
    assert invoice.status == "paid"
    assert Payment.objects.get().recorded_by.username == "treasurer"


def test_board_sees_but_cannot_record_or_remind(role_client, invoices):
    board = role_client("Board")
    invoice = invoices["Bystigen 4"]

    assert board.get(reverse("invoicing:overdue_list")).status_code == 200
    pay = board.post(reverse("invoicing:invoice_pay", args=[invoice.pk]), {"amount": "1"})
    remind = board.post(reverse("invoicing:send_reminders"), {"invoices": [invoice.pk]})
    assert (pay.status_code, remind.status_code) == (403, 403)


def read_csv(response):
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig")), delimiter=";"))


def test_invoice_export_for_bookkeeping(treasurer_client, invoices):
    record_payment(invoices["Bystigen 4"], D("183"), TODAY)

    rows = read_csv(
        treasurer_client.get(reverse("invoicing:export_invoices"), HTTP_ACCEPT_LANGUAGE="en")
    )

    assert rows[0][:3] == ["Number", "Kind", "Invoice date"]
    by_unit = {row[5]: row for row in rows[1:]}
    assert by_unit["Bystigen 4"][9:14] == ["183,00", "0,00", "183,00", "0,00", "0,00"]
    assert by_unit["Bystigen 6"][13] == "183,00"


def test_payments_export_with_dates_and_fees(treasurer_client, invoices):
    record_payment(invoices["Bystigen 4"], D("183"), TODAY - datetime.timedelta(days=40))
    record_payment(invoices["Bystigen 6"], D("50"), TODAY)
    PaymentReminder.objects.create(
        invoice=invoices["Bystigen 8"], fee=D("5"), new_due_date=TODAY, channel="letter"
    )

    form = treasurer_client.get(reverse("invoicing:export_payments"))
    rows = read_csv(
        treasurer_client.get(
            reverse("invoicing:export_payments"),
            {"start": (TODAY - datetime.timedelta(days=7)).isoformat(), "go": "1"},
            HTTP_ACCEPT_LANGUAGE="en",
        )
    )

    assert form.templates[0].name == "invoicing/export_payments.html"
    assert [row[1] for row in rows[1:]] == ["Payment", "Reminder fee"]
    assert rows[1][4] == "50,00"
