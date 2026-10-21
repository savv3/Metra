import time

import pytest
from allauth.mfa.adapter import get_adapter
from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal.auth import TOTP, format_hotp_value, generate_totp_secret, hotp_value
from django.core.cache import cache
from django.urls import reverse

SECRET = generate_totp_secret()


def current_code():
    return format_hotp_value(hotp_value(SECRET, int(time.time()) // 30))


@pytest.fixture
def admin_user(make_user):
    return make_user("admin", "Admin", is_staff=True)


def test_staff_without_two_factor_are_sent_to_set_it_up(client, admin_user):
    client.force_login(admin_user)

    for url in [reverse("register:unit_list"), reverse("admin:index")]:
        response = client.get(url)
        assert response.status_code == 302
        assert response.url == reverse("mfa_activate_totp")


def test_superusers_without_two_factor_are_sent_to_set_it_up(client, make_user):
    client.force_login(make_user("root", is_superuser=True))

    response = client.get(reverse("register:unit_list"))

    assert response.url == reverse("mfa_activate_totp")


def log_in_and_confirm_password(client):
    """Adding an authenticator asks for the password again (allauth's reauthentication)."""
    client.post(reverse("account_login"), {"login": "admin", "password": "pw"})
    response = client.get(reverse("register:unit_list"), follow=True)
    assert response.redirect_chain[-1][0].startswith(reverse("account_reauthenticate"))
    client.post(reverse("account_reauthenticate"), {"password": "pw"})


def test_setup_page_and_logout_stay_open_for_staff(client, admin_user):
    log_in_and_confirm_password(client)

    assert client.get(reverse("mfa_activate_totp")).status_code == 200
    assert client.post(reverse("account_logout")).status_code == 302
    assert client.get(reverse("register:unit_list")).url.startswith(reverse("account_login"))


def test_staff_with_two_factor_can_use_the_app(client, admin_user):
    TOTP.activate(admin_user, SECRET)
    client.force_login(admin_user)

    assert client.get(reverse("register:unit_list")).status_code == 200
    assert client.get(reverse("admin:index")).status_code == 200


def test_two_factor_is_optional_for_other_users(board_client):
    assert board_client.get(reverse("register:unit_list")).status_code == 200


def test_login_asks_for_the_authenticator_code(client, admin_user):
    TOTP.activate(admin_user, SECRET)

    response = client.post(reverse("account_login"), {"login": "admin", "password": "pw"})
    assert response.url == reverse("mfa_authenticate")
    assert client.get(reverse("register:unit_list")).status_code == 302  # not logged in yet

    response = client.post(reverse("mfa_authenticate"), {"code": current_code()})
    assert response.url == reverse("setup:start")  # a new install starts in the setup wizard
    assert client.get(reverse("register:unit_list")).status_code == 200


def test_wrong_authenticator_code_is_refused(client, admin_user):
    TOTP.activate(admin_user, SECRET)
    client.post(reverse("account_login"), {"login": "admin", "password": "pw"})

    response = client.post(reverse("mfa_authenticate"), {"code": "000000"})

    assert response.status_code == 200
    assert client.get(reverse("register:unit_list")).status_code == 302


def test_admin_login_goes_through_the_app_login(client):
    response = client.get(reverse("admin:login"))

    assert response.status_code == 302
    assert response.url.startswith(reverse("account_login"))


def test_staff_cannot_remove_their_authenticator(admin_user, make_user):
    staff_totp = TOTP.activate(admin_user, SECRET).instance
    board_totp = TOTP.activate(make_user("board", "Board"), SECRET).instance

    assert not get_adapter().can_delete_authenticator(staff_totp)
    assert get_adapter().can_delete_authenticator(board_totp)


def test_activating_two_factor_creates_recovery_codes(client, admin_user):
    log_in_and_confirm_password(client)
    client.get(reverse("mfa_activate_totp"))
    secret = client.session["mfa.totp.secret"]
    code = format_hotp_value(hotp_value(secret, int(time.time()) // 30))

    client.post(reverse("mfa_activate_totp"), {"code": code})

    types = set(Authenticator.objects.filter(user=admin_user).values_list("type", flat=True))
    assert types == {Authenticator.Type.TOTP, Authenticator.Type.RECOVERY_CODES}


@pytest.mark.django_db
def test_nobody_can_sign_up(client, django_user_model):
    client.post(
        reverse("account_signup"),
        {"username": "visitor", "password1": "a-Long-pass-123", "password2": "a-Long-pass-123"},
    )

    assert not django_user_model.objects.filter(username="visitor").exists()


def test_other_users_are_reminded_to_turn_on_two_factor(board_client):
    response = board_client.get(reverse("register:unit_list"))

    assert response.status_code == 200
    assert reverse("mfa_activate_totp") in response.content.decode()


def test_reminder_goes_once_two_factor_is_on(board_client):
    user = board_client.get(reverse("register:unit_list")).wsgi_request.user
    TOTP.activate(user, SECRET)

    response = board_client.get(reverse("register:unit_list"))

    assert reverse("mfa_activate_totp") not in response.content.decode()


def code_for(secret):
    return format_hotp_value(hotp_value(secret, int(time.time()) // 30))


def test_setup_survives_a_second_page_load_and_then_login_needs_the_code(client, admin_user):
    """The bug from the pilot: a second load of the setup page (here the browser
    asking for /favicon.ico, which used to be redirected to it) changed the
    secret, so the code from the scanned QR code was always refused."""
    from allauth.mfa.totp.internal.auth import SECRET_SESSION_KEY

    log_in_and_confirm_password(client)
    page = client.get(reverse("mfa_activate_totp"))
    secret = client.session[SECRET_SESSION_KEY]
    assert secret in page.content.decode()

    icon = client.get("/favicon.ico")
    client.get(reverse("mfa_activate_totp"))  # a reload or a second tab

    assert icon.status_code == 301
    assert icon.url.endswith("favicon.svg")
    assert client.session[SECRET_SESSION_KEY] == secret
    response = client.post(reverse("mfa_activate_totp"), {"code": code_for(secret)})
    assert response.status_code == 302, response.content.decode()
    assert Authenticator.objects.filter(user=admin_user, type="totp").exists()

    client.post(reverse("account_logout"))
    after_password = client.post(reverse("account_login"), {"login": "admin", "password": "pw"})
    assert after_password.url == reverse("mfa_authenticate")
    assert client.get(reverse("register:unit_list")).status_code == 302  # not in yet
    # A code works once (allauth remembers used codes in the cache); forgetting
    # that is the same as the next 30-second code coming round.
    cache.clear()
    signed_in = client.post(reverse("mfa_authenticate"), {"code": code_for(secret)})
    assert signed_in.status_code == 302
    assert client.get(reverse("register:unit_list")).status_code == 200


def test_requests_that_are_not_pages_are_not_sent_to_setup(client, admin_user):
    client.force_login(admin_user)

    for url in ["/favicon.ico", "/robots.txt", "/logo"]:
        response = client.get(url)
        assert response.status_code != 302 or "2fa" not in response.url, url


def test_two_factor_can_be_made_optional(client, admin_user, settings):
    settings.REQUIRE_MFA = False
    client.force_login(admin_user)

    response = client.get(reverse("register:unit_list"), HTTP_ACCEPT_LANGUAGE="en")

    assert response.status_code == 200
    assert "Two-factor login is not required on this installation" in response.content.decode()


def test_no_warning_when_two_factor_is_required(client, admin_user):
    TOTP.activate(admin_user, SECRET)
    client.force_login(admin_user)

    page = client.get(reverse("register:unit_list"), HTTP_ACCEPT_LANGUAGE="en").content.decode()

    assert "is not required on this installation" not in page


def banners(client):
    page = client.get(reverse("register:unit_list"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    return "two-factor-off" in page, "two-factor-nudge" in page, page


def test_staff_without_two_factor_see_one_banner_when_it_is_off(client, admin_user, settings):
    settings.REQUIRE_MFA = False
    client.force_login(admin_user)

    off, nudge, page = banners(client)

    assert off and not nudge
    assert "Turn on two-factor login" in page


def test_staff_with_two_factor_see_the_installation_warning_only(client, admin_user, settings):
    settings.REQUIRE_MFA = False
    TOTP.activate(admin_user, SECRET)
    client.force_login(admin_user)

    off, nudge, page = banners(client)

    assert off and not nudge
    assert "Turn on two-factor login" not in page


def test_no_two_factor_banner_when_required_and_set_up(client, admin_user):
    TOTP.activate(admin_user, SECRET)
    client.force_login(admin_user)

    off, nudge, _page = banners(client)

    assert not off and not nudge


def test_other_users_without_two_factor_get_the_personal_nudge_only(role_client):
    off, nudge, _page = banners(role_client("Board"))

    assert nudge and not off
