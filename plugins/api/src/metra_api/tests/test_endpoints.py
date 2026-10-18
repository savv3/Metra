import datetime
from decimal import Decimal

import pytest
from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings

from apps.plugins import api

V1 = "/plugins/api/v1/"


def entries_for(obj):
    return LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(obj), object_pk=str(obj.pk)
    )


# Roles


def test_read_only_role_can_read_but_not_write(api_as, unit, household):
    http = api_as("Read-only")
    assert http.get(f"{V1}units/").status_code == 200
    assert http.get(f"{V1}people/").status_code == 200
    response = http.post(
        f"{V1}units/",
        {"unit_type": household.pk, "name": "New", "custom_fields": {"meter_number": "M-1"}},
        format="json",
    )
    assert response.status_code == 403
    assert not api.Unit.objects.filter(name="New").exists()


def test_board_can_create_units_and_people(api_as, household):
    http = api_as("Board")
    response = http.post(
        f"{V1}units/",
        {
            "unit_type": household.pk,
            "name": "Strandvägen 1",
            "city": "Mariehamn",
            "custom_fields": {"meter_number": "M-200", "usage_limit": 150},
        },
        format="json",
    )
    assert response.status_code == 201, response.json()
    unit = api.Unit.objects.get(name="Strandvägen 1")
    assert unit.custom_data == {"meter_number": "M-200", "usage_limit": "150"}
    assert unit.status == "active"
    assert response.json()["custom_fields"]["meter_number"] == "M-200"

    response = http.post(
        f"{V1}people/",
        {"first_name": "Erik", "last_name": "Sjöberg", "email": "erik@example.com"},
        format="json",
    )
    assert response.status_code == 201, response.json()
    assert api.Person.objects.filter(first_name="Erik").exists()


def test_without_view_permission_nobody_lists(api_as, unit):
    http = api_as("Board")
    http.api_client.user.groups.clear()
    assert http.get(f"{V1}units/").status_code == 403
    assert http.get(f"{V1}people/").status_code == 403
    assert http.get(f"{V1}invoices/").status_code == 403


def test_read_only_flag_refuses_writes_whatever_the_role(api_as, unit):
    http = api_as("Admin", read_only=True)
    assert http.get(f"{V1}units/{unit.pk}/").status_code == 200
    assert http.patch(f"{V1}units/{unit.pk}/", {"name": "X"}, format="json").status_code == 403
    assert http.delete(f"{V1}units/{unit.pk}/").status_code == 403
    unit.refresh_from_db()
    assert unit.name == "Byvägen 4" and not unit.is_archived


def test_read_only_role_cannot_see_invoices(api_as):
    # Read-only has no invoicing permissions in Metra, so neither does its client.
    assert api_as("Read-only").get(f"{V1}invoices/").status_code == 403


# Units and people


def test_delete_archives_instead_of_deleting(api_as, unit, person):
    http = api_as("Board")
    assert http.delete(f"{V1}units/{unit.pk}/").status_code == 204
    assert http.delete(f"{V1}people/{person.pk}/").status_code == 204
    unit.refresh_from_db()
    person.refresh_from_db()
    assert unit.is_archived and person.is_archived
    assert http.get(f"{V1}units/").json()["count"] == 0
    archived = http.get(f"{V1}units/", {"archived": "true"}).json()
    assert [row["id"] for row in archived["results"]] == [unit.pk]
    # Still readable by id.
    assert http.get(f"{V1}units/{unit.pk}/").status_code == 200


def test_unit_filters(api_as, unit, household):
    other_type = api.UnitType.objects.create(name="Member")
    tag = api.Tag.objects.create(name="Summer")
    unit.tags.add(tag)
    api.Unit.objects.create(unit_type=other_type, name="Club", status="inactive")
    http = api_as("Read-only")

    def names(**params):
        return [row["name"] for row in http.get(f"{V1}units/", params).json()["results"]]

    assert names() == ["Byvägen 4", "Club"]
    assert names(unit_type=household.pk) == ["Byvägen 4"]
    assert names(status="inactive") == ["Club"]
    assert names(tag="Summer") == ["Byvägen 4"]
    assert names(tag=tag.pk) == ["Byvägen 4"]
    assert names(search="club") == ["Club"]


def test_person_search_and_page_size(api_as, person):
    api.Person.objects.create(first_name="Bo", last_name="Ek", preferred_channel="post")
    http = api_as("Read-only")
    response = http.get(f"{V1}people/", {"search": "lindq"}).json()
    assert [row["first_name"] for row in response["results"]] == ["Anna"]
    response = http.get(f"{V1}people/", {"page_size": 1}).json()
    assert response["count"] == 2 and len(response["results"]) == 1 and response["next"]
    response = http.get(f"{V1}people/", {"page_size": 1000}).json()
    assert len(response["results"]) == 2


