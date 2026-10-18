import datetime

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Notice
from apps.register.models import Organisation, validate_logo

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50


@pytest.fixture
def organisation(db):
    return Organisation.objects.create(
        name="Byns vattenandelslag r.f.",
        display_name="Byns vatten",
        description="Vi levererar vatten till 50 hushåll.",
        email="styrelsen@example.com",
        phone="018 123 45",
        emergency_phone="040 999 99 99",
        street_address="Byvägen 1",
        postal_code="22100",
        city="Mariehamn",
        website="https://byns-vatten.example",
        opening_hours="Vardagar 9–16",
    )


def test_public_page_shows_contact_details(client, organisation):
    response = client.get("/", HTTP_ACCEPT_LANGUAGE="en")

    body = response.content.decode()
    assert response.status_code == 200
    assert "<h1>Byns vatten</h1>" in body
    assert "Vi levererar vatten till 50 hushåll." in body
    assert 'href="tel:0409999999"' in body
    assert 'href="mailto:styrelsen@example.com"' in body
    assert "Vardagar 9–16" in body
    assert "byns-vatten.example" in body
    assert reverse("account_login") in body
    assert "X-Robots-Tag" not in response
    assert "noindex" not in body


def test_public_page_is_translated_and_has_language_links(client, organisation):
    swedish = client.get("/").content.decode()
    switched = client.get("/?lang=en")

    assert "Kontakta oss" in swedish
    assert switched.status_code == 302
    assert "Contact us" in client.get("/").content.decode()


def test_public_page_can_be_switched_off(client, organisation):
    organisation.public_page = False
    organisation.save()

    response = client.get("/", HTTP_ACCEPT_LANGUAGE="en")

    assert "Byns vatten" not in response.content.decode()
    assert response["X-Robots-Tag"] == "noindex, nofollow"
    assert "Allow" not in client.get("/robots.txt").content.decode()


def test_staff_are_still_sent_to_the_register(board_client, organisation):
    response = board_client.get("/")

    assert response.url == reverse("register:unit_list")


def test_only_the_public_page_may_be_indexed(client, board_client, organisation):
    robots = client.get("/robots.txt").content.decode()

    assert robots == "User-agent: *\nAllow: /$\nDisallow: /\n"
    assert client.get(reverse("account_login"))["X-Robots-Tag"] == "noindex, nofollow"
    assert board_client.get(reverse("register:unit_list"))["X-Robots-Tag"] == "noindex, nofollow"


def test_current_notices_show_on_public_and_member_pages(client, organisation, unit, person):
    from apps.register.models import UnitContact
    from apps.selfservice.models import SelfServiceLink

    Notice.objects.create(text="Vattnet är avstängt till kl 18.", level="urgent")
    Notice.objects.create(text="Gammal", ends_at=timezone.now() - datetime.timedelta(minutes=1))
    Notice.objects.create(text="Senare", starts_at=timezone.now() + datetime.timedelta(days=1))
    UnitContact.objects.create(unit=unit, person=person, role="owner")
    _link, token = SelfServiceLink.create_for(unit, person)

    public = client.get("/").content.decode()
    member = client.get(f"/m/{token}/").content.decode()

    for page in (public, member):
        assert "Vattnet är avstängt till kl 18." in page
        assert 'role="alert"' in page
        assert "Gammal" not in page and "Senare" not in page
    assert "040 999 99 99" in member


def test_logo_is_served_and_validated(client, organisation, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    organisation.logo = SimpleUploadedFile("logo.png", PNG, content_type="image/png")
    organisation.save()

    response = client.get(reverse("core:logo"))
    page = client.get("/").content.decode()

    assert response["Content-Type"] == "image/png"
    assert b"".join(response.streaming_content) == PNG
    assert 'alt="Byns vatten"' in page
    validate_logo(SimpleUploadedFile("ok.png", PNG))
    for bad in [
        SimpleUploadedFile("logo.svg", b"<svg onload=alert(1)>"),
        SimpleUploadedFile("fake.png", b"<html>not an image</html>"),
        SimpleUploadedFile("big.png", PNG + b"\x00" * (1024 * 1024)),
    ]:
        with pytest.raises(ValidationError):
            validate_logo(bad)


def test_no_logo_is_a_404(client, organisation):
    assert client.get(reverse("core:logo")).status_code == 404


def test_letters_show_the_contact_block(board_client, organisation, unit, person):
    from apps.register.models import UnitContact

    UnitContact.objects.create(unit=unit, person=person, role="owner")

    page = board_client.post(reverse("selfservice:unit_print", args=[unit.pk])).content.decode()

    assert "040 999 99 99" in page
    assert "Byns vatten" in page


def test_organisation_settings_have_the_public_fields(client, make_user, organisation):
    from allauth.mfa.totp.internal.auth import TOTP, generate_totp_secret

    admin = make_user("admin", "Admin", is_staff=True)
    TOTP.activate(admin, generate_totp_secret())
    client.force_login(admin)

    page = client.get(reverse("admin:register_organisation_change", args=[organisation.pk]))

    body = page.content.decode()
    for field in ["public_page", "display_name", "emergency_phone", "opening_hours", "logo"]:
        assert f'name="{field}"' in body


def test_organisation_placeholders_in_messages(organisation):
    from apps.messaging.models import MessageTemplate, organisation_placeholders

    text = MessageTemplate.fill(
        "{organisation}: ring {emergency_phone} eller se {organisation_website}",
        organisation_placeholders(),
    )

    assert text == "Byns vatten: ring 040 999 99 99 eller se https://byns-vatten.example"
