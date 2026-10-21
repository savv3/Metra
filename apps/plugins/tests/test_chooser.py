import pytest
from auditlog.models import LogEntry
from django.urls import reverse
from metra_example_plugin import apps as example

from apps.messaging.registry import registry
from apps.plugins import api, state
from apps.plugins.hooks import NAVIGATION, SETTINGS_LINKS, UNIT_PANELS, hooks
from apps.plugins.models import PluginSetting, PluginState

LIST = reverse("plugins:list")
SETTINGS = reverse("plugins:settings", args=["example"])


@pytest.fixture(autouse=True)
def english(settings):
    settings.LANGUAGE_CODE = "en"


def turn(client, name, on):
    return client.post(
        reverse("plugins:toggle", args=[name]), {"enabled": "1" if on else "0"}, follow=True
    )


def test_items_know_the_plugin_that_added_them(db):
    labels = {hooks.owner(item): item.label for item in hooks.get(NAVIGATION)}
    assert labels["example"] == "Example"
    assert registry._providers["sms"]["example-log"].plugin == "example"
    assert registry._providers["sms"]["console"].plugin is None


def test_admin_turns_a_plugin_off_and_on(role_client, unit):
    client = role_client("Admin")

    response = turn(client, "example", on=False)

    assert "Example plugin is off. Its data is kept." in response.content.decode()
    assert not state.is_enabled("example")
    assert not [i for i in hooks.get(NAVIGATION) if hooks.owner(i) == "example"]
    assert not [i for i in hooks.get(UNIT_PANELS) if hooks.owner(i) == "example"]
    assert not [i for i in hooks.get(SETTINGS_LINKS) if hooks.owner(i) == "example"]
    assert "example-log" not in registry.names("sms")
    page = client.get(unit.get_absolute_url()).content.decode()
    assert "/plugins/example/" not in page
    assert "Example panel" not in page
    assert client.get("/plugins/example/").status_code == 404

    turn(client, "example", on=True)

    assert state.is_enabled("example")
    assert "Example panel" in client.get(unit.get_absolute_url()).content.decode()
    assert client.get("/plugins/example/").status_code == 200
    assert "example-log" in registry.names("sms")
    assert PluginState.objects.get(name="example").changed_by.username == "admin"


def test_events_skip_receivers_of_a_plugin_that_is_off(db, django_capture_on_commit_callbacks):
    example.issued.clear()
    PluginState.objects.create(name="example", enabled=False)
    state.forget()

    with django_capture_on_commit_callbacks(execute=True):
        api.events.send_on_commit(
            api.events.invoice_issued, None, invoice=type("I", (), {"number": "7"})
        )

    assert example.issued == []
    PluginState.objects.filter(name="example").update(enabled=True)
    state.forget()
    with django_capture_on_commit_callbacks(execute=True):
        api.events.send_on_commit(
            api.events.invoice_issued, None, invoice=type("I", (), {"number": "8"})
        )
    assert example.issued == ["8"]


def test_the_plugins_page_lists_installed_plugins(role_client):
    page = role_client("Admin").get(LIST).content.decode()

    assert "Example plugin" in page
    assert "46elks SMS" in page
    assert SETTINGS in page


def test_only_admins_choose_plugins(role_client, db):
    for role in ["Board", "Treasurer", "Read-only"]:
        client = role_client(role)
        assert client.get(LIST).status_code == 403
        assert turn(client, "example", on=False).status_code == 403
        assert client.get(SETTINGS).status_code == 403
    assert state.is_enabled("example")


def test_settings_page_links_to_plugins_for_admins(role_client, settings):
    settings.REQUIRE_MFA = False
    admin = role_client("Admin")

    assert LIST in admin.get(reverse("core:settings")).content.decode()


def test_unknown_plugins_are_not_found(role_client):
    client = role_client("Admin")

    assert turn(client, "nope", on=False).status_code == 404
    assert client.get(reverse("plugins:settings", args=["46elks"])).status_code in (200, 404)
    assert client.get(reverse("plugins:settings", args=["nope"])).status_code == 404


# Plugin settings


def test_settings_default_save_and_reach_the_plugin(role_client, unit):
    client = role_client("Admin")
    assert "Hello!" in client.get("/plugins/example/").content.decode()

    response = client.post(
        SETTINGS, {"greeting": "Hej", "loud": "on", "times": "3", "api_key": "s3cret"}, follow=True
    )

    assert "Saved the settings." in response.content.decode()
    values = api.plugin_settings("example")
    assert values.get("greeting") == "Hej"
    assert values.get("loud") is True
    assert values.get("times") == 3
    assert values.get("api_key") == "s3cret"
    assert "HEJ!" in client.get("/plugins/example/").content.decode()


def test_secrets_are_encrypted_never_shown_and_kept_when_left_empty(role_client, db):
    client = role_client("Admin")
    client.post(SETTINGS, {"greeting": "Hej", "times": "1", "api_key": "s3cret"})
    stored = PluginSetting.objects.get(plugin="example", key="api_key").value

    assert "s3cret" not in stored
    page = client.get(SETTINGS).content.decode()
    assert "s3cret" not in page
    assert stored not in page
    assert "A value is saved. Leave this empty to keep it." in page

    client.post(SETTINGS, {"greeting": "Hej", "times": "1", "api_key": ""})
    assert api.plugin_settings("example").get("api_key") == "s3cret"

    client.post(SETTINGS, {"greeting": "Hej", "times": "1", "api_key__clear": "on"})
    assert api.plugin_settings("example").get("api_key") is None


def test_the_audit_log_names_the_setting_but_not_the_value(role_client, db):
    role_client("Admin").post(SETTINGS, {"greeting": "Hej", "times": "1", "api_key": "s3cret"})

    entries = LogEntry.objects.get_for_model(PluginSetting)
    assert {entry.object_repr for entry in entries} == {
        "example: greeting",
        "example: api_key",
        "example: times",
    }
    text = " ".join(str(entry.changes) for entry in entries)
    assert "api_key" in text
    assert "s3cret" not in text
    assert "Hej" not in text


def test_the_environment_wins_and_locks_the_field(role_client, monkeypatch, db):
    monkeypatch.setenv("METRA_EXAMPLE_TIMES", "5")
    client = role_client("Admin")

    page = client.get(SETTINGS).content.decode()
    client.post(SETTINGS, {"greeting": "Hej", "times": "2"})

    assert "Set in the server environment (METRA_EXAMPLE_TIMES)" in page
    assert api.plugin_settings("example").get("times") == 5
    assert not PluginSetting.objects.filter(key="times").exists()


def test_a_secret_saved_with_another_key_must_be_entered_again(role_client, settings, db):
    client = role_client("Admin")
    client.post(SETTINGS, {"greeting": "Hej", "times": "1", "api_key": "s3cret"})

    settings.SETTINGS_KEY = "another server"

    assert api.plugin_settings("example").get("api_key") is None
    assert "cannot be read with this server" in client.get(SETTINGS).content.decode()


def test_a_plugin_reads_its_own_settings_without_naming_itself(db):
    from metra_example_plugin import views

    assert views.api.plugin_settings("example").get("greeting") == "Hello"
