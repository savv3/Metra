import pytest
from django.urls import reverse

from apps.register.models import Person, Tag, Unit, UnitContact, UnitType

HTMX = {"HTTP_HX_REQUEST": "true", "HTTP_HX_TARGET": "results"}


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["register:unit_list", "register:person_list"])
def test_register_requires_login(client, name):
    response = client.get(reverse(name))

    assert response.status_code == 302
    assert reverse("account_login") in response.url


def test_unit_search_matches_contact_names(board_client, unit, household, person):
    UnitContact.objects.create(unit=unit, person=person, role="owner")
    Unit.objects.create(unit_type=household, name="Strandvägen 9")

    response = board_client.get(reverse("register:unit_list"), {"q": "lindqvist"})

    assert list(response.context["page"].object_list) == [unit]


def test_unit_list_htmx_returns_only_results(board_client, unit):
    response = board_client.get(reverse("register:unit_list"), {"q": "byv"}, **HTMX)

    assert [t.name for t in response.templates][0] == "register/_unit_results.html"
    assert "Byvägen 4" in response.content.decode()


def test_unit_list_filters_by_tag_and_hides_archived(board_client, unit, household):
    tagged = Unit.objects.create(unit_type=household, name="Tagged")
    tag = Tag.objects.create(name="North")
    tagged.tags.add(tag)
    unit.archive()

    by_tag = board_client.get(reverse("register:unit_list"), {"tag": tag.pk})
    default = board_client.get(reverse("register:unit_list"))
    archived = board_client.get(reverse("register:unit_list"), {"show": "archived"})

    assert list(by_tag.context["page"].object_list) == [tagged]
    assert list(default.context["page"].object_list) == [tagged]
    assert list(archived.context["page"].object_list) == [unit]


def test_create_unit_with_custom_fields(board_client, household):
    response = board_client.post(
        reverse("register:unit_create") + f"?type={household.pk}",
        {
            "unit_type": household.pk,
            "name": "Ny",
            "status": "active",
            "country": "AX",
            "custom__meter_number": "M-9",
        },
    )

    unit = Unit.objects.get(name="Ny")
    assert response.status_code == 302
    assert unit.custom_data == {"meter_number": "M-9"}


def test_create_unit_asks_for_type_when_several_exist(board_client, household):
    UnitType.objects.create(name="Client")

    response = board_client.get(reverse("register:unit_create"))

    assert "register/unit_type_choose.html" in [t.name for t in response.templates]


def test_unit_detail_shows_custom_values_and_contacts(board_client, unit, person):
    UnitContact.objects.create(unit=unit, person=person, role="owner")

    response = board_client.get(unit.get_absolute_url())

    body = response.content.decode()
    assert "M-100" in body
    assert "Anna Lindqvist" in body


def test_edit_unit(board_client, unit):
    board_client.post(
        reverse("register:unit_edit", args=[unit.pk]),
        {"name": "Renamed", "status": "inactive", "country": "AX", "custom__meter_number": "M-1"},
    )

    unit.refresh_from_db()
    assert (unit.name, unit.status) == ("Renamed", "inactive")


def test_archive_toggle_requires_post(board_client, unit):
    url = reverse("register:unit_archive", args=[unit.pk])

    assert board_client.get(url).status_code == 405
    board_client.post(url)
    unit.refresh_from_db()
    assert unit.is_archived
    board_client.post(url)
    unit.refresh_from_db()
    assert not unit.is_archived


def test_add_and_remove_contact(board_client, unit, person):
    board_client.post(
        reverse("register:unit_contact_add", args=[unit.pk]),
        {"person": person.pk, "role": "billing"},
    )
    contact = UnitContact.objects.get()
    assert contact.role == "billing"

    board_client.post(reverse("register:unit_contact_remove", args=[unit.pk, contact.pk]))
    assert not UnitContact.objects.exists()


def test_create_person_for_unit_links_them(board_client, unit):
    board_client.post(
        reverse("register:person_create") + f"?unit={unit.pk}",
        {
            "first_name": "Bo",
            "preferred_channel": "post",
            "country": "AX",
            "for_unit": unit.pk,
            "role": "owner",
        },
    )

    person = Person.objects.get(first_name="Bo")
    assert UnitContact.objects.get(person=person).unit == unit


def test_person_list_search_and_detail(board_client, person, unit):
    UnitContact.objects.create(unit=unit, person=person, role="owner")

    found = board_client.get(reverse("register:person_list"), {"q": "anna@"})
    detail = board_client.get(person.get_absolute_url())

    assert list(found.context["page"].object_list) == [person]
    assert "Byvägen 4" in detail.content.decode()
