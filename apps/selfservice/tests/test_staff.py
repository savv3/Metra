import pytest
from auditlog.models import LogEntry
from django.urls import reverse

from apps.register.models import Person, Unit, UnitContact
from apps.selfservice.models import SelfServiceLink


def test_print_letters_makes_links_and_shows_qr_codes(board_client, unit, owner, open_round):
    response = board_client.post(
        reverse("selfservice:round_print", args=[open_round.pk]),
        {"scope": "all", "layout": "letters"},
        HTTP_ACCEPT_LANGUAGE="en",
    )

    body = response.content.decode()
    link = SelfServiceLink.objects.get()
    assert "no-store" in response["Cache-Control"]
    assert "<svg" in body
    assert "https://register.example.com/m/" in body
    assert "Anna Lindqvist" in body
    assert link.round == open_round
    assert link.created_by.username == "board"


def test_print_list_for_units_without_phone_or_email(
    board_client, unit, owner, household, open_round
):
    paper = Person.objects.create(first_name="Paper", last_name="Only")
    other = Unit.objects.create(unit_type=household, name="Strandvägen 9")
    UnitContact.objects.create(unit=other, person=paper, role="owner")

    response = board_client.post(
        reverse("selfservice:round_print", args=[open_round.pk]),
        {"scope": "unreachable", "layout": "list"},
    )

    assert [link.unit for link in SelfServiceLink.objects.all()] == [other]
    assert 'class="link-list"' in response.content.decode()


def test_print_for_missing_skips_units_that_reported(board_client, unit, owner, open_round):
    from apps.readings.models import Reading

    Reading.objects.create(round=open_round, unit=unit, value=1)

    board_client.post(
        reverse("selfservice:round_print", args=[open_round.pk]), {"scope": "missing"}
    )

    assert not SelfServiceLink.objects.exists()


def test_print_reports_units_without_contacts(board_client, unit, open_round):
    response = board_client.post(
        reverse("selfservice:round_print", args=[open_round.pk]),
        {"scope": "all"},
        HTTP_ACCEPT_LANGUAGE="en",
    )

    assert "have no contact person" in response.content.decode()


def test_unit_letter_uses_the_open_round(board_client, unit, owner, open_round):
    board_client.post(reverse("selfservice:unit_print", args=[unit.pk]))

    assert SelfServiceLink.objects.get().round == open_round


def test_unit_letter_needs_a_contact(board_client, unit):
    response = board_client.post(reverse("selfservice:unit_print", args=[unit.pk]))

    assert response.status_code == 302
    assert not SelfServiceLink.objects.exists()


def test_revoke_one_and_all(board_client, issued, unit, owner, open_round):
    link, token, _url = issued

    board_client.post(reverse("selfservice:link_revoke", args=[link.pk]))
    assert SelfServiceLink.find(token) is None

    _second, second_token = SelfServiceLink.create_for(unit, owner, open_round)
    board_client.post(reverse("selfservice:round_revoke", args=[open_round.pk]))
    assert SelfServiceLink.find(second_token) is None


def test_round_links_page_lists_links_without_tokens(board_client, issued, open_round):
    _link, token, _url = issued

    page = board_client.get(reverse("selfservice:round_links", args=[open_round.pk]))

    assert page.status_code == 200
    assert "Anna Lindqvist" in page.content.decode()
    assert token not in page.content.decode()


def test_recent_changes_lists_member_corrections(board_client, client, issued, owner):
    _link, _token, url = issued
    client.post(
        url,
        {"action": "contact", "email": "new@example.com", "city": "Jomala"},
    )
    client.post(url, {"action": "reading", "value": "77"})

    page = board_client.get(reverse("selfservice:recent_changes"), HTTP_ACCEPT_LANGUAGE="en")

    body = page.content.decode()
    assert "anna@example.com &rarr; new@example.com" in body
    assert "77" in body
    assert LogEntry.objects.filter(additional_data__has_key="self_service_link").count() >= 2


def test_unit_page_shows_links_and_print_button(board_client, issued, unit):
    page = board_client.get(unit.get_absolute_url(), HTTP_ACCEPT_LANGUAGE="en").content.decode()

    assert reverse("selfservice:unit_print", args=[unit.pk]) in page
    assert "Link for Anna Lindqvist" in page


@pytest.fixture
def urls(issued, unit, open_round):
    link, _token, _url = issued
    return {
        "round_links": ("get", reverse("selfservice:round_links", args=[open_round.pk])),
        "round_print": ("post", reverse("selfservice:round_print", args=[open_round.pk])),
        "round_revoke": ("post", reverse("selfservice:round_revoke", args=[open_round.pk])),
        "unit_print": ("post", reverse("selfservice:unit_print", args=[unit.pk])),
        "link_revoke": ("post", reverse("selfservice:link_revoke", args=[link.pk])),
    }


@pytest.mark.parametrize("role", ["Treasurer", "Read-only"])
def test_viewing_roles_cannot_make_or_stop_links(role_client, urls, role):
    client = role_client(role)

    for name, (method, url) in urls.items():
        status = getattr(client, method)(url).status_code
        assert status == (200 if name == "round_links" else 403), name


@pytest.mark.parametrize("role", ["Board", "Admin"])
def test_board_and_admin_can_manage_links(role_client, urls, role):
    client = role_client(role)

    for name, (method, url) in urls.items():
        assert getattr(client, method)(url).status_code in (200, 302), name


def test_recent_changes_needs_audit_permission(role_client):
    assert role_client("Read-only").get(reverse("selfservice:recent_changes")).status_code == 403
