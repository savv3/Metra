"""Euro amounts: always Decimal, rounded half up to whole cents."""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def cents(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def vat_of(base, rate):
    """VAT on a base at a rate given in percent (25.5 for 25.5 %)."""
    return cents(Decimal(base) * Decimal(rate) / 100)