def test_partial_update_keeps_other_fields_and_custom_values(api_as, unit):
    http = api_as("Board")
    response = http.patch(
        f"{V1}units/{unit.pk}/",
        {"city": "Jomala", "custom_fields": {"usage_limit": "90.5"}},
        format="json",
    )
    assert response.status_code == 200, response.json()
    unit.refresh_from_db()
    assert unit.city == "Jomala"
    assert unit.street_address == "Byvägen 4"
    assert unit.custom_data == {"meter_number": "M-100", "usage_limit": "90.5"}


def test_tags_by_name(api_as, person):
    api.Tag.objects.create(name="Board member")
    http = api_as("Board")
    response = http.patch(f"{V1}people/{person.pk}/", {"tags": ["Board member"]}, format="json")
    assert response.status_code == 200, response.json()
    assert list(person.tags.values_list("name", flat=True)) == ["Board member"]
    response = http.patch(f"{V1}people/{person.pk}/", {"tags": ["Nope"]}, format="json")
    assert response.status_code == 400


def test_a_units_type_cannot_change(api_as, unit):
    other = api.UnitType.objects.create(name="Member")
    response = api_as("Board").patch(
        f"{V1}units/{unit.pk}/", {"unit_type": other.pk}, format="json"
    )
    assert response.status_code == 400
    assert "unit_type" in response.json()


# Custom fields are checked like the web form checks them


@pytest.mark.parametrize(
    "custom, field",
    [
        ({}, "meter_number"),  # required
        ({"meter_number": "M-1", "connected": "not a date"}, "connected"),
        ({"meter_number": "M-1", "usage_limit": "lots"}, "usage_limit"),
        ({"meter_number": "M-1", "colour": "blue"}, "colour"),  # no such field
        ({"meter_number": ["M-1", "M-2"]}, "meter_number"),  # one value per field
    ],
)
def test_custom_fields_the_form_rejects_are_rejected(api_as, household, custom, field):
    data = {"unit_type": household.pk, "name": "Test", "custom_fields": custom}
    form_data = {"name": "Test", "status": "active", "country": "FI"}
    form_data.update({f"custom__{key}": value for key, value in custom.items()})
    form = api.UnitForm(form_data, unit_type=household)
    if field != "colour" and not isinstance(custom.get(field), list):
        assert not form.is_valid()

    response = api_as("Board").post(f"{V1}units/", data, format="json")
    assert response.status_code == 400
    assert field in response.json()["custom_fields"]
    assert not api.Unit.objects.filter(name="Test").exists()


def test_choice_fields_accept_only_their_options(api_as, household):
    api.CustomField.objects.create(
        target="unit",
        unit_type=household,
        key="connection",
        label="Connection",
        field_type="choice",
        choices="Summer\nAll year",
    )
    http = api_as("Board")
    base = {"unit_type": household.pk, "name": "Test"}
    bad = {**base, "custom_fields": {"meter_number": "1", "connection": "Winter"}}
    assert http.post(f"{V1}units/", bad, format="json").status_code == 400
    good = {**base, "custom_fields": {"meter_number": "1", "connection": "All year"}}
    assert http.post(f"{V1}units/", good, format="json").status_code == 201


def test_person_rules_from_the_form_apply(api_as):
    response = api_as("Board").post(
        f"{V1}people/", {"first_name": "Ann", "preferred_channel": "sms"}, format="json"
    )
    assert response.status_code == 400
    assert "phone" in response.json()


def test_unit_types_list_their_custom_fields(api_as, household):
    response = api_as("Read-only").get(f"{V1}unit-types/").json()
    fields = response["results"][0]["custom_fields"]
    assert fields[0] == {
        "key": "meter_number",
        "label": "Meter number",
        "type": "text",
        "choices": [],
        "required": True,
        "help_text": "",
    }
    assert api_as("Board").post(f"{V1}unit-types/", {"name": "X"}, format="json").status_code in (
        403,
        405,
    )


# Contacts


def test_link_and_unlink_a_person(api_as, unit, person):
    http = api_as("Board")
    response = http.post(
        f"{V1}unit-contacts/",
        {"unit": unit.pk, "person": person.pk, "role": "owner"},
        format="json",
    )
    assert response.status_code == 201, response.json()
    again = http.post(
        f"{V1}unit-contacts/",
        {"unit": unit.pk, "person": person.pk, "role": "owner"},
        format="json",
    )
    assert again.status_code == 400
    listed = http.get(f"{V1}unit-contacts/", {"unit": unit.pk}).json()["results"]
    assert [row["role"] for row in listed] == ["owner"]
    assert http.get(f"{V1}units/{unit.pk}/").json()["contacts"][0]["person"] == person.pk
    assert http.delete(f"{V1}unit-contacts/{response.json()['id']}/").status_code == 204
    assert not unit.unit_contacts.exists()


# Readings


@pytest.fixture
def round_(household):
    meter = api.ReadingType.objects.create(name="Water meter", unit_type=household)
    return api.ReadingRound.objects.create(
        reading_type=meter,
        period_label="2026",
        opens_on=datetime.date(2026, 1, 1),
        closes_on=datetime.date(2026, 12, 31),
        status="open",
    )


