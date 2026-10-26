from decimal import Decimal

from django import template
from django.utils.formats import number_format

register = template.Library()


@register.filter
def money(value):
    """An amount with cents and thousands grouped: 1 234,50."""
    if value in (None, ""):
        return ""
    return number_format(Decimal(value), decimal_pos=2, force_grouping=True)


@register.filter
def money_or_blank(value):
    """Like ``money``, but a zero is left empty (a debit or credit column)."""
    if not value:
        return ""
    return money(value)


@register.filter
def vat_label(rate, code):
    """ "Sales 25.5 %" for a rate and a VAT code (sales or purchases)."""
    from ..models import vat_label as label

    return label(code, Decimal(rate))
