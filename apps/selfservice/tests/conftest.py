import datetime

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.readings.models import ReadingRound, ReadingType
from apps.register.models import UnitContact
from apps.selfservice.models import SelfServiceLink


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def meter(household):
    return ReadingType.objects.create(
        name="Water meter", unit_type=household, unit_label="m³", cumulative=True
    )


@pytest.fixture
def open_round(meter):
    today = timezone.localdate()
    return ReadingRound.objects.create(
        reading_type=meter,
        period_label=str(today.year),
        opens_on=today - datetime.timedelta(days=5),
        closes_on=today + datetime.timedelta(days=10),
        is_draft=False,
    )


@pytest.fixture
def owner(unit, person):
    UnitContact.objects.create(unit=unit, person=person, role=UnitContact.Role.OWNER)
    return person


@pytest.fixture
def issued(unit, owner, open_round):
    """(link, token, url path) for the unit's owner in the open round."""
    link, token = SelfServiceLink.create_for(unit, owner, open_round)
    return link, token, f"/m/{token}/"