def test_readings_create_and_correct(api_as, unit, round_):
    http = api_as("Board")
    response = http.post(
        f"{V1}readings/", {"round": round_.pk, "unit": unit.pk, "value": 1234}, format="json"
    )
    assert response.status_code == 201, response.json()
    reading = api.Reading.objects.get()
    assert reading.value == Decimal("1234")
    assert reading.source == "staff"
    assert reading.submitted_by == http.api_client.user
    assert response.json()["submitted_by"] == http.api_client.user.username

    # The reading type has no decimals, as the web form says.
    bad = http.patch(f"{V1}readings/{reading.pk}/", {"value": "12.5"}, format="json")
    assert bad.status_code == 400 and "value" in bad.json()
    note = http.patch(f"{V1}readings/{reading.pk}/", {"note": "Checked"}, format="json")
    assert note.status_code == 200, note.json()
    again = http.post(
        f"{V1}readings/", {"round": round_.pk, "unit": unit.pk, "value": 1}, format="json"
    )
    assert again.status_code == 400

    listed = http.get(f"{V1}readings/", {"round": round_.pk}).json()
    assert listed["count"] == 1
    assert http.get(f"{V1}reading-rounds/").json()["results"][0]["period_label"] == "2026"


def test_readings_only_for_units_of_the_rounds_type(api_as, round_):
    other = api.UnitType.objects.create(name="Member")
    club = api.Unit.objects.create(unit_type=other, name="Club")
    response = api_as("Board").post(
        f"{V1}readings/", {"round": round_.pk, "unit": club.pk, "value": 1}, format="json"
    )
    assert response.status_code == 400


def test_read_only_role_cannot_enter_readings(api_as, unit, round_):
    response = api_as("Read-only").post(
        f"{V1}readings/", {"round": round_.pk, "unit": unit.pk, "value": 1}, format="json"
    )
    assert response.status_code == 403


# Invoices and payments


def test_invoices_and_payments_are_read_only(api_as, unit, person):
    invoice = api.Invoice.objects.create(unit=unit, person=person, period_label="2026")
    api.InvoiceLine.objects.create(
        invoice=invoice, description="Grundavgift", unit_price=Decimal("100")
    )
    payment = api.Payment.objects.create(
        invoice=invoice, amount=Decimal("10"), paid_on=datetime.date(2026, 3, 1)
    )
    http = api_as("Treasurer")
    data = http.get(f"{V1}invoices/{invoice.pk}/").json()
    assert data["status"] == "draft"
    assert data["lines"][0]["net"] == "100.00"
    assert http.get(f"{V1}payments/", {"invoice": invoice.pk}).json()["results"][0]["id"] == (
        payment.pk
    )
    for url in [f"{V1}invoices/", f"{V1}payments/"]:
        assert http.post(url, {}, format="json").status_code == 405
    assert http.delete(f"{V1}invoices/{invoice.pk}/").status_code == 405
    assert http.patch(f"{V1}payments/{payment.pk}/", {}, format="json").status_code == 405
    # Board may look but not change: refused before the method is checked.
    assert api_as("Board").post(f"{V1}invoices/", {}, format="json").status_code == 403


# Audit log


def test_writes_are_logged_as_the_clients_user(api_as, unit):
    http = api_as("Board")
    response = http.patch(f"{V1}units/{unit.pk}/", {"name": "Byvägen 6"}, format="json")
    assert response.status_code == 200
    entry = entries_for(unit).filter(action=LogEntry.Action.UPDATE).get()
    assert entry.actor == http.api_client.user


def test_retrieving_a_person_logs_a_view(api_as, person):
    http = api_as("Read-only")
    assert http.get(f"{V1}people/{person.pk}/").status_code == 200
    view = entries_for(person).get(action=LogEntry.Action.ACCESS)
    assert view.actor == http.api_client.user
    # Lists do not log a view of every row.
    http.get(f"{V1}people/")
    assert entries_for(person).filter(action=LogEntry.Action.ACCESS).count() == 1


# Rate limits and the schema


@override_settings(METRA_API_RATE="2/min")
def test_calls_are_rate_limited_per_client(api_as):
    http = api_as("Read-only")
    assert http.get(f"{V1}units/").status_code == 200
    assert http.get(f"{V1}units/").status_code == 200
    assert http.get(f"{V1}units/").status_code == 429
    # Another client has its own allowance.
    assert api_as("Read-only", name="Other").get(f"{V1}units/").status_code == 200


def test_schema_needs_a_token_or_a_staff_login(client, api_as, role_client):
    assert client.get(f"{V1}schema/").status_code in (401, 403)
    response = api_as("Read-only").get(f"{V1}schema/")
    assert response.status_code == 200
    assert "/plugins/api/v1/units/" in response.json()["paths"]
    assert role_client("Board").get(f"{V1}schema/").status_code == 403
    assert role_client("Admin").get(f"{V1}schema/").status_code == 200


def test_responses_are_json_only(api_as, unit):
    http = api_as("Read-only")
    response = http.get(f"{V1}units/", HTTP_ACCEPT="text/html")
    assert response.status_code == 406
