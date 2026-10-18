import pytest
from allauth.mfa.totp.internal.auth import TOTP, generate_totp_secret
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import translation

from apps.accounts.roles import role_label

SWEDISH = {
    "Admin": "Admin",
    "Board": "Styrelse",
    "Treasurer": "Kassör",
    "Read-only": "Läsbehörighet",
}


@pytest.fixture
def admin_client(client, make_user):
    admin = make_user("admin", "Admin", is_staff=True)
    TOTP.activate(admin, generate_totp_secret())
    client.force_login(admin)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize("name", list(SWEDISH))
def test_built_in_roles_are_translated_but_stored_in_english(name):
    assert Group.objects.filter(name=name).exists()
    with translation.override("sv"):
        assert role_label(Group.objects.get(name=name)) == SWEDISH[name]
    with translation.override("en"):
        assert role_label(name) == name


@pytest.mark.django_db
def test_custom_groups_keep_their_name():
    group = Group.objects.create(name="Kören")

    with translation.override("en"):
        assert role_label(group) == "Kören"


def test_account_menu_shows_the_users_role(role_client):
    client = role_client("Treasurer")

    swedish = client.get(reverse("register:unit_list")).content.decode()
    english = client.get(reverse("register:unit_list"), HTTP_ACCEPT_LANGUAGE="en")

    assert "<span>Kassör</span>" in swedish
    assert "<span>Treasurer</span>" in english.content.decode()


@pytest.mark.parametrize("language, expected", [("sv", "Läsbehörighet"), ("en", "Read-only")])
def test_settings_group_list_is_translated(admin_client, language, expected):
    Group.objects.create(name="Kören")

    page = admin_client.get(reverse("admin:auth_group_changelist"), HTTP_ACCEPT_LANGUAGE=language)

    html = page.content.decode()
    assert expected in html
    assert "Kören" in html


@pytest.mark.parametrize("language, expected", [("sv", "Styrelse"), ("en", "Board")])
def test_user_form_and_filter_show_translated_roles(admin_client, make_user, language, expected):
    user = make_user("someone", "Board")

    form = admin_client.get(
        reverse("admin:auth_user_change", args=[user.pk]), HTTP_ACCEPT_LANGUAGE=language
    )
    changelist = admin_client.get(
        reverse("admin:auth_user_changelist"), HTTP_ACCEPT_LANGUAGE=language
    )

    assert f">{expected}</option>" in form.content.decode()
    assert expected in changelist.content.decode()


def test_role_filter_finds_the_role_members(admin_client, make_user):
    make_user("someone", "Board")
    board = Group.objects.get(name="Board")

    page = admin_client.get(reverse("admin:auth_user_changelist"), {"role": board.pk})

    assert page.context["cl"].result_count == 1
