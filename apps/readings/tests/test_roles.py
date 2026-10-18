import pytest
from django.urls import reverse

from apps.readings.models import Reading


@pytest.fixture
def urls(round_, unit):
    return {
        "round_list": ("get", reverse("readings:round_list")),
        "round_detail": ("get", round_.get_absolute_url()),
        "round_export": ("get", reverse("readings:round_export", args=[round_.pk])),
        "round_create": ("get", reverse("readings:round_create")),
        "round_edit": ("get", reverse("readings:round_edit", args=[round_.pk])),
        "reading_entry": (
            "get",
            reverse("readings:reading_entry", args=[round_.pk, unit.pk]),
        ),
    }


VIEWING = {"round_list", "round_detail", "round_export"}


@pytest.mark.parametrize("role", ["Treasurer", "Read-only"])
def test_viewing_roles_can_only_view(role_client, urls, role):
    client = role_client(role)

    for name, (method, url) in urls.items():
        status = getattr(client, method)(url).status_code
        assert status == (200 if name in VIEWING else 403), name


@pytest.mark.parametrize("role", ["Board", "Admin"])
def test_board_and_admin_can_edit(role_client, urls, role):
    client = role_client(role)

    for name, (method, url) in urls.items():
        assert getattr(client, method)(url).status_code == 200, name


def test_users_without_a_role_are_refused(client, make_user, urls):
    client.force_login(make_user("nobody"))

    for name, (method, url) in urls.items():
        assert getattr(client, method)(url).status_code == 403, name


def test_read_only_sees_values_but_no_entry_forms(role_client, round_, unit):
    Reading.objects.create(round=round_, unit=unit, value=42)
    client = role_client("Read-only")

    page = client.get(round_.get_absolute_url()).content.decode()
    unit_page = client.get(unit.get_absolute_url()).content.decode()

    assert "42 m³" in page
    assert reverse("readings:reading_entry", args=[round_.pk, unit.pk]) not in page
    assert reverse("readings:reading_entry", args=[round_.pk, unit.pk]) not in unit_page
    assert (
        reverse("readings:round_create")
        not in client.get(reverse("readings:round_list")).content.decode()
    )
