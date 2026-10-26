import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.utils import translation

from metra_bookkeeping import countries
from metra_bookkeeping.models import Account, FiscalYear, Voucher, VoucherLine, VoucherSeries


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
