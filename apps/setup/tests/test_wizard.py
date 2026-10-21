import re

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import RequestFactory
from django.urls import reverse

from apps.accounts.adapter import AccountAdapter
from apps.invoicing.models import BillingSettings
from apps.messaging import providers
from apps.readings.models import ReadingType
from apps.register.models import CustomField, Organisation, UnitType
from apps.setup import examples
from apps.setup.models import SetupState

pytestmark = pytest.mark.django_db

User = get_user_model()


def url(name):
    return reverse("setup:step", args=[name])


@pytest.fixture
def admin_client(role_client):
    return role_client("Admin")


def login_redirect(user):
    request = RequestFactory().get("/")
    request.user = user
    return AccountAdapter().get_login_redirect_url(request)


def test_admin_starts_in_the_wizard_until_it_is_finished(make_user, admin_client):
    admin = make_user("first", "Admin")
    board = make_user("board", "Board")

    assert login_redirect(admin) == reverse("setup:start")
    assert login_redirect(board) != reverse("setup:start")

    admin_client.post(reverse("setup:finish"))

    assert SetupState.current().finished_at is not None
    assert login_redirect(admin) != reverse("setup:start")


def test_only_admins_can_run_it(role_client):
    for role in ["Board", "Treasurer", "Read-only"]:
        client = role_client(role)
        assert client.get(url("organisation")).status_code == 403, role
        assert client.post(reverse("setup:finish")).status_code == 403, role


def test_steps_are_listed_and_can_be_skipped(admin_client):
    page = admin_client.get(reverse("setup:start"), follow=True, HTTP_ACCEPT_LANGUAGE="en")
    body = page.content.decode()

    assert "Step 1 of 7" in body
    assert f'href="{url("language")}">Skip this step' in body
    assert admin_client.get("/setup/nonsense/").status_code == 404
    assert not Organisation.objects.exists()  # nothing changes until a step is saved


def test_organisation_step_saves_and_moves_on(admin_client):
    response = admin_client.post(
        url("organisation"),
        {"name": "Byns vattenandelslag", "country": "AX", "email": "styrelsen@example.com"},
    )

    assert response.url == url("language")
    assert Organisation.current().name == "Byns vattenandelslag"
    assert "organisation" in SetupState.current().saved_steps

    admin_client.post(url("organisation"), {"name": "Byns vatten r.f.", "country": "AX"})
    assert Organisation.objects.get().name == "Byns vatten r.f."


def test_language_step_sets_the_admins_language(admin_client):
    response = admin_client.post(url("language"), {"language": "fi"})

    assert response.cookies["django_language"].value == "fi"


