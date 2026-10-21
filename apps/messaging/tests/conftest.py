import datetime

import pytest
from django.utils import timezone

from apps.messaging import providers
from apps.readings.models import ReadingRound, ReadingType
from apps.register.models import Person, Unit, UnitContact


@pytest.fixture(autouse=True)
def empty_outbox():
    providers.outbox.clear()
    yield
    providers.outbox.clear()


@pytest.fixture
def open_round(household):
    meter = ReadingType.objects.create(
        name="Vattenmätare", unit_type=household, unit_label="m³", cumulative=True
    )
    today = timezone.localdate()
    return ReadingRound.objects.create(
        reading_type=meter,
        period_label="2026",
        opens_on=today - datetime.timedelta(days=5),
        closes_on=datetime.date(2026, 10, 31),
        is_draft=False,
    )


@pytest.fixture
def make_household(household):
    def make(name, **person):
        unit = Unit.objects.create(unit_type=household, name=name)
        if person:
            contact = Person.objects.create(**person)
            UnitContact.objects.create(unit=unit, person=contact, role="owner")
        return unit

    return make


@pytest.fixture
def admin_client(role_client):
    return role_client("Admin")
