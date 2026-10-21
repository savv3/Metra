import datetime
from decimal import Decimal as D

import pytest
from django.utils import translation

from apps.invoicing.models import BillingSettings, FeeLine, FeePlan
from apps.readings.models import Reading, ReadingRound, ReadingType
from apps.register.models import Organisation, Person, Unit, UnitContact


@pytest.fixture
def organisation(db):
    return Organisation.objects.create(
        name="Västerby vattenandelslag",
        business_id="1234567-8",
        street_address="Bystigen 2",
        postal_code="22240",
        city="Hammarland",
    )


@pytest.fixture
def billing(organisation):
    settings = BillingSettings.current()
    settings.iban = "FI21 1234 5600 0007 85"
    settings.bic = "NDEAFIHH"
    settings.save()
    return settings


@pytest.fixture
def meter(household):
    return ReadingType.objects.create(
        name="Vattenmätare", unit_type=household, unit_label="m³", cumulative=True
    )


@pytest.fixture
def rounds(meter):
    def make(year):
        return ReadingRound.objects.create(
            reading_type=meter,
            period_label=str(year),
            opens_on=datetime.date(year, 10, 1),
            closes_on=datetime.date(year, 10, 31),
            is_draft=False,
        )

    return make(2025), make(2026)


@pytest.fixture
def plan(household, meter):
    plan = FeePlan.objects.create(name="Kommunal vattenavgift", unit_type=household)
    FeeLine.objects.create(
        plan=plan,
        kind="fixed",
        description="Grundavgift {period}",
        unit_price=D("120"),
        unit_label="st",
        vat_rate=D("25.5"),
        order=0,
    )
    FeeLine.objects.create(
        plan=plan,
        kind="usage",
        description="Vatten {period}",
        unit_price=D("1.50"),
        vat_rate=D("25.5"),
        reading_type=meter,
        order=1,
    )
    return plan


@pytest.fixture
def make_household(household):
    def make(name, readings=(), **person):
        unit = Unit.objects.create(
            unit_type=household,
            name=name,
            street_address=name,
            postal_code="22240",
            city="Hammarland",
        )
        if person:
            contact = Person.objects.create(**person)
            UnitContact.objects.create(unit=unit, person=contact, role="owner")
        for round_, value in readings:
            Reading.objects.create(round=round_, unit=unit, value=D(value))
        return unit

    return make


@pytest.fixture
def treasurer_client(role_client):
    return role_client("Treasurer")


@pytest.fixture(autouse=True)
def english():
    """Messages in English, whatever an earlier test left active."""
    with translation.override("en"):
        yield
