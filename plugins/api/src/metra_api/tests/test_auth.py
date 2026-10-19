import datetime

import pytest
from django.contrib.auth.models import Group, Permission
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from metra_api.models import ApiClient, hash_token

UNITS = "/plugins/api/v1/units/"


def bearer(token):
    http = APIClient()
    http.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return http


def test_a_valid_token_authenticates(make_client, unit):
    client, token = make_client("Read-only")
    response = bearer(token).get(UNITS)
    assert response.status_code == 200
    assert response.json()["results"][0]["name"] == "Byvägen 4"
    client.refresh_from_db()
    assert client.last_used_at is not None


@pytest.mark.parametrize(
    "header",
    ["", "Bearer", "Bearer not-a-token", "Bearer a b", "Token whatever"],
)
def test_missing_or_wrong_tokens_get_401(db, header):
    http = APIClient()
    if header:
        http.credentials(HTTP_AUTHORIZATION=header)
    response = http.get(UNITS)
    assert response.status_code == 401
    assert response["WWW-Authenticate"].startswith("Bearer")
    assert "detail" in response.json()


def test_a_revoked_token_gets_401(make_client):
    client, token = make_client("Board")
    client.revoke()
    assert bearer(token).get(UNITS).status_code == 401
    client.user.refresh_from_db()
    assert not client.user.is_active


def test_an_expired_token_gets_401(make_client):
    _client, token = make_client("Board", expires_at=timezone.now() - datetime.timedelta(seconds=1))
    assert bearer(token).get(UNITS).status_code == 401


def test_a_client_whose_user_is_inactive_gets_401(make_client):
    client, token = make_client("Board")
    client.user.is_active = False
    client.user.save()
    assert bearer(token).get(UNITS).status_code == 401


def test_rotating_stops_the_old_token(make_client):
    client, old = make_client("Board")
    new = client.rotate()
    assert bearer(old).get(UNITS).status_code == 401
    assert bearer(new).get(UNITS).status_code == 200


def test_last_used_is_updated_at_most_once_a_minute(make_client):
    client, token = make_client("Board")
    bearer(token).get(UNITS)
    client.refresh_from_db()
    first = client.last_used_at
    bearer(token).get(UNITS)
    client.refresh_from_db()
    assert client.last_used_at == first
    ApiClient.objects.filter(pk=client.pk).update(
        last_used_at=first - datetime.timedelta(minutes=2)
    )
    bearer(token).get(UNITS)
    client.refresh_from_db()
    assert client.last_used_at > first - datetime.timedelta(minutes=1)


def test_only_the_hash_of_the_token_is_stored(make_client):
    client, token = make_client("Board")
    client.refresh_from_db()
    assert client.token_hash == hash_token(token)
    assert client.token_prefix == token[:8]
    stored = [str(value) for value in ApiClient.objects.values_list().get(pk=client.pk)]
    assert token not in stored


def test_the_clients_user_has_one_role_and_no_password(make_client):
    client, _token = make_client("Treasurer", name="Bookkeeping")
    user = client.user
    assert user.username == "api-bookkeeping"
    assert not user.has_usable_password()
    assert not user.is_staff
    assert list(user.groups.values_list("name", flat=True)) == ["Treasurer"]
    other, _token = make_client("Board", name="Bookkeeping")
    assert other.user.username == "api-bookkeeping-2"


def test_the_clients_user_cannot_log_in_to_the_web(client, make_client):
    api_client, _token = make_client("Admin", name="Robot")
    user = api_client.user
    # Even if someone gives it a password under Settings, it is taken away.
    user.set_password("a-long-password-123")
    user.is_staff = True
    user.save()
    user.refresh_from_db()
    assert not user.has_usable_password()
    assert not user.is_staff
    response = client.post(
        reverse("account_login"), {"login": user.username, "password": "a-long-password-123"}
    )
    assert response.status_code == 200  # the form again, with an error
    assert "_auth_user_id" not in client.session


def test_deleting_a_client_deactivates_its_user(make_client):
    client, _token = make_client("Board")
    user = client.user
    client.delete()
    user.refresh_from_db()
    assert not user.is_active


def test_session_login_does_not_give_api_access(role_client, unit):
    http = role_client("Admin")
    assert http.get(UNITS).status_code == 401


def test_the_migration_gives_admin_the_client_permissions(db):
    admin = Group.objects.get(name="Admin")
    codenames = set(
        admin.permissions.filter(content_type__app_label="metra_api").values_list(
            "codename", flat=True
        )
    )
    assert {"view_apiclient", "add_apiclient", "change_apiclient"} <= codenames
    for role in ["Board", "Treasurer", "Read-only"]:
        assert not Group.objects.get(name=role).permissions.filter(
            content_type__app_label="metra_api"
        )
    assert Permission.objects.filter(codename="view_apiclient").exists()
