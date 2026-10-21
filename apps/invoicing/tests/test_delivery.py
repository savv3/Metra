import pytest
from django.core import mail
from django.urls import reverse

from apps.invoicing.delivery import channel_for, send_invoices
from apps.invoicing.models import BillingSettings, Invoice, InvoiceDelivery, InvoiceRun
from apps.invoicing.pdf import PDFUnavailable, invoice_html, payment_qr, render_pdf
from apps.invoicing.runs import build_run
from apps.messaging.models import MessageBatch


def weasyprint_or_skip():
    try:
        render_pdf([])
    except PDFUnavailable:
        pytest.skip("WeasyPrint's Pango library is not installed here")


@pytest.fixture
def issued(plan, rounds, make_household, billing):
    """Two issued invoices: Anna has email, Bo prefers post."""
    last, current = rounds
    make_household(
        "Bystigen 4",
        [(last, "300"), (current, "342")],
        first_name="Anna",
        email="anna@example.com",
    )
    make_household(
        "Bystigen 6",
        [(last, "100"), (current, "120")],
        first_name="Bo",
        preferred_channel="post",
    )
    run = InvoiceRun.objects.create(period_label="2026")
    run.plans.add(plan)
    run.rounds.add(current)
    build_run(run)
    for invoice in run.invoices.order_by("unit__name"):
        invoice.issue()
    return run


def test_issued_invoices_get_a_reference(issued):
    first, second = issued.invoices.order_by("sequence")

    assert (first.reference, second.reference) == ("100010", "100023")
    assert first.reference_display == "1 00010"
    assert first.barcode.startswith("42112345600000785")


def test_rf_references_when_chosen(plan, rounds, make_household, billing):
    billing.reference_type = BillingSettings.ReferenceType.RF
    billing.save()
    last, current = rounds
    make_household("A", [(last, "1"), (current, "2")], first_name="A")
    run = InvoiceRun.objects.create(period_label="2026")
    run.plans.add(plan)
    run.rounds.add(current)
    build_run(run)

    invoice = run.invoices.get()
    invoice.issue()

    assert invoice.reference.startswith("RF") and invoice.reference.endswith("100010")
    assert invoice.barcode.startswith("5")


def test_invoice_html_has_the_required_details(issued, organisation):
    invoice = issued.invoices.get(unit__name="Bystigen 4")

    html = invoice_html([invoice])

    for text in [
        "Västerby vattenandelslag",
        "1234567-8",
        "Bystigen 2",
        "Anna",
        "Bystigen 4",
        invoice.number,
        "1 00010",
        "FI21 1234 5600 0007 85",
        "Grundavgift 2026",
        "Ej momsskyldig",
        invoice.barcode,
        "data:image/svg+xml;base64",
    ]:
        assert text in html, text
    assert payment_qr(invoice).startswith("data:image/svg+xml")


def test_credit_notes_have_no_payment_block(issued):
    invoice = issued.invoices.first()
    note = invoice.make_credit_note()
    note.issue()

    html = invoice_html([note])

    assert note.reference == ""
    assert "FI21 1234 5600 0007 85" not in html
    assert invoice.number in html


def test_pdf_renders(issued):
    weasyprint_or_skip()

    pdf = render_pdf(list(issued.invoices.all()))

    assert pdf.startswith(b"%PDF")


def test_sending_emails_the_pdf_and_lists_post(issued):
    weasyprint_or_skip()
    batch = MessageBatch.objects.create(kind=MessageBatch.Kind.INVOICES)

    send_invoices(batch, issued.invoices.order_by("sequence"))

    assert [m.to for m in mail.outbox] == [["anna@example.com"]]
    email = mail.outbox[0]
    number = issued.invoices.get(unit__name="Bystigen 4").number
    assert email.subject == f"Faktura {number} från Västerby vattenandelslag"
    assert "1 00010" in email.body
    filename, content, mimetype = email.attachments[0]
    assert (filename, mimetype) == (f"invoice-{number}.pdf", "application/pdf")
    assert content.startswith(b"%PDF")
    channels = dict(InvoiceDelivery.objects.values_list("invoice__unit__name", "channel"))
    assert channels == {"Bystigen 4": "email", "Bystigen 6": "letter"}
    assert batch.messages.get(channel="letter").status == "to_print"
    send_invoices(batch, issued.invoices.all())  # sent once only
    assert len(mail.outbox) == 1


