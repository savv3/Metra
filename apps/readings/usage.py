"""Usage from readings, and warnings for values that look wrong.

Warnings never block saving: a meter can be replaced or a household can
fill a pool. They point staff at values worth a second look.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from django.utils.formats import number_format
from django.utils.translation import gettext as _

from .models import Reading

# A usage more than this many times the unit's usual usage gets a warning.
HIGH_USAGE_FACTOR = 3
# How many earlier usages make up "usual".
USUAL_FROM = 3


@dataclass
class Assessment:
    previous: Decimal | None = None
    usage: Decimal | None = None
    warnings: list = field(default_factory=list)


def earlier_values(round_, unit_ids):
    """{unit_id: [values of earlier rounds, newest first]} for the round's reading type."""
    rounds = list(round_.earlier_rounds().values_list("pk", flat=True))
    order = {pk: index for index, pk in enumerate(rounds)}
    values = {}
    readings = Reading.objects.filter(round_id__in=rounds, unit_id__in=unit_ids).values_list(
        "unit_id", "round_id", "value"
    )
    for unit_id, _round_id, value in sorted(readings, key=lambda r: order[r[1]]):
        values.setdefault(unit_id, []).append(value)
    return values


def assess(reading_type, value, earlier):
    """Usage of ``value`` given the unit's earlier values (newest first), with warnings."""
    result = Assessment()
    if value is None:
        if earlier:
            result.previous = earlier[0]
        return result
    if reading_type.cumulative:
        if not earlier:
            return result
        result.previous = earlier[0]
        result.usage = value - earlier[0]
        if result.usage < 0:
            result.warnings.append(
                _("Lower than the previous reading (%(previous)s). Was the meter replaced?")
                % {"previous": _format(reading_type, earlier[0])}
            )
            return result
        history = [newer - older for newer, older in zip(earlier, earlier[1:], strict=False)]
    else:
        result.usage = value
        history = list(earlier)
    usual = [usage for usage in history[:USUAL_FROM] if usage >= 0]
    if usual:
        average = sum(usual) / len(usual)
        if average > 0 and result.usage > average * HIGH_USAGE_FACTOR:
            result.warnings.append(
                _("Much higher than usual (about %(usual)s %(unit)s).")
                % {"usual": _format(reading_type, average), "unit": reading_type.unit_label}
            )
    return result


def _format(reading_type, value):
    return number_format(value, decimal_pos=reading_type.decimals)
