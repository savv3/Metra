import datetime

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from django.utils import timezone

from apps.readings.models import ReadingRound

DAY = datetime.timedelta(days=1)


def dated(make_round, opens, closes, year=2026, **kwargs):
    round_ = make_round(year, **kwargs)
    round_.opens_on, round_.closes_on = opens, closes
    round_.save()
    return round_


@pytest.mark.parametrize(
    ("opens", "closes", "is_draft", "state", "accepts"),
    [
        (+3, +10, False, "upcoming", False),
        (-3, +10, False, "open", True),
        (0, 0, False, "open", True),
        (-10, -1, False, "closed", False),
        (-3, +10, True, "draft", False),
        (-10, -1, True, "draft", False),
        (+3, +10, True, "draft", False),
    ],
)
def test_state_comes_from_the_dates_and_the_draft_flag(
    make_round, opens, closes, is_draft, state, accepts
):
    today = timezone.localdate()
    round_ = dated(make_round, today + opens * DAY, today + closes * DAY, is_draft=is_draft)

    assert round_.state == state
    assert round_.status == state
    assert round_.accepts_member_readings is accepts
    assert (round_ in ReadingRound.objects.open_now()) is accepts
    assert round_ in ReadingRound.objects.in_state(state)


def test_state_label_names_the_date(make_round):
    today = timezone.localdate()
    upcoming = dated(make_round, today + 3 * DAY, today + 9 * DAY)

    assert "Not yet open" not in str(upcoming.state_label)
    assert upcoming.state_label.startswith(("Opens", "Öppnar"))
    open_ = dated(make_round, today - DAY, today + 9 * DAY, year=2027)
    assert open_.state_label.startswith(("Open until", "Öppen till"))
    draft = dated(make_round, today, today, year=2028, is_draft=True)
    assert str(draft.state_label) in ("Draft", "Utkast")


def test_round_pages_show_the_state(board_client, make_round):
    today = timezone.localdate()
    dated(make_round, today - DAY, today + 9 * DAY)

    page = board_client.get(reverse("readings:round_list"), HTTP_ACCEPT_LANGUAGE="en")

    assert "Open until" in page.content.decode()


def test_form_has_a_draft_checkbox_instead_of_a_status(board_client, meter):
    form = board_client.get(reverse("readings:round_create")).context["form"]

    assert "is_draft" in form.fields and "status" not in form.fields
    assert form.fields["is_draft"].initial is None or form.fields["is_draft"].initial is True


def test_data_migration_maps_status_to_the_draft_flag(transactional_db, household):
    executor = MigrationExecutor(connection)
    executor.migrate([("readings", "0003_reading_submitted_by_person")])
    old = executor.loader.project_state([("readings", "0003_reading_submitted_by_person")]).apps
    Type = old.get_model("readings", "ReadingType")
    Round = old.get_model("readings", "ReadingRound")
    kind = Type.objects.create(name="Meter", unit_type_id=household.pk)
    for label, status in [("d", "draft"), ("o", "open"), ("c", "closed")]:
        Round.objects.create(
            reading_type=kind,
            period_label=label,
            opens_on=datetime.date(2026, 1, 1),
            closes_on=datetime.date(2026, 2, 1),
            status=status,
        )

    executor = MigrationExecutor(connection)
    executor.migrate([("readings", "0004_readinground_is_draft")])
    new = executor.loader.project_state([("readings", "0004_readinground_is_draft")]).apps
    flags = dict(
        new.get_model("readings", "ReadingRound").objects.values_list("period_label", "is_draft")
    )

    assert flags == {"d": True, "o": False, "c": False}
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())
