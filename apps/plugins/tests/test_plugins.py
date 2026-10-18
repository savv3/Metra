from importlib.metadata import EntryPoint

import pytest
from django.apps import apps
from django.core.checks import run_checks
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse

from apps.messaging.registry import provider_for, registry
from apps.plugins import api
from apps.plugins.hooks import UNIT_PANELS, hooks
from config.plugins import GROUP, app_for, available, enabled_apps


def entry_point(name, value):
    return EntryPoint(name=name, value=value, group=GROUP)


def test_the_example_plugin_is_found_through_its_entry_point():
    assert app_for(available()["example"]) == "scr_example_plugin"
    assert apps.is_installed("scr_example_plugin")


def test_only_listed_plugins_are_enabled():
    found = {"a": entry_point("a", "pkg_a"), "b": entry_point("b", "pkg_b.apps:BConfig")}

    assert enabled_apps([], found) == {}
    assert enabled_apps(["b"], found) == {"b": "pkg_b.apps.BConfig"}


def test_an_unknown_plugin_name_stops_startup():
    with pytest.raises(ImproperlyConfigured, match="nope"):
        enabled_apps(["nope"], {"example": entry_point("example", "x")})


def test_plugin_menu_item_shows_for_users_with_the_permission(board_client, client, make_user):
    page = board_client.get(reverse("register:unit_list")).content.decode()
    client.force_login(make_user("nobody"))
    other = client.get(reverse("register:unit_list"))

    assert '<a href="/plugins/example/">Example</a>' in page
    assert "/plugins/example/" not in other.content.decode()


def test_plugin_page_is_mounted_under_its_name(board_client, unit):
    response = board_client.get("/plugins/example/")

    assert response.status_code == 200
    assert "The register has 1 active units." in response.content.decode()


def test_plugin_panel_on_unit_page(board_client, unit):
    page = board_client.get(unit.get_absolute_url()).content.decode()

    assert "Example panel" in page
    assert "Byvägen 4 has 0 contact links." in page


def test_plugin_sms_provider_can_be_chosen(settings):
    settings.MESSAGING = {**settings.MESSAGING, "sms_provider": "example-log"}

    provider = provider_for("sms")

    assert "example-log" in registry.names("sms")
    assert provider.send("+358401", "Hej").provider_id == "example"


@pytest.fixture
def broken_panel():
    panel = api.Panel("does/not/exist.html", title="Broken")
    api.add_unit_panel(panel)
    yield panel
    hooks._items[UNIT_PANELS].remove(panel)


def test_a_failing_panel_does_not_break_the_page(board_client, unit, broken_panel, settings):
    settings.DEBUG = False

    response = board_client.get(unit.get_absolute_url())

    assert response.status_code == 200
    assert "Example panel" in response.content.decode()


def test_a_failing_panel_shows_its_error_in_development(board_client, unit, broken_panel, settings):
    from django.template import TemplateDoesNotExist

    settings.DEBUG = True

    with pytest.raises(TemplateDoesNotExist):
        board_client.get(unit.get_absolute_url())


def test_unknown_extension_point_is_refused():
    with pytest.raises(ValueError, match="Unknown extension point"):
        hooks.register("nowhere", object())


def test_plugins_must_declare_personal_data(monkeypatch, settings):
    config = apps.get_app_config("scr_example_plugin")
    assert "plugins.W001" not in [w.id for w in run_checks()]

    monkeypatch.delattr(type(config), "personal_data")

    assert [w.id for w in run_checks()].count("plugins.W001") == 1
