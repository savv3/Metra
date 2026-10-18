from django import template
from django.utils.formats import number_format

from ..models import Reading, ReadingRound
from ..usage import assess

register = template.Library()

UNIT_ROUNDS_SHOWN = 10


@register.filter
def reading_value(value, reading_type, unit=True):
    """A value with the reading type's decimals and, unless unit=False, its unit label."""
    if value is None or value == "":
        return ""
    text = number_format(value, decimal_pos=reading_type.decimals)
    if unit and reading_type.unit_label:
        return f"{text} {reading_type.unit_label}"
    return text


@register.filter
def reading_number(value, reading_type):
    """The value alone, e.g. to fill in a form field."""
    return reading_value(value, reading_type, unit=False)


@register.inclusion_tag("readings/_unit_readings.html", takes_context=True)
def unit_readings(context, unit):
    """The unit's readings in recent rounds, for the unit page."""
    user = context["request"].user
    if not user.has_perm("readings.view_reading"):
        return {"show": False}
    rounds = list(
        ReadingRound.objects.filter(reading_type__unit_type_id=unit.unit_type_id)
        .select_related("reading_type")
        .order_by("-opens_on", "-pk")
    )
    if not rounds:
        return {"show": False}
    readings = {r.round_id: r for r in Reading.objects.filter(unit=unit, round__in=rounds)}
    rows = []
    # Oldest first, so each reading can be compared with the ones before it.
    earlier_by_type = {}
    for round_ in reversed(rounds):
        reading = readings.get(round_.pk)
        earlier = earlier_by_type.setdefault(round_.reading_type_id, [])
        rows.append(
            {
                "round": round_,
                "reading": reading,
                "assessment": assess(
                    round_.reading_type, reading.value if reading else None, list(earlier)
                ),
            }
        )
        if reading:
            earlier.insert(0, reading.value)
    rows.reverse()
    return {
        "show": True,
        "unit": unit,
        "rows": rows[:UNIT_ROUNDS_SHOWN],
        "can_enter": user.has_perms(["readings.add_reading", "readings.change_reading"]),
    }
