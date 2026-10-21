import re

import pytest
from django.urls import reverse

from apps.invoicing.models import FeeLine, FeePlan
from apps.register.models import Organisation

pytestmark = pytest.mark.django_db

URL = reverse("core:settings")


@pytest.fixture(autouse=True)
def no_mfa(settings):
    settings.REQUIRE_MFA = False


@pytest.fixture(autouse=True)
def without_example_plugin(monkeypatch):
    """The example plugin, enabled in tests, offers every user a link."""
    from apps.core import settings_page

    links = settings_page.settings_links
    monkeypatch.setattr(
        settings_page,
        "settings_links",
        lambda user: [link for link in links(user) if "/plugins/example/" not in link[0]],
    )


def groups(page):
    return re.findall(r'id="settings-([a-z]+)"', page)


def get(client, user):
    client.force_login(user)
    return client.get(URL, HTTP_ACCEPT_LANGUAGE="en")


def test_admin_sees_every_group_but_advanced(client, make_user):
    page = get(client, make_user("admin", "Admin", is_staff=True)).content.decode()

    assert groups(page) == [
        "organisation",
        "register",
        "readings",
        "invoicing",
        "messages",
        "users",
        "integrations",
        "backups",
        "setup",
    ]
    for url in [
        reverse("admin:register_organisation_add"),
        reverse("admin:register_unittype_changelist"),
        reverse("admin:register_customfield_changelist") + "?target__exact=person",
        reverse("admin:register_tag_changelist"),
        reverse("admin:readings_readingtype_changelist"),
        reverse("admin:invoicing_billingsettings_add"),
        reverse("admin:invoicing_feeplan_changelist"),
        reverse("admin:messaging_messagetemplate_changelist"),
        reverse("admin:core_notice_changelist"),
        reverse("admin:auth_user_changelist"),
        reverse("admin:auth_group_changelist"),
        reverse("backups:list"),
        reverse("setup:start"),
    ]:
        assert f'href="{url}"' in page
    assert f'href="{reverse("admin:index")}"' not in page


def test_main_pages_are_not_repeated(client, make_user):
    page = get(client, make_user("admin", "Admin", is_staff=True)).content.decode()
    main = page.split('<main id="main">')[1]

    for name in ["unit", "person", "invoice", "message", "messagebatch", "backuprun"]:
        assert f"_{name}_changelist" not in main
        assert f"/{name}/" not in main


def test_singletons_link_to_their_change_form(client, make_user):
    organisation = Organisation.objects.create(name="Byns vatten")

    page = get(client, make_user("admin", "Admin", is_staff=True)).content.decode()

    assert reverse("admin:register_organisation_change", args=[organisation.pk]) in page


def test_superusers_also_get_advanced(client, make_user):
    user = make_user("root", is_staff=True, is_superuser=True)

    page = get(client, user).content.decode()

    assert groups(page)[-1] == "advanced"
    assert f'href="{reverse("admin:index")}"' in page


def test_board_sees_only_what_it_may_change(client, make_user):
    page = get(client, make_user("board", "Board", is_staff=True)).content.decode()

    assert groups(page) == ["register", "messages"]
    assert reverse("admin:register_tag_changelist") in page
    assert reverse("admin:messaging_consentrecord_changelist") in page
    assert reverse("admin:messaging_messagetemplate_changelist") not in page
    assert reverse("admin:register_unittype_changelist") not in page


def test_treasurer_with_staff_status_sees_invoicing(client, make_user):
    page = get(client, make_user("treasurer", "Treasurer", is_staff=True)).content.decode()

    assert groups(page) == ["invoicing", "messages"]


def test_admin_entries_need_staff_status(client, make_user):
    """The admin lets in staff only, so its forms are not offered to others."""
    page = get(client, make_user("admin", "Admin")).content.decode()

    assert "admin/" not in page.split('<main id="main">')[1]
    assert groups(page) == ["integrations", "backups", "setup"]


@pytest.mark.parametrize("role", ["Read-only", "Board"])
def test_users_with_nothing_to_set_are_refused(client, make_user, role):
    user = make_user("someone", role)

    assert get(client, user).status_code == 403
    assert f'href="{URL}"' not in client.get(reverse("register:unit_list")).content.decode()


def test_anonymous_users_are_sent_to_log_in(client):
    assert client.get(URL).status_code == 302


def test_plugin_links_are_under_integrations(client, make_user):
    page = get(client, make_user("admin", "Admin", is_staff=True)).content.decode()
    section = page.split('id="settings-integrations"')[1].split("</section>")[0]

    assert reverse("metra_api:client_list") in section
    assert reverse("metra_webhooks:endpoint_list") in section


def test_no_plugin_wording(client, make_user):
    user = make_user("root", "Admin", is_staff=True, is_superuser=True)
    for language in ["en", "sv", "fi"]:
        client.force_login(user)
        page = client.get(URL, HTTP_ACCEPT_LANGUAGE=language).content.decode()
        main = page.split('<main id="main">')[1].lower()
        text = re.sub(r"<[^>]+>", " ", main)
        for word in ["plugin", "insticks", "laajennu", "liitännäi"]:
            assert word not in text


def test_the_menu_links_to_the_settings_page(client, make_user):
    client.force_login(make_user("admin", "Admin", is_staff=True))

    page = client.get(reverse("register:unit_list")).content.decode()

    assert f'href="{URL}"' in page
    assert f'href="{reverse("admin:index")}"' not in page


def test_the_help_link_opens_getting_started(client, make_user):
    page = get(client, make_user("admin", "Admin", is_staff=True)).content.decode()

    assert reverse("help:article", args=["getting-started"]) in page


def test_fee_lines_are_edited_in_the_fee_plan(client, make_user, household):
    plan = FeePlan.objects.create(name="Basic", unit_type=household)
    FeeLine.objects.create(plan=plan, description="Base fee", unit_price=10)
    client.force_login(make_user("admin", "Admin", is_staff=True))

    form = client.get(reverse("admin:invoicing_feeplan_change", args=[plan.pk]))
    index = client.get(reverse("admin:index")).content.decode()

    assert "TOTAL_FORMS" in form.content.decode()
    assert "Base fee" in form.content.decode()
    assert reverse("admin:invoicing_feeline_changelist") not in index
    assert reverse("admin:invoicing_feeplan_changelist") in index


def test_the_admin_index_hides_main_pages_from_non_superusers(client, make_user):
    client.force_login(make_user("admin", "Admin", is_staff=True))
    index = client.get(reverse("admin:index")).content.decode()

    assert reverse("admin:register_unit_changelist") not in index
    assert reverse("admin:auditlog_logentry_changelist") not in index
    assert reverse("admin:register_unittype_changelist") in index

    client.force_login(make_user("root", is_staff=True, is_superuser=True))
    index = client.get(reverse("admin:index")).content.decode()

    assert reverse("admin:register_unit_changelist") in index


def test_invoice_settings_offer_every_setting(client, make_user):
    client.force_login(make_user("admin", "Admin", is_staff=True))

    form = client.get(reverse("admin:invoicing_billingsettings_add")).content.decode()

    for name in ["reference_type", "reminder_fee", "reminder_days", "iban"]:
        assert f'name="{name}"' in form
