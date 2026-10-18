import datetime

import pytest

from apps.readings.models import ReadingRound, ReadingType


@pytest.fixture
def meter(household):
    return ReadingType.objects.create(
        name="Water meter", unit_type=household, unit_label="m³", cumulative=True
    )


@pytest.fixture
def make_round(meter):
    def make(year, status=ReadingRound.Status.OPEN, reading_type=None):
        return ReadingRound.objects.create(
            reading_type=reading_type or meter,
            period_label=str(year),
            opens_on=datetime.date(year, 1, 1),
            closes_on=datetime.date(year, 12, 31),
            status=status,
        )

    return make


@pytest.fixture
def round_(make_round):
    return make_round(2026)
