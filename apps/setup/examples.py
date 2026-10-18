"""Ready-made setups an admin can start from. Names are created in the
admin's current language and can be changed afterwards."""

from django.db import transaction
from django.utils.translation import gettext as _

from apps.readings.models import ReadingType
from apps.register.models import CustomField, UnitType


@transaction.atomic
def water_association():
    """A household type with the fields a water association keeps, and a
    cumulative water meter read once a year. Returns the unit type; running it
    again adds nothing new."""
    household, _created = UnitType.objects.get_or_create(
        name=_("Household"),
        defaults={"description": _("A property connected to the water network.")},
    )
    fields = [
        ("property_id", _("Property ID"), CustomField.FieldType.TEXT, "", True),
        ("meter_number", _("Meter number"), CustomField.FieldType.TEXT, "", False),
        ("connected_year", _("Year connected"), CustomField.FieldType.NUMBER, "", False),
        (
            "connection",
            _("Connection"),
            CustomField.FieldType.CHOICE,
            "\n".join([_("Water"), _("Water and sewage")]),
            False,
        ),
        ("residents", _("Number of residents"), CustomField.FieldType.NUMBER, "", False),
    ]
    for order, (key, label, field_type, choices, required) in enumerate(fields):
        CustomField.objects.get_or_create(
            target=CustomField.Target.UNIT,
            unit_type=household,
            key=key,
            defaults={
                "label": label,
                "field_type": field_type,
                "choices": choices,
                "required": required,
                "order": order,
            },
        )
    ReadingType.objects.get_or_create(
        name=_("Water meter"),
        defaults={"unit_type": household, "unit_label": "m³", "decimals": 0, "cumulative": True},
    )
    return household