def test_logo_step(admin_client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    Organisation.objects.create(name="Byns vatten")
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20

    from django.core.files.uploadedfile import SimpleUploadedFile

    admin_client.post(url("logo"), {"logo": SimpleUploadedFile("logo.png", png, "image/png")})
    assert Organisation.current().logo

    admin_client.post(url("logo"), {"remove": "1"})
    assert not Organisation.current().logo


def test_water_association_example_can_be_added_twice(admin_client):
    admin_client.post(url("types"), {"action": "example"}, HTTP_ACCEPT_LANGUAGE="en")
    admin_client.post(url("types"), {"action": "example"}, HTTP_ACCEPT_LANGUAGE="en")

    household = UnitType.objects.get()
    keys = list(household.custom_fields.values_list("key", flat=True))
    assert keys == ["property_id", "meter_number", "connected_year", "connection", "residents"]
    meter = ReadingType.objects.get()
    assert meter.unit_type == household and meter.cumulative and meter.unit_label == "m³"


def test_example_names_follow_the_language():
    from django.utils import translation

    with translation.override("sv"):
        assert examples.water_association().name == "Hushåll"


def test_unit_types_and_fields_can_be_added(admin_client):
    admin_client.post(url("types"), {"action": "type", "type-name": "Båtplats"})
    berth = UnitType.objects.get(name="Båtplats")

    admin_client.post(
        url("types"),
        {
            "action": "field",
            "field-applies_to": str(berth.pk),
            "field-label": "Båtens längd",
            "field-field_type": "number",
        },
    )
    admin_client.post(
        url("types"),
        {
            "action": "field",
            "field-applies_to": "person",
            "field-label": "Medlemsnummer",
            "field-field_type": "text",
        },
    )
    again = admin_client.post(
        url("types"),
        {
            "action": "field",
            "field-applies_to": "person",
            "field-label": "Medlemsnummer",
            "field-field_type": "text",
        },
        HTTP_ACCEPT_LANGUAGE="en",
    )

    assert berth.custom_fields.get().key == "batens_langd"
    assert CustomField.objects.get(target="person").unit_type is None
    assert "There is already a field with this name." in again.content.decode()
    assert CustomField.objects.count() == 2


def test_test_messages(admin_client):
    admin_client.post(url("messaging"), {"channel": "email", "to": "me@example.com"})
    admin_client.post(url("messaging"), {"channel": "sms", "to": "0401234567"})

    assert mail.outbox[0].to == ["me@example.com"]
    assert providers.outbox[0]["to"] == "0401234567"
    assert "messaging" in SetupState.current().saved_steps


def test_invoicing_step(admin_client):
    admin_client.post(
        url("invoicing"),
        {
            "vat_registered": "",
            "vat_exemption_text": "Ej momspliktig",
            "default_vat_rate": "25.5",
            "iban": "FI2112345600000785",
            "bic": "NDEAFIHH",
            "payment_terms_days": "21",
            "reference_type": BillingSettings.ReferenceType.values[0],
            "number_prefix": "",
            "next_number": "1",
            "late_interest_text": "Dröjsmålsränta enligt räntelagen.",
            "footer": "",
            "reminder_fee": "0",
            "reminder_days": "14",
        },
    )

    billing = BillingSettings.current()
    assert billing.iban == "FI2112345600000785"
    assert billing.payment_terms_days == 21


def test_inviting_a_board_member(admin_client, client):
    Organisation.objects.create(name="Byns vatten")
    from django.contrib.auth.models import Group

    board = Group.objects.get(name="Board")

    admin_client.post(
        url("board"),
        {"first_name": "Bo", "email": "Bo@Example.com", "role": board.pk},
        HTTP_ACCEPT_LANGUAGE="en",
    )

    user = User.objects.get(username="bo@example.com")
    assert list(user.groups.all()) == [board]
    assert not user.has_usable_password() and not user.is_staff
    email = mail.outbox[0]
    assert email.to == ["bo@example.com"] and "Byns vatten" in email.subject
    link = re.search(r"https?://\S+/accounts/password/reset/key/\S+/", email.body).group(0)

    client.logout()
    page = client.get(link.split("testserver")[1], follow=True)
    assert page.status_code == 200
    assert b"password1" in page.content


def test_an_invitation_needs_working_email(admin_client, settings):
    from django.contrib.auth.models import Group

    settings.MESSAGING = {**settings.MESSAGING, "email_provider": ""}

    response = admin_client.post(
        url("board"),
        {"first_name": "Bo", "email": "bo@example.com", "role": Group.objects.get(name="Board").pk},
    )

    assert response.status_code == 200
    assert not User.objects.filter(username="bo@example.com").exists()


def test_settings_links_to_the_wizard(make_user, client, settings):
    settings.REQUIRE_MFA = False
    client.force_login(make_user("root", "Admin", is_staff=True))

    page = client.get(reverse("core:settings")).content.decode()

    assert reverse("setup:start") in page


def test_existing_installs_are_not_sent_to_the_wizard(make_user):
    """The migration marks a configured install as done; without the row an
    admin would be sent there."""
    admin = make_user("first", "Admin")
    SetupState.objects.create(finished_at="2026-01-01T00:00:00Z")

    assert login_redirect(admin) != reverse("setup:start")
