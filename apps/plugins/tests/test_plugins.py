from importlib.metadata import EntryPoint

import pytest
from django.apps import apps
from django.core.checks import run_checks
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse

from apps.messaging.registry import provider_for, registry
from apps.plugins import api
from apps.plugins.hooks import UNIT_PANELS, hooks
from config.plugins import GROUP, app_for, available, enabled_apps, enabled_names


def entry_point(name, value):
    return EntryPoint(name=name, value=value, group=GROUP)


def test_the_example_plugin_is_found_through_its_entry_point():
    assert app_for(available()["example"]) == "metra_example_plugin"
    assert apps.is_installed("metra_example_plugin")


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
    config = apps.get_app_config("metra_example_plugin")
    assert "plugins.W001" not in [w.id for w in run_checks()]

    monkeypatch.delattr(type(config), "personal_data")

    assert [w.id for w in run_checks()].count("plugins.W001") == 1


def test_plugins_must_declare_the_api_versions_they_work_with(monkeypatch):
    config = apps.get_app_config("metra_example_plugin")
    assert "plugins.W002" not in [w.id for w in run_checks()]

    monkeypatch.delattr(type(config), "metra_api")

    assert [w.id for w in run_checks()].count("plugins.W002") == 1


def test_a_plugin_for_another_api_version_stops_the_app(monkeypatch):
    config = apps.get_app_config("metra_example_plugin")
    monkeypatch.setattr(type(config), "metra_api", [api.API_VERSION + 1])

    errors = [e for e in run_checks() if e.id == "plugins.E001"]

    assert len(errors) == 1
    assert errors[0].is_serious()
    assert "metra_example_plugin" in errors[0].msg


def test_a_plugin_supporting_several_api_versions_loads(monkeypatch):
    config = apps.get_app_config("metra_example_plugin")
    monkeypatch.setattr(type(config), "metra_api", [api.API_VERSION, api.API_VERSION + 1])

    assert "plugins.E001" not in [e.id for e in run_checks()]


def test_bundled_plugins_are_on_unless_disabled():
    found = {"sms": entry_point("sms", "pkg_sms"), "extra": entry_point("extra", "pkg_x")}

    assert enabled_names([], found=found, bundled=("sms",)) == ["sms"]
    assert enabled_names(["extra", "sms"], found=found, bundled=("sms",)) == ["sms", "extra"]
    assert enabled_names([], disabled=["sms"], found=found, bundled=("sms",)) == []
    # A bundled plugin that is not installed is skipped, not an error.
    assert enabled_names([], found={}, bundled=("sms",)) == []


def test_events_are_sent_after_commit(django_capture_on_commit_callbacks, household):
    from apps.register.models import Person, Unit

    seen = []

    def receiver(sender, **kwargs):
        seen.append(kwargs)

    api.events.unit_saved.connect(receiver)
    api.events.person_saved.connect(receiver)
    try:
        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            unit = Unit.objects.create(unit_type=household, name="Byvägen 4")
            assert seen == []  # nothing before the commit
        for callback in callbacks:
            callback()
        with django_capture_on_commit_callbacks(execute=True):
            person = Person.objects.create(first_name="Anna")
            person.first_name = "Anne"
            person.save()
    finally:
        api.events.unit_saved.disconnect(receiver)
        api.events.person_saved.disconnect(receiver)

    assert seen == [
        {"unit": unit, "created": True, "signal": api.events.unit_saved},
        {"person": person, "created": True, "signal": api.events.person_saved},
        {"person": person, "created": False, "signal": api.events.person_saved},
    ]


def test_a_failing_receiver_does_not_break_the_change(
    db, django_capture_on_commit_callbacks, caplog
):
    from apps.register.models import Person

    def broken(sender, **kwargs):
        raise RuntimeError("plugin bug")

    api.events.person_saved.connect(broken)
    try:
        with django_capture_on_commit_callbacks(execute=True):
            Person.objects.create(first_name="Anna")
    finally:
        api.events.person_saved.disconnect(broken)

    assert Person.objects.count() == 1
    assert "Plugin event receiver" in caplog.text


def test_settings_page_lists_plugin_links(client, make_user, settings):
    settings.REQUIRE_MFA = False
    client.force_login(make_user("root", "Admin", is_staff=True))

    page = client.get(reverse("admin:index")).content.decode()

    assert 'href="/plugins/example/">Example plugin</a>' in page
    assert "What the example plugin adds." in page


def test_grant_to_roles_gives_and_takes_permissions(db):
    from django.apps import apps as global_apps
    from django.contrib.auth.models import Group, Permission

    operation = api.grant_to_roles({"Read-only": ["register.change_unit"], "Nobody": ["x.y"]})
    change_unit = Permission.objects.get(codename="change_unit")
    readonly = Group.objects.get(name="Read-only")

    operation.code(global_apps, None)
    assert change_unit in readonly.permissions.all()

    operation.reverse_code(global_apps, None)
    assert change_unit not in readonly.permissions.all()


def test_old_names_from_before_the_rename_get_a_warning(settings, monkeypatch):
    from django.core.checks import run_checks

    import config.plugins

    settings.LEGACY_SETTING_NAMES = ["SCR_DOMAIN"]
    monkeypatch.setattr(config.plugins, "legacy_plugins", lambda: ["old"])

    ids = [message.id for message in run_checks()]

    assert "core.W001" in ids and "plugins.W003" in ids


def test_no_warning_without_old_names(settings):
    from django.core.checks import run_checks

    settings.LEGACY_SETTING_NAMES = []

    assert "core.W001" not in [message.id for message in run_checks()]
