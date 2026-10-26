import importlib

import pytest
from django.urls import reverse
from django.utils import translation

from apps.register import unitwords
from apps.register.models import Unit, UnitType
from apps.setup import examples


@pytest.fixture
def cabin(db):
    return UnitType.objects.create(name="Stuga", name_plural="Stugor")


def menu(content):
    start = content.index('<nav class="side-nav"')
    return content[start : content.index("</nav>", start)]


def get(client, name, lang="sv", **kwargs):
    return client.get(reverse(name), HTTP_ACCEPT_LANGUAGE=lang, **kwargs).content.decode()


def test_one_type_uses_its_own_names(board_client, cabin):
    Unit.objects.create(unit_type=cabin, name="Strand 1")

    html = get(board_client, "register:unit_list")

    assert ">Stugor</a>" in menu(html)
    assert "<h1>Stugor</h1>" in html
    assert "Lägg till: Stuga" in html
    assert ">Enheter</a>" not in menu(html)
    assert 'id="f-type"' not in html
    assert '<th scope="col">Typ</th>' not in html
    assert "Strand 1" in html


def test_english_variant(board_client):
    UnitType.objects.create(name="Cabin", name_plural="Cabins")

    html = get(board_client, "register:unit_list", lang="en")

    assert ">Cabins</a>" in menu(html)
    assert "<h1>Cabins</h1>" in html
    assert "Add: Cabin" in html


def test_export_link_uses_plural(board_client, cabin):
    Unit.objects.create(unit_type=cabin, name="Strand 1")

    assert "Exportera CSV: 1 Stugor" in get(board_client, "register:unit_list")


def test_two_types_keep_generic_wording(board_client, cabin):
    UnitType.objects.create(name="Brygga", name_plural="Bryggor")
    Unit.objects.create(unit_type=cabin, name="Strand 1")

    html = get(board_client, "register:unit_list")

    assert ">Enheter</a>" in menu(html)
    assert "<h1>Enheter</h1>" in html
    assert 'id="f-type"' in html
    assert '<th scope="col">Typ</th>' in html
    assert "Lägg till enhet" in html


def test_empty_plural_falls_back_to_generic(board_client):
    UnitType.objects.create(name="Stuga")

    html = get(board_client, "register:unit_list")

    assert ">Enheter</a>" in menu(html)
    assert "<h1>Enheter</h1>" in html
    assert 'id="f-type"' not in html


def test_add_title_needs_no_agreement(board_client, cabin):
    response = board_client.get(reverse("register:unit_create"), HTTP_ACCEPT_LANGUAGE="sv")
    html = response.content.decode()

    assert "<h1>Lägg till: Stuga</h1>" in html
    assert "Ny Stuga" not in html

    UnitType.objects.create(name="Brygga")
    response = board_client.get(
        reverse("register:unit_create"), {"type": cabin.pk}, HTTP_ACCEPT_LANGUAGE="fi"
    )
    assert "<h1>Lisää: Stuga</h1>" in response.content.decode()


def test_words_are_cached_per_request(cabin):
    from django.test import RequestFactory

    request = RequestFactory().get("/")
    first = unitwords.words(request)
    assert unitwords.words(request) is first


@pytest.mark.parametrize(("lang", "plural"), [("sv", "Hushåll"), ("en", "Households")])
def test_wizard_example_fills_the_plural(db, lang, plural):
    with translation.override(lang):
        assert examples.water_association().name_plural == plural


def test_migration_adds_an_optional_plural(db):
    migration = importlib.import_module("apps.register.migrations.0003_unittype_name_plural")
    field = migration.Migration.operations[0].field
    assert field.blank
    assert UnitType.objects.create(name="X").name_plural == ""
