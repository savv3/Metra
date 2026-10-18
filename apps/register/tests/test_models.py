import pytest
from django.core.exceptions import ValidationError

from apps.register.models import CustomField, Person, Unit


def test_archive_and_restore(unit):
    unit.archive()
    assert unit.is_archived
    assert unit not in Unit.objects.active()
    assert unit in Unit.objects.archived()

    unit.restore()
    assert not unit.is_archived


def test_address_line_skips_empty_parts(db):
    person = Person(first_name="A", street_address="Byvägen 4", city="Mariehamn")

    assert person.address_line == "Byvägen 4, Mariehamn"


def test_unit_custom_field_needs_unit_type(db):
    field = CustomField(target=CustomField.Target.UNIT, key="x", label="X")

    with pytest.raises(ValidationError):
        field.clean()


def test_choice_field_needs_options(household):
    field = CustomField(
        target=CustomField.Target.UNIT,
        unit_type=household,
        key="x",
        label="X",
        field_type=CustomField.FieldType.CHOICE,
        choices="\n \n",
    )

    with pytest.raises(ValidationError):
        field.clean()
