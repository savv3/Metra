import csv
import io
from decimal import Decimal as D

from auditlog.models import LogEntry
from django.core.management import call_command
from django.urls import reverse

from apps.readings.models import Reading, ReadingRound, ReadingType
from apps.register.models import Unit, UnitType

HTMX = {"HTTP_HX_REQUEST": "true", "HTTP_HX_TARGET": "results"}


def entry_url(round_, unit):
    return reverse("readings:reading_entry", args=[round_.pk, unit.pk])


def test_create_round(board_client, meter):
    response = board_client.post(
        reverse("readings:round_create"),
        {
            "reading_type": meter.pk,
            "period_label": "2026",
            "opens_on": "2026-03-01",
            "closes_on": "2026-03-31",
        },
    )

    round_ = ReadingRound.objects.get()
    assert response.status_code == 302
    assert (round_.period_label, round_.is_draft) == ("2026", False)


def test_round_cannot_close_before_it_opens(board_client, meter):
    response = board_client.post(
        reverse("readings:round_create"),
        {
            "reading_type": meter.pk,
            "period_label": "2026",
            "opens_on": "2026-03-31",
            "closes_on": "2026-03-01",
        },
    )

    assert response.status_code == 200
    assert not ReadingRound.objects.exists()


def test_archived_reading_types_are_not_offered(board_client, meter, household):
    ReadingType.objects.create(name="Old", unit_type=household).archive()

    form = board_client.get(reverse("readings:round_create")).context["form"]

    assert list(form.fields["reading_type"].queryset) == [meter]


def test_round_list_shows_progress(board_client, round_, unit, household):
    Unit.objects.create(unit_type=household, name="Strandvägen 9")
    Reading.objects.create(round=round_, unit=unit, value=10)

    response = board_client.get(reverse("readings:round_list"), HTTP_ACCEPT_LANGUAGE="en")

    assert "1 of 2" in response.content.decode()


def test_round_detail_expects_active_units_of_the_type(board_client, round_, unit, household):
    Unit.objects.create(unit_type=household, name="Archived").archive()
    Unit.objects.create(unit_type=household, name="Inactive", status="inactive")
    Unit.objects.create(unit_type=UnitType.objects.create(name="Club"), name="Other type")

    response = board_client.get(round_.get_absolute_url())

    assert [row["unit"] for row in response.context["rows"]] == [unit]
    assert response.context["missing"] == 1


def test_round_detail_htmx_filter_for_missing(board_client, round_, unit, household):
    missing = Unit.objects.create(unit_type=household, name="Strandvägen 9")
    Reading.objects.create(round=round_, unit=unit, value=10)

    response = board_client.get(round_.get_absolute_url(), {"show": "missing"}, **HTMX)

    assert response.templates[0].name == "readings/_round_results.html"
    assert [row["unit"] for row in response.context["rows"]] == [missing]
    reported = board_client.get(round_.get_absolute_url(), {"show": "submitted"}, **HTMX)
    assert [row["unit"] for row in reported.context["rows"]] == [unit]


def test_enter_reading_from_round_form(board_client, round_, unit):
    response = board_client.post(entry_url(round_, unit), {"value": "123", "note": "Photo"})

    reading = Reading.objects.get()
    assert response.status_code == 302
    assert response.url == f"{round_.get_absolute_url()}#unit-{unit.pk}"
    assert (reading.value, reading.note) == (123, "Photo")


def test_enter_reading_respects_decimals_and_accepts_comma(board_client, round_, unit, meter):
    refused = board_client.post(entry_url(round_, unit), {"value": "123,5"})
    meter.decimals = 1
    meter.save()
    board_client.post(entry_url(round_, unit), {"value": "123,5", "note": "Photo"})

    assert refused.status_code == 200
    reading = Reading.objects.get()
    assert (reading.value, reading.note, reading.source) == (D("123.5"), "Photo", "staff")
    assert reading.submitted_by.username == "board"


