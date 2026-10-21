import re

from auditlog.models import LogEntry
from django.urls import reverse

from metra_api.models import ApiClient, hash_token


def token_on(response):
    return re.search(r"<code data-api-token>([^<]+)</code>", response.content.decode()).group(1)


def test_the_client_pages_need_the_permission(role_client, make_client):
    client, _token = make_client("Board")
    http = role_client("Board")
    assert http.get(reverse("metra_api:client_list")).status_code == 403
    assert http.get(reverse("metra_api:client_create")).status_code == 403
    assert http.post(reverse("metra_api:client_rotate", args=[client.pk])).status_code == 403
    assert http.post(reverse("metra_api:client_revoke", args=[client.pk])).status_code == 403
    assert http.get(reverse("metra_api:docs")).status_code == 403


def test_an_admin_creates_a_client_and_sees_the_token_once(role_client):
    http = role_client("Admin")
    assert http.get(reverse("metra_api:client_list")).status_code == 200
    response = http.post(
        reverse("metra_api:client_create"),
        {"name": "Accounting", "role": "Treasurer", "read_only": "on", "description": ""},
    )
    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]
    token = token_on(response)
    client = ApiClient.objects.get(name="Accounting")
    assert client.token_hash == hash_token(token)
    assert client.read_only and client.role == "Treasurer"
    assert client.created_by.username == "admin"
    # The list shows only the start of the token.
    listed = http.get(reverse("metra_api:client_list")).content.decode()
    assert token[:8] in listed and token not in listed
    assert "API-klienter" in listed  # Swedish by default
    # Creating the client is in the audit log, without the token.
    entry = LogEntry.objects.get_for_object(client).get()
    assert entry.actor.username == "admin"
    assert token not in str(entry.changes) and client.token_hash not in str(entry.changes)


def test_rotating_shows_a_new_token(role_client, make_client):
    client, old = make_client("Board")
    response = role_client("Admin").post(reverse("metra_api:client_rotate", args=[client.pk]))
    new = token_on(response)
    assert new != old
    client.refresh_from_db()
    assert client.token_hash == hash_token(new)


def test_revoking_stops_the_client(role_client, make_client):
    client, _token = make_client("Board")
    http = role_client("Admin")
    response = http.post(reverse("metra_api:client_revoke", args=[client.pk]))
    assert response.status_code == 302
    client.refresh_from_db()
    assert client.is_revoked and not client.user.is_active
    # A revoked client cannot get a new token.
    rotate = http.post(reverse("metra_api:client_rotate", args=[client.pk]))
    assert rotate.status_code == 404


def test_nobody_gives_a_client_more_than_they_have(make_user, client):
    from django.contrib.auth.models import Permission

    from metra_api.forms import grantable_roles

    board = make_user("helper", "Board")
    board.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="metra_api", codename="add_apiclient")
    )
    roles = [value for value, _label in grantable_roles(board)]
    assert "Admin" not in roles and "Board" in roles and "Read-only" in roles
    client.force_login(board)
    response = client.post(reverse("metra_api:client_create"), {"name": "X", "role": "Admin"})
    assert response.status_code == 200
    assert "role" in response.context["form"].errors
    assert not ApiClient.objects.exists()


def test_the_docs_page_lists_the_endpoints(role_client):
    response = role_client("Admin").get(reverse("metra_api:docs"))
    assert response.status_code == 200
    assert "/plugins/api/v1/units/" in response.content.decode()


def test_the_settings_page_links_to_the_clients(make_user, rf):
    from django.template import Context, Template

    request = rf.get("/")
    request.user = make_user("admin", "Admin")
    template = Template("{% load plugins %}{% plugin_settings_links as links %}{{ links }}")
    assert reverse("metra_api:client_list") in template.render(Context({"request": request}))
    request.user = make_user("board", "Board")
    assert reverse("metra_api:client_list") not in template.render(Context({"request": request}))


def test_the_swedish_client_intro_appears_once(role_client):
    html = role_client("Admin").get(reverse("metra_api:client_list")).content.decode()

    assert html.count("Varje klient är ett annat system med en egen token.") == 1
