import pytest
from allauth.mfa.models import Authenticator
from allauth.mfa.recovery_codes.internal.auth import RecoveryCodes
from django.urls import reverse


@pytest.fixture
def board_user(make_user):
    return make_user("board", "Board")


def test_account_page_needs_login(client):
    response = client.get(reverse("accounts:profile"))

    assert response.status_code == 302
    assert response.url.startswith(reverse("account_login"))


def test_account_page_shows_details_and_offers_two_factor(client, board_user):
    client.force_login(board_user)

    response = client.get(reverse("accounts:profile"))

    content = response.content.decode()
    assert response.status_code == 200
    assert "board" in content
    assert reverse("mfa_activate_totp") in content
    assert reverse("account_change_password") in content
    # The page itself explains two-factor, so the reminder banner is left out.
    assert "two-factor-nudge" not in content


def test_account_page_shows_two_factor_on_with_recovery_codes(client, board_user):
    Authenticator.objects.create(
        user=board_user, type=Authenticator.Type.TOTP, data={"secret": "x"}
    )
    RecoveryCodes.activate(board_user)
    client.force_login(board_user)

    response = client.get(reverse("accounts:profile"))

    content = response.content.decode()
    assert reverse("mfa_deactivate_totp") in content
    assert reverse("mfa_view_recovery_codes") in content
    assert reverse("mfa_activate_totp") not in content


def test_menu_links_to_the_account_page_instead_of_two_factor(client, board_user):
    client.force_login(board_user)

    response = client.get(reverse("register:unit_list"))

    content = response.content.decode()
    assert reverse("accounts:profile") in content
    assert f'href="{reverse("mfa_index")}"' not in content
    assert f'<a href="{reverse("register:unit_list")}" aria-current="page">' in content


def test_two_factor_pages_link_back_to_the_account_page(client, board_user):
    client.force_login(board_user)

    response = client.get(reverse("mfa_index"))

    assert reverse("accounts:profile") in response.content.decode()