def test_inline_entry_returns_the_row(board_client, round_, unit):
    response = board_client.post(
        entry_url(round_, unit), {"value": "40", "inline": "1"}, HTTP_HX_REQUEST="true"
    )

    assert response.templates[0].name == "readings/_round_row.html"
    assert f'id="unit-{unit.pk}"' in response.content.decode()
    assert Reading.objects.get().value == 40


def test_inline_entry_shows_errors_in_the_row(board_client, round_, unit):
    response = board_client.post(
        entry_url(round_, unit), {"value": "abc", "inline": "1"}, HTTP_HX_REQUEST="true"
    )

    assert 'aria-invalid="true"' in response.content.decode()
    assert not Reading.objects.exists()


def test_inline_entry_keeps_the_note(board_client, round_, unit):
    Reading.objects.create(round=round_, unit=unit, value=10, note="Meter in the cellar")

    board_client.post(
        entry_url(round_, unit), {"value": "12", "inline": "1"}, HTTP_HX_REQUEST="true"
    )

    assert Reading.objects.get().note == "Meter in the cellar"


def test_lower_value_is_saved_with_a_warning(board_client, make_round, unit):
    last_year = make_round(2025)
    Reading.objects.create(round=last_year, unit=unit, value=100)
    round_ = make_round(2026)

    response = board_client.post(entry_url(round_, unit), {"value": "90"}, follow=True)

    assert Reading.objects.get(round=round_).value == 90
    levels = [m.level_tag for m in response.context["messages"]]
    assert "warning" in levels


def test_correction_from_unit_page_goes_back_there_and_is_logged(board_client, round_, unit):
    reading = Reading.objects.create(round=round_, unit=unit, value=10, source="member")

    response = board_client.post(entry_url(round_, unit), {"value": "11", "next": "unit"})

    assert response.url == unit.get_absolute_url()
    reading.refresh_from_db()
    assert (reading.value, reading.source) == (11, "staff")
    change = LogEntry.objects.get_for_object(reading).get(action=LogEntry.Action.UPDATE)
    assert change.changes_dict["value"] == ["10.000", "11"]
    page = board_client.get(entry_url(round_, unit), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert "History" in page
    assert "10 &rarr; 11" in page


def test_unit_of_another_type_cannot_get_a_reading(board_client, round_):
    other = Unit.objects.create(unit_type=UnitType.objects.create(name="Club"), name="Club")

    assert board_client.get(entry_url(round_, other)).status_code == 404


def test_unit_page_lists_readings_with_usage(board_client, make_round, unit):
    Reading.objects.create(round=make_round(2025), unit=unit, value=100)
    Reading.objects.create(round=make_round(2026), unit=unit, value=142)

    page = board_client.get(unit.get_absolute_url(), HTTP_ACCEPT_LANGUAGE="en").content.decode()

    assert "Water meter 2026" in page
    assert "42 m³" in page
    assert entry_url(ReadingRound.objects.get(period_label="2026"), unit) in page


def test_round_export(board_client, make_round, unit, household):
    Reading.objects.create(round=make_round(2025), unit=unit, value=100)
    round_ = make_round(2026)
    Reading.objects.create(round=round_, unit=unit, value=142, note="ok")
    Unit.objects.create(unit_type=household, name="Strandvägen 9")

    response = board_client.get(
        reverse("readings:round_export", args=[round_.pk]), HTTP_ACCEPT_LANGUAGE="en"
    )

    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig")), delimiter=";"))
    assert rows[0][:6] == ["Unit", "Address", "Period", "Previous reading", "Reading", "Usage"]
    assert rows[1][:6] == ["Byvägen 4", "Byvägen 4, Mariehamn", "2026", "100", "142", "42"]
    assert rows[2][0] == "Strandvägen 9"
    assert rows[2][4] == ""
    assert LogEntry.objects.filter(additional_data__export="csv").exists()


def test_water_sample_adds_a_meter_reading_type(db):
    call_command("load_sample_setup", "water")

    meter = ReadingType.objects.get()
    assert (meter.name, meter.unit_label, meter.cumulative) == ("Vattenmätare", "m³", True)
    assert meter.unit_type.name == "Hushåll"