def test_email_failure_is_recorded_and_can_be_retried(issued, monkeypatch):
    from apps.invoicing import delivery

    def broken(invoices, **kwargs):
        raise PDFUnavailable("no Pango")

    monkeypatch.setattr(delivery, "render_pdf", broken)
    batch = MessageBatch.objects.create(kind=MessageBatch.Kind.INVOICES)

    send_invoices(batch, issued.invoices.filter(unit__name="Bystigen 4"))

    message = batch.messages.get()
    assert (message.status, message.error) == ("failed", "no Pango")
    assert not InvoiceDelivery.objects.exists()


def test_post_goes_by_letter(issued, settings):
    anna = issued.invoices.get(unit__name="Bystigen 4")
    assert channel_for(anna) == "email"
    settings.MESSAGING = {**settings.MESSAGING, "email_provider": ""}
    assert channel_for(anna) == "letter"


def test_staff_send_and_print(treasurer_client, issued):
    weasyprint_or_skip()

    response = treasurer_client.post(reverse("invoicing:run_send", args=[issued.pk]))
    batch = MessageBatch.objects.get(kind="invoices")
    page = treasurer_client.get(batch.get_absolute_url(), HTTP_ACCEPT_LANGUAGE="en")
    letters = treasurer_client.get(reverse("invoicing:batch_print", args=[batch.pk]))
    one = treasurer_client.get(reverse("invoicing:invoice_pdf", args=[issued.invoices.first().pk]))
    post = treasurer_client.get(reverse("invoicing:run_print", args=[issued.pk]))

    assert response.url == batch.get_absolute_url()
    assert "1 invoice goes by post" in page.content.decode()
    for pdf in (letters, one, post):
        assert pdf["Content-Type"] == "application/pdf"
        assert pdf.content.startswith(b"%PDF")


def test_board_can_download_but_not_send(role_client, issued):
    board = role_client("Board")

    assert board.post(reverse("invoicing:run_send", args=[issued.pk])).status_code == 403


def test_members_see_and_download_their_invoices(client, issued):
    weasyprint_or_skip()
    from apps.selfservice.models import SelfServiceLink

    invoice = issued.invoices.get(unit__name="Bystigen 4")
    other = issued.invoices.get(unit__name="Bystigen 6")
    _link, token = SelfServiceLink.create_for(invoice.unit, invoice.person)

    page = client.get(f"/m/{token}/", HTTP_ACCEPT_LANGUAGE="en").content.decode()
    pdf = client.get(f"/m/{token}/invoices/{invoice.pk}/")
    not_theirs = client.get(f"/m/{token}/invoices/{other.pk}/")

    assert "Your invoices" in page and invoice.number in page
    assert pdf["Content-Type"] == "application/pdf"
    assert pdf["X-Robots-Tag"] == "noindex, nofollow"
    assert not_theirs.status_code == 404


def test_drafts_are_not_shown_to_members(client, plan, rounds, make_household, billing):
    from apps.selfservice.models import SelfServiceLink

    last, current = rounds
    unit = make_household("A", [(last, "1"), (current, "2")], first_name="A")
    run = InvoiceRun.objects.create(period_label="2026")
    run.plans.add(plan)
    run.rounds.add(current)
    build_run(run)
    draft = Invoice.objects.get()
    _link, token = SelfServiceLink.create_for(unit, draft.person)

    assert (
        "Your invoices"
        not in client.get(f"/m/{token}/", HTTP_ACCEPT_LANGUAGE="en").content.decode()
    )
    assert client.get(f"/m/{token}/invoices/{draft.pk}/").status_code == 404
    assert '<div class="preview">' in invoice_html([draft])  # the DRAFT watermark


def test_invoices_go_by_email_even_to_those_who_prefer_sms(issued):
    # Invoices have no SMS; email is the fallback for those who prefer SMS.
    anna = issued.invoices.get(unit__name="Bystigen 4")
    anna.person.preferred_channel = "sms"
    assert channel_for(anna) == "email"
    anna.person.preferred_channel = "post"
    assert channel_for(anna) == "letter"
