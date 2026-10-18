import pytest
from django.core.management import CommandError, call_command

from apps.register.models import CustomField, UnitType


@pytest.mark.django_db
def test_load_water_sample_creates_household_type():
    call_command("load_sample_setup", "water")

    unit_type = UnitType.objects.get()
    assert set(unit_type.custom_fields.values_list("key", flat=True)) == {
        "property_id",
        "meter_number",
        "connection",
    }
    assert CustomField.objects.get(key="connection").choice_list == ["Året runt", "Sommar"]


@pytest.mark.django_db
def test_load_sample_twice_changes_nothing():
    call_command("load_sample_setup", "water")

    with pytest.raises(CommandError):
        call_command("load_sample_setup", "water")
    assert CustomField.objects.count() == 3
