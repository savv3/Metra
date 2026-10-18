from decimal import Decimal as D

import pytest
from django.utils import translation

from apps.readings.models import Reading, ReadingType
from apps.readings.usage import assess, earlier_values


def test_cumulative_usage_is_the_difference_from_last_time(meter):
    result = assess(meter, D(150), [D(100), D(60)])

    assert (result.previous, result.usage, result.warnings) == (D(100), D(50), [])


def test_first_reading_of_a_meter_has_no_usage(meter):
    result = assess(meter, D(150), [])

    assert result.usage is None
    assert result.warnings == []


def test_lower_than_last_time_warns(meter):
    with translation.override("en"):
        result = assess(meter, D(90), [D(100)])

    assert result.usage == D(-10)
    assert "Lower than the previous reading" in result.warnings[0]


def test_far_above_usual_warns(meter):
    # Usual usage is about 50 per round; 400 is far above that.
    with translation.override("en"):
        result = assess(meter, D(600), [D(200), D(150), D(100)])

    assert result.usage == D(400)
    assert "Much higher than usual" in result.warnings[0]


def test_somewhat_higher_does_not_warn(meter):
    assert assess(meter, D(320), [D(200), D(150), D(100)]).warnings == []


@pytest.mark.django_db
def test_non_cumulative_values_are_the_usage(household):
    reading_type = ReadingType.objects.create(name="Visitors", unit_type=household)

    assert assess(reading_type, D(10), [D(12)]).usage == D(10)
    assert assess(reading_type, D(100), [D(12), D(10)]).warnings


def test_earlier_values_skip_missing_rounds_and_ignore_later_ones(make_round, unit):
    first, second, third, later = (make_round(year) for year in (2023, 2024, 2025, 2027))
    Reading.objects.create(round=first, unit=unit, value=10)
    Reading.objects.create(round=third, unit=unit, value=30)
    Reading.objects.create(round=later, unit=unit, value=99)
    current = make_round(2026)

    assert earlier_values(current, [unit.pk]) == {unit.pk: [D(30), D(10)]}
    assert earlier_values(second, [unit.pk]) == {unit.pk: [D(10)]}
