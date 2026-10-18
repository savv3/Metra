import pytest

from apps.register.models import CustomField, Person, Unit, UnitType


@pytest.fixture
def household(db):
    unit_type = UnitType.objects.create(name="Household")
    CustomField.objects.create(
        target=CustomField.Target.UNIT,
        unit_type=unit_type,
        key="meter_number",
        label="Meter number",
        required=True,
    )
    CustomField.objects.create(
        target=CustomField.Target.UNIT,
        unit_type=unit_type,
        key="connected",
        label="Connected since",
        field_type=CustomField.FieldType.DATE,
        order=1,
    )
    CustomField.objects.create(
        target=CustomField.Target.UNIT,
        unit_type=unit_type,
        key="usage_limit",
        label="Usage limit",
        field_type=CustomField.FieldType.NUMBER,
        order=2,
    )
    return unit_type


@pytest.fixture
def unit(household):
    return Unit.objects.create(
        unit_type=household,
        name="Byvägen 4",
        street_address="Byvägen 4",
        city="Mariehamn",
        custom_data={"meter_number": "M-100"},
    )


@pytest.fixture
def person(db):
    return Person.objects.create(first_name="Anna", last_name="Lindqvist", email="anna@example.com")


@pytest.fixture
def staff_client(client, django_user_model):
    user = django_user_model.objects.create_user("board", password="pw", is_staff=True)
    client.force_login(user)
    return client
