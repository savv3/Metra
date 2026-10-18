from decimal import Decimal

from django import template
from django.utils.formats import number_format

register = template.Library()


@register.filter
def price(value):
    """A unit price with 2 to 4 decimals: 120,00 and 1,50 but 0,0125."""
    if value in (None, ""):
        return ""
    value = Decimal(value)
    decimals = max(2, -value.normalize().as_tuple().exponent)
    return number_format(value, decimal_pos=min(decimals, 4))


@register.filter
def quantity(value):
    """A quantity without trailing zeros: 1, 65, 12,5."""
    if value in (None, ""):
        return ""
    value = Decimal(value).normalize()
    decimals = max(0, -value.as_tuple().exponent)
    return number_format(value, decimal_pos=decimals)
