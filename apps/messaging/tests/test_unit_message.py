import re

from django.core import mail
from django.urls import reverse

from apps.messaging import providers
from apps.messaging.models import MessageBatch
from apps.register.models import Person, UnitContact


def url(unit):
    return reverse("messaging:unit_compose", args=[unit.pk])


def send(client, unit, step="preview", **data):
    fields = {
        "contacts": "all",
        "channels": "email",
        "body": "Hej {first_name}, mätarbytet sker på tisdag.",
        "subject": "Mätarbyte",
        "step": step,
    }
    return client.post(url(unit), {**fields, **data}, HTTP_ACCEPT_LANGUAGE="en")


def test_board_writes_to_one_unit_from_its_page(board_client, make_household):
    unit = make_household("Byvägen 4", first_name="Anna", email="anna@example.com")
    other = make_household("Byvägen 6", first_name="Bo", email="bo@example.com")
    partner = Person.objects.create(first_name="Ali", email="ali@example.com")
    UnitContact.objects.create(unit=unit, person=partner, role="other")

    page = board_client.get(unit.get_absolute_url()).content.decode()
    assert url(unit) in page
    assert url(other) not in page.split('id="messages"')[0]  # only this unit's button

    preview = send(board_client, unit).content.decode()
    assert "Byvägen 4" in preview
    assert "Send now to 2 people" in preview

    response = send(board_client, unit, step="confirm")

    batch = MessageBatch.objects.get()
    assert response.url == batch.get_absolute_url()
    assert batch.kind == MessageBatch.Kind.BROADCAST
    assert batch.audience.startswith("Byvägen 4")
    assert sorted(m.to[0] for m in mail.outbox) == ["ali@example.com", "anna@example.com"]
    assert mail.outbox[0].subject == "Mätarbyte"
    assert providers.outbox == []
    assert not batch.messages.filter(unit=other).exists()


def test_the_message_shows_on_the_unit_page(board_client, make_household):
    unit = make_household("Byvägen 4", first_name="Anna", email="anna@example.com")
    send(board_client, unit, step="confirm")

    page = board_client.get(unit.get_absolute_url()).content.decode()

    assert 'id="messages"' in page
    assert "Mätarbyte" in page
    assert "anna@example.com" in page


def test_email_is_the_default_and_sms_an_option(board_client, make_household):
    unit = make_household("Byvägen 4", first_name="Anna", phone="0401234567")

    form = board_client.get(url(unit), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert re.search(r'value="email"[^>]*checked', form)
    assert 'name="scope"' not in form
    assert 'name="urgent"' not in form

    send(board_client, unit, step="confirm", channels="sms", subject="")

    assert [m["to"] for m in providers.outbox] == ["0401234567"]
    assert mail.outbox == []


def test_only_roles_with_the_permission_can_write_to_a_unit(role_client, make_household):
    unit = make_household("Byvägen 4", first_name="Anna", email="anna@example.com")
    for role in ["Treasurer", "Read-only"]:
        client = role_client(role)
        assert client.get(url(unit)).status_code == 403, role
        assert send(client, unit, step="confirm").status_code == 403, role
        assert url(unit) not in client.get(unit.get_absolute_url()).content.decode(), role
    assert not MessageBatch.objects.exists()
    assert role_client("Admin").get(url(unit)).status_code == 200


def test_archived_units_cannot_be_written_to(board_client, make_household):
    unit = make_household("Byvägen 4", first_name="Anna", email="anna@example.com")
    unit.archive()

    assert board_client.get(url(unit)).status_code == 404


def test_board_can_count_sms_on_the_unit_form(board_client):
    response = board_client.get(reverse("messaging:sms_count"), {"body": "Hej"})

    assert response.status_code == 200


def test_tag_and_type_choices_are_hidden_unless_chosen(role_client):
    form = role_client("Admin").get("/messages/new/").content.decode()

    assert '<div data-scope-only="tag" hidden>' in form
    assert '<div data-scope-only="unit_type" hidden>' in form
