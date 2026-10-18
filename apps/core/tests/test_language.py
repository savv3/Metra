import pytest
from django.urls import reverse

from apps.register.models import Organisation

pytestmark = pytest.mark.django_db

NOTICE = 'class="message machine-translation"'


def test_finnish_is_offered_in_the_language_menu(client):
    body = client.get(reverse("core:home")).content.decode()

    assert '<option value="fi"' in body


def test_finnish_pages_say_the_translation_is_machine_made(client):
    client.post(reverse("set_language"), {"language": "fi", "next": "/"})

    body = client.get(reverse("core:home")).content.decode()

    assert '<html lang="fi">' in body
    assert NOTICE in body
    assert "automaattisesti" in body


@pytest.mark.parametrize("language", ["sv", "en"])
def test_reviewed_languages_have_no_notice(client, language):
    client.post(reverse("set_language"), {"language": language, "next": "/"})

    assert NOTICE not in client.get(reverse("core:home")).content.decode()


def test_member_pages_can_switch_to_finnish(client):
    Organisation.objects.create(name="Byns vattenandelslag r.f.")

    assert client.get("/?lang=fi").status_code == 302
    body = client.get("/").content.decode()
    assert '<html lang="fi">' in body
    assert NOTICE in body
