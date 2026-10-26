"""What differs between countries: chart of accounts templates, the length a
financial year may have, and (in later versions) statement formats,
retention periods and export formats. The ledger itself is the same
everywhere; a new country is a new module here.

A country module has:

    CODE = "fi"
    NAME = gettext_lazy("Finland")
    CHARTS = {"association": Chart(...), ...}
    FIRST_YEAR_MONTHS = (1, 18)   # how long a first or changed year may be
    VAT_RATES = [VatRate(...), ...]  # the rates in force, with their dates
    POSTING_ACCOUNTS = {...}  # account numbers postings from invoicing use
"""

import datetime
from dataclasses import dataclass, field
from decimal import Decimal
from importlib import import_module

from django.conf import settings
from django.utils.translation import get_language

COUNTRIES = ("fi",)
DEFAULT = "fi"


@dataclass(frozen=True)
class Account:
    """An account in a chart template, with its name in each language."""

    number: str
    kind: str
    names: dict

    def name(self, language=None):
        language = (language or get_language() or settings.LANGUAGE_CODE)[:2]
        return self.names.get(language) or self.names["en"]


@dataclass(frozen=True)
class Chart:
    """A ready chart of accounts that a new set of books starts from."""

    name: object
    description: object
    accounts: list = field(default_factory=list)
    # Income statement sections by account number range: (first, last, key).
    # The statements (a later version) are built from these, so an account
    # added by the treasurer lands in the section its number falls in.
    sections: list = field(default_factory=list)

    def section(self, number):
        for first, last, key in self.sections:
            if len(number) == len(first) and first <= number <= last:
                return key
        return None


@dataclass(frozen=True)
class VatRate:
    """A VAT rate (in per cent) and the days it applies, both inclusive;
    None for no limit. When a rate changes, the old one gets a last day and
    the new one is added, so entries keep the rate of their own date."""

    rate: Decimal
    first: datetime.date | None = None
    last: datetime.date | None = None

    def applies(self, date):
        return (self.first is None or self.first <= date) and (
            self.last is None or date <= self.last
        )


def get(code=None):
    code = code or DEFAULT
    if code not in COUNTRIES:
        raise LookupError(f"No bookkeeping rules for country {code!r}.")
    return import_module(f"{__name__}.{code}")


def chart_choices(code=None):
    return [(key, chart.name) for key, chart in get(code).CHARTS.items()]


def vat_rate_applies(rate, date, code=None):
    """Whether ``rate`` is a VAT rate in force on ``date``."""
    return any(r.rate == rate and r.applies(date) for r in get(code).VAT_RATES)


def vat_rates(code=None, since=None):
    """The rates in force on or after ``since`` (all of them by default),
    highest first, without repeats."""
    rates = {
        r.rate for r in get(code).VAT_RATES if since is None or r.last is None or r.last >= since
    }
    return sorted(rates, reverse=True)
