import pytest
from django.contrib.auth.models import Group, Permission
from django.urls import reverse

from apps.register.models import UnitContact


@pytest.fixture
def urls(unit, person):
    contact = UnitContact.objects.create(unit=unit, person=person)
    return {
        "unit_list": ("get", reverse("register:unit_list")),
        "unit_detail": ("get", unit.get_absolute_url()),
        "person_list": ("get", reverse("register:person_list")),
        "person_detail": ("get", person.get_absolute_url()),
        "unit_create": ("get", reverse("register:unit_create")),
        "unit_edit": ("get", reverse("register:unit_edit", args=[unit.pk])),
        "unit_archive": ("post", reverse("register:unit_archive", args=[unit.pk])),
        "contact_add": ("post", reverse("register:unit_contact_add", args=[unit.pk])),
        "contact_remove": (
            "post",
            reverse("register:unit_contact_remove", args=[unit.pk, contact.pk]),
        ),
        "person_create": ("get", reverse("register:person_create")),
        "person_create_for_unit": ("get", reverse("register:person_create") + f"?unit={unit.pk}"),
        "person_edit": ("get", reverse("register:person_edit", args=[person.pk])),
        "person_archive": ("post", reverse("register:person_archive", args=[person.pk])),
    }


VIEWING = {"unit_list", "unit_detail", "person_list", "person_detail"}


@pytest.mark.parametrize("role", ["Treasurer", "Read-only"])
def test_viewing_roles_can_only_view(role_client, urls, role):
    client = role_client(role)

    for name, (method, url) in urls.items():
        status = getattr(client, method)(url).status_code
        if name in VIEWING:
            assert status == 200, name
        else:
            assert status == 403, name


@pytest.mark.parametrize("role", ["Board", "Admin"])
def test_board_and_admin_can_view_and_edit(role_client, urls, role, make_user):
    client = role_client(role)

    for name, (method, url) in urls.items():
        assert getattr(client, method)(url).status_code in (200, 302), name


def test_users_without_a_role_are_refused(client, make_user, urls):
    client.force_login(make_user("nobody"))

    for name, (method, url) in urls.items():
        assert getattr(client, method)(url).status_code == 403, name


def test_refusal_is_a_translated_page(client, make_user):
    client.force_login(make_user("nobody"))

    response = client.get(reverse("register:unit_list"), HTTP_ACCEPT_LANGUAGE="en")

    assert response.status_code == 403
    assert "Your role does not allow you to open this page." in response.content.decode()


def test_read_only_pages_hide_edit_buttons(role_client, unit, person):
    UnitContact.objects.create(unit=unit, person=person)
    client = role_client("Read-only")

    units = client.get(reverse("register:unit_list")).content.decode()
    unit_page = client.get(unit.get_absolute_url()).content.decode()
    person_page = client.get(person.get_absolute_url()).content.decode()

    assert reverse("register:unit_create") not in units
    assert reverse("register:unit_edit", args=[unit.pk]) not in unit_page
    assert reverse("register:unit_archive", args=[unit.pk]) not in unit_page
    assert reverse("register:unit_contact_add", args=[unit.pk]) not in unit_page
    assert "/remove/" not in unit_page
    assert reverse("register:person_edit", args=[person.pk]) not in person_page
    assert reverse("admin:index") not in units


def test_board_pages_show_edit_buttons(board_client, unit):
    page = board_client.get(unit.get_absolute_url()).content.decode()

    assert reverse("register:unit_edit", args=[unit.pk]) in page
    assert reverse("register:unit_contact_add", args=[unit.pk]) in page


def test_only_staff_can_open_settings(board_client):
    assert board_client.get(reverse("admin:index"), follow=True).status_code == 403


@pytest.mark.django_db
def test_roles_have_the_agreed_permissions():
    def codenames(role):
        return set(Group.objects.get(name=role).permissions.values_list("codename", flat=True))

    every = Permission.objects.filter(content_type__app_label__in=["register", "auth", "auditlog"])
    assert set(every.values_list("codename", flat=True)) <= codenames("Admin")
    assert codenames("Treasurer") == codenames("Read-only")
    assert all(name.startswith("view_") for name in codenames("Read-only"))
    assert {"change_unit", "add_person", "delete_unitcontact", "view_logentry"} <= codenames(
        "Board"
    )
    assert not any(
        name.startswith("delete_") for name in codenames("Board") - {"delete_unitcontact"}
    )
    assert "view_logentry" not in codenames("Treasurer")


def test_refusal_page_is_swedish_by_default(client, make_user):
    client.force_login(make_user("nobody"))

    response = client.get(reverse("register:unit_list"))

    assert "Ingen åtkomst" in response.content.decode()
