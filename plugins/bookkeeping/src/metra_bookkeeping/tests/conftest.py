import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.utils import timezone, translation

from apps.plugins import api
from metra_bookkeeping import countries
from metra_bookkeeping.models import (
    Account,
    FiscalYear,
    PostingSettings,
    VatRegistration,
    Voucher,
    VoucherLine,
    VoucherSeries,
)

TODAY = timezone.localdate()
D = datetime.date


@pytest.fixture(autouse=True)
def in_english():
    """Messages are checked in English (the test settings default to Swedish)."""
    with translation.override("en"):
        yield


@pytest.fixture
def login(make_user, settings):
    """A logged-in client for a new user with a role, seeing English pages."""

    def make(username, role=None):
        client = Client()
        client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        user = make_user(username, role)
        client.force_login(user)
        client.user = user
        return client

    return make


@pytest.fixture
def treasurer(login):
    return login("treasurer", "Treasurer")


@pytest.fixture
def year(db):
    return FiscalYear.objects.create(
        start=datetime.date(2026, 1, 1), end=datetime.date(2026, 12, 31)
    )


@pytest.fixture
def chart(db):
    Account.create_chart(countries.get("fi").CHARTS["association"], "en")
    return {account.number: account for account in Account.objects.all()}


@pytest.fixture
def series(db):
    return VoucherSeries.default()


@pytest.fixture
def make_voucher(year, chart, series):
    """A draft voucher with (account number, debit, credit) lines."""

    def make(lines, date=datetime.date(2026, 3, 1), description="Electricity", **extra):
        voucher = Voucher.objects.create(
            year=FiscalYear.for_date(date) or year,
            series=extra.pop("series", series),
            date=date,
            description=description,
            **extra,
        )
        for order, (number, debit, credit) in enumerate(lines, start=1):
            VoucherLine.objects.create(
                voucher=voucher,
                account=chart[number],
                debit=Decimal(debit),
                credit=Decimal(credit),
                order=order,
            )
        return voucher

    return make


# Postings from invoicing


@pytest.fixture
def this_year(db):
    return FiscalYear.objects.create(start=D(TODAY.year, 1, 1), end=D(TODAY.year, 12, 31))


@pytest.fixture
def books(this_year, chart):
    """Books for this year, posting invoices from its first day."""
    settings = PostingSettings.current()
    settings.start = this_year.start
    settings.invoice_series = VoucherSeries.objects.create(code="L", name="Sales invoices")
    settings.payment_series = VoucherSeries.objects.create(code="S", name="Payments")
    settings.save()
    assert settings.is_on
    return settings


@pytest.fixture
def seller(db):
    api.Organisation.objects.create(
        name="Västerby vattenandelslag",
        business_id="1234567-8",
        vat_number="FI12345678",
        street_address="Bystigen 2",
        postal_code="22240",
        city="Hammarland",
    )
    billing = api.BillingSettings.current()
    billing.iban = "FI21 1234 5600 0007 85"
    billing.save()
    return billing


@pytest.fixture
def vat_registered(seller, this_year):
    seller.vat_registered = True
    seller.save()
    VatRegistration.objects.create(start=D(2020, 1, 1))
    return seller


@pytest.fixture
def make_invoice(seller, unit, person, django_capture_on_commit_callbacks):
    """Issue an invoice with (description, quantity, price, VAT rate) lines,
    running the add-on's receivers as after a real commit."""
    person.street_address = "Byvägen 4"
    person.save()

    def make(lines, kind="invoice", credits=None, fee_line=None):
        invoice = api.Invoice.objects.create(unit=unit, person=person, kind=kind, credits=credits)
        for order, (text, quantity, price, rate) in enumerate(lines):
            api.InvoiceLine.objects.create(
                invoice=invoice,
                description=text,
                quantity=Decimal(quantity),
                unit_price=Decimal(price),
                vat_rate=Decimal(rate),
                fee_line=fee_line if order == 0 else None,
                order=order,
            )
        with django_capture_on_commit_callbacks(execute=True):
            invoice.issue()
        return invoice

    return make


@pytest.fixture
def pay(django_capture_on_commit_callbacks):
    from apps.invoicing.payments import record_payment

    def pay(invoice, amount, paid_on=TODAY):
        with django_capture_on_commit_callbacks(execute=True):
            return record_payment(invoice, Decimal(amount), paid_on)

    return pay


@pytest.fixture
def remind(django_capture_on_commit_callbacks):
    def remind(invoice, fee):
        with django_capture_on_commit_callbacks(execute=True):
            reminder = api.PaymentReminder.objects.create(
                invoice=invoice, fee=Decimal(fee), new_due_date=TODAY, channel="letter"
            )
            api.events.send_on_commit(api.events.reminder_sent, None, reminder=reminder)
        return reminder

    return remind
