import pytest
from auditlog.models import LogEntry
from django.contrib.auth.models import Group
from django.urls import reverse

from apps.register.models import Tag, Unit, UnitContact


def entries_for(obj, action=None):
    entries = LogEntry.objects.get_for_object(obj)
    return entries.filter(action=action) if action is not None else entries


def test_edit_is_logged_with_actor_and_field_changes(board_client, unit):
    board_client.post(
        reverse("register:unit_edit", args=[unit.pk]),
        {
            "name": "Byvägen 4 A",
            "status": "active",
            "country": "FI",
            "custom__meter_number": "M-200",
        },
    )

    entry = entries_for(unit, LogEntry.Action.UPDATE).get()
    assert entry.actor.username == "board"
    assert entry.changes_dict["name"] == ["Byvägen 4", "Byvägen 4 A"]
    assert entry.changes_dict["custom_data"][1]["meter_number"] == "M-200"
    assert "updated_at" not in entry.changes_dict


def test_create_and_archive_are_logged(board_client, household):
    board_client.post(
        reverse("register:unit_create") + f"?type={household.pk}",
        {
            "unit_type": household.pk,
            "name": "Ny",
            "status": "active",
            "country": "FI",
            "custom__meter_number": "M-1",
        },
    )
    unit = Unit.objects.get(name="Ny")
    board_client.post(reverse("register:unit_archive", args=[unit.pk]))

    assert entries_for(unit, LogEntry.Action.CREATE).get().actor.username == "board"
    archived = entries_for(unit, LogEntry.Action.UPDATE).get()
    assert archived.changes_dict["archived_at"][0] is None


def test_tag_changes_are_logged(unit):
    tag = Tag.objects.create(name="North")

    unit.tags.add(tag)

    change = entries_for(unit, LogEntry.Action.UPDATE).get().changes_dict["tags"]
    assert change == {"type": "m2m", "operation": "add", "objects": ["North"]}
    assert entries_for(tag, LogEntry.Action.CREATE).exists()


def test_contact_links_are_logged_for_unit_and_person(board_client, unit, person):
    board_client.post(
        reverse("register:unit_contact_add", args=[unit.pk]),
        {"person": person.pk, "role": "owner"},
    )
    contact = UnitContact.objects.get()
    board_client.post(reverse("register:unit_contact_remove", args=[unit.pk, contact.pk]))

    entries = LogEntry.objects.filter(additional_data__unit_id=unit.pk)
    assert list(entries.values_list("action", flat=True)) == [
        LogEntry.Action.DELETE,
        LogEntry.Action.CREATE,
    ]
    assert all(e.additional_data["person_id"] == person.pk for e in entries)


def test_deleting_in_settings_is_logged(person):
    pk = person.pk
    person.delete()

    assert LogEntry.objects.filter(object_id=pk, action=LogEntry.Action.DELETE).exists()


def test_viewing_a_record_is_logged(role_client, unit, person):
    client = role_client("Read-only")

    client.get(unit.get_absolute_url())
    client.get(person.get_absolute_url())

    for obj in (unit, person):
        assert entries_for(obj, LogEntry.Action.ACCESS).get().actor.username == "read-only"


def test_role_changes_are_logged(make_user):
    user = make_user("someone")

    user.groups.add(Group.objects.get(name="Board"))

    change = entries_for(user, LogEntry.Action.UPDATE).get().changes_dict["groups"]
    assert change["objects"] == ["Board"]
    assert "password" not in entries_for(user, LogEntry.Action.CREATE).get().changes_dict


def test_board_sees_history_on_unit_and_person_pages(board_client, unit, person):
    board_client.post(
        reverse("register:unit_contact_add", args=[unit.pk]),
        {"person": person.pk, "role": "owner"},
    )
    board_client.post(
        reverse("register:person_edit", args=[person.pk]),
        {
            "first_name": "Annika",
            "last_name": "Lindqvist",
            "email": "anna@example.com",
            "preferred_channel": "email",
            "country": "FI",
        },
    )

    unit_page = board_client.get(unit.get_absolute_url(), HTTP_ACCEPT_LANGUAGE="en")
    person_page = board_client.get(person.get_absolute_url(), HTTP_ACCEPT_LANGUAGE="en")

    assert "Contact added" in unit_page.content.decode()
    person_html = person_page.content.decode()
    assert "Contact added" in person_html
    assert "Anna &rarr; Annika" in person_html
    assert "Recently viewed by" in person_html


@pytest.mark.parametrize("role", ["Treasurer", "Read-only"])
def test_other_roles_do_not_see_history(role_client, unit, role):
    page = role_client(role).get(unit.get_absolute_url(), HTTP_ACCEPT_LANGUAGE="en")

    assert "Recently viewed by" not in page.content.decode()


def test_settings_shows_a_records_audit_history(client, make_user, unit):
    from allauth.mfa.totp.internal.auth import TOTP, generate_totp_secret

    admin = make_user("admin", "Admin", is_staff=True)
    TOTP.activate(admin, generate_totp_secret())
    client.force_login(admin)

    response = client.get(reverse("admin:register_unit_auditlog", args=[unit.pk]))

    assert response.status_code == 200
    assert "Byvägen 4" in response.content.decode()
