import datetime

import pytest

from apps.register.forms import PersonForm, UnitContactForm, UnitForm
from apps.register.models import CustomField, Person, UnitContact


def unit_data(**overrides):
    data = {
        "name": "Strandvägen 1",
        "status": "active",
        "country": "AX",
        "custom__meter_number": "M-200",
        "custom__connected": "2020-05-01",
        "custom__usage_limit": "120.5",
    }
    data.update(overrides)
    return data


def test_unit_form_stores_custom_fields_as_json(household):
    form = UnitForm(unit_data(), unit_type=household)

    assert form.is_valid(), form.errors
    unit = form.save()

    unit.refresh_from_db()
    assert unit.unit_type == household
    assert unit.custom_data == {
        "meter_number": "M-200",
        "connected": "2020-05-01",
        "usage_limit": "120.5",
    }


def test_unit_form_requires_required_custom_field(household):
    form = UnitForm(unit_data(custom__meter_number=""), unit_type=household)

    assert not form.is_valid()
    assert "custom__meter_number" in form.errors


def test_unit_form_rejects_invalid_custom_values(household):
    form = UnitForm(
        unit_data(custom__connected="not a date", custom__usage_limit="lots"), unit_type=household
    )

    assert not form.is_valid()
    assert {"custom__connected", "custom__usage_limit"} <= form.errors.keys()


def test_unit_form_loads_stored_values_as_initial(unit):
    unit.custom_data = {"meter_number": "M-100", "connected": "2021-01-02"}

    form = UnitForm(instance=unit, unit_type=unit.unit_type)

    assert form.initial["custom__meter_number"] == "M-100"
    assert form.initial["custom__connected"] == datetime.date(2021, 1, 2)


def test_unit_form_keeps_values_of_removed_fields(unit):
    unit.custom_data = {"meter_number": "M-100", "old_field": "keep me"}
    unit.save()

    form = UnitForm(unit_data(name=unit.name), instance=unit, unit_type=unit.unit_type)
    assert form.is_valid(), form.errors
    form.save()

    unit.refresh_from_db()
    assert unit.custom_data["old_field"] == "keep me"


def test_clearing_optional_custom_field_removes_it(unit):
    unit.custom_data = {"meter_number": "M-100", "usage_limit": "50"}
    unit.save()

    form = UnitForm(
        unit_data(name=unit.name, custom__usage_limit="", custom__connected=""),
        instance=unit,
        unit_type=unit.unit_type,
    )
    assert form.is_valid(), form.errors
    form.save()

    unit.refresh_from_db()
    assert "usage_limit" not in unit.custom_data


def test_unit_end_date_cannot_precede_start_date(household):
    form = UnitForm(unit_data(start_date="2024-01-01", end_date="2023-01-01"), unit_type=household)

    assert not form.is_valid()
    assert "end_date" in form.errors


@pytest.mark.django_db
def test_person_form_includes_person_custom_fields():
    CustomField.objects.create(
        target=CustomField.Target.PERSON,
        key="member_since",
        label="Member since",
        field_type=CustomField.FieldType.BOOLEAN,
    )

    form = PersonForm(
        {
            "first_name": "Erik",
            "preferred_channel": "post",
            "country": "FI",
            "custom__member_since": "on",
        }
    )

    assert form.is_valid(), form.errors
    assert form.save().custom_data == {"member_since": True}


@pytest.mark.django_db
@pytest.mark.parametrize(("channel", "missing"), [("email", "email"), ("sms", "phone")])
def test_person_form_needs_contact_detail_for_chosen_channel(channel, missing):
    form = PersonForm({"first_name": "Erik", "preferred_channel": channel, "country": "FI"})

    assert not form.is_valid()
    assert missing in form.errors


def test_contact_form_rejects_duplicate_role(unit, person):
    UnitContact.objects.create(unit=unit, person=person, role="owner")

    form = UnitContactForm({"person": person.pk, "role": "owner"}, unit=unit)

    assert not form.is_valid()
    assert form.non_field_errors()


def test_contact_form_hides_archived_people(unit, person):
    person.archive()

    form = UnitContactForm(unit=unit)

    assert person not in form.fields["person"].queryset
    assert Person.objects.count() == 1
