import json

import pytest
from auditlog.models import LogEntry
from django.test import Client
from django.urls import reverse

from metra_webhooks.models import WebhookDelivery, WebhookEndpoint


@pytest.fixture
def admin(role_client, settings):
    client = role_client("Admin")
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"  # the pages are checked in English
    return client


@pytest.fixture
def board_client(make_user):
    client = Client()  # not the admin's client
    client.force_login(make_user("board", "Board"))
    return client


def test_staff_pages_need_permission(board_client, admin, endpoint):
    urls = [
        reverse("metra_webhooks:endpoint_list"),
        reverse("metra_webhooks:endpoint_create"),
        reverse("metra_webhooks:endpoint_edit", args=[endpoint.pk]),
        reverse("metra_webhooks:delivery_list", args=[endpoint.pk]),
        reverse("metra_webhooks:endpoint_delete", args=[endpoint.pk]),
    ]

    assert [board_client.get(url).status_code for url in urls] == [403] * 5
    assert [admin.get(url).status_code for url in urls] == [200] * 5
    for name in ["endpoint_rotate", "endpoint_test"]:
        assert (
            board_client.post(reverse(f"metra_webhooks:{name}", args=[endpoint.pk])).status_code
            == 403
        )


def test_anonymous_is_sent_to_login(client, db):
    response = client.get(reverse("metra_webhooks:endpoint_list"))

    assert response.status_code == 302 and "login" in response["Location"]


def test_create_endpoint(admin):
    response = admin.post(
        reverse("metra_webhooks:endpoint_create"),
        {"url": "https://hooks.example.org/x", "description": "Bookkeeping",
         "events": ["invoice.issued", "payment.recorded"], "active": "on"},
    )  # fmt: skip

    endpoint = WebhookEndpoint.objects.get()
    assert response.status_code == 302
    assert endpoint.events == ["invoice.issued", "payment.recorded"]
    assert endpoint.created_by.username == "admin"
    assert endpoint.secret
    page = admin.get(endpoint.get_absolute_url()).content.decode()
    assert endpoint.secret in page


def test_unknown_events_and_plain_http_are_refused(admin, settings):
    settings.DEBUG = False

    response = admin.post(
        reverse("metra_webhooks:endpoint_create"),
        {"url": "http://hooks.example.org/x", "events": ["nonsense"]},
    )

    assert response.status_code == 200
    assert not WebhookEndpoint.objects.exists()
    assert "https://" in response.content.decode()


def test_rotate_secret(admin, endpoint):
    old = endpoint.secret

    admin.post(reverse("metra_webhooks:endpoint_rotate", args=[endpoint.pk]))

    endpoint.refresh_from_db()
    assert endpoint.secret != old


def test_rotate_needs_post(admin, endpoint):
    assert (
        admin.get(reverse("metra_webhooks:endpoint_rotate", args=[endpoint.pk])).status_code == 405
    )


def test_delete_endpoint(admin, endpoint):
    admin.post(reverse("metra_webhooks:endpoint_delete", args=[endpoint.pk]))

    assert not WebhookEndpoint.objects.exists()


def test_secret_is_not_in_the_audit_log(admin, endpoint):
    endpoint.rotate_secret()
    admin.post(
        reverse("metra_webhooks:endpoint_edit", args=[endpoint.pk]),
        {"url": "https://other.example.org/x", "events": ["unit.saved"], "active": "on"},
    )

    entries = LogEntry.objects.filter(object_pk=str(endpoint.pk))
    assert entries.exists()
    for entry in entries:
        assert endpoint.secret not in json.dumps(entry.changes) + (entry.changes_text or "")
        assert "secret" not in (entry.changes or {})


def test_test_event_is_sent_as_a_ping(admin, endpoint, network):
    admin.post(reverse("metra_webhooks:endpoint_test", args=[endpoint.pk]))

    body = json.loads(network.requests[0]["body"])
    assert body["event"] == "ping" and body["data"] == {"message": "test"}
    assert network.requests[0]["headers"]["Metra-Event"] == "ping"
    page = admin.get(reverse("metra_webhooks:delivery_list", args=[endpoint.pk])).content.decode()
    assert "ping" in page and "Delivered" in page


def test_deliveries_page_and_retry(admin, endpoint, network):
    network.answer = (500, "boom")
    admin.post(reverse("metra_webhooks:endpoint_test", args=[endpoint.pk]))
    delivery = WebhookDelivery.objects.get()
    assert delivery.status == "failed"
    page = admin.get(reverse("metra_webhooks:delivery_list", args=[endpoint.pk])).content.decode()
    assert "Retry now" in page and "500" in page

    network.answer = (200, "ok")
    admin.post(reverse("metra_webhooks:delivery_retry", args=[endpoint.pk, delivery.pk]))

    delivery.refresh_from_db()
    assert delivery.status == "delivered"
    assert len(network.requests) == 2
    # A delivery that went through cannot be retried.
    response = admin.post(reverse("metra_webhooks:delivery_retry", args=[endpoint.pk, delivery.pk]))
    assert response.status_code == 404


def test_list_shows_last_delivery_status(admin, endpoint, network):
    admin.post(reverse("metra_webhooks:endpoint_test", args=[endpoint.pk]))

    page = admin.get(reverse("metra_webhooks:endpoint_list")).content.decode()

    assert "Delivered" in page and endpoint.url in page


def test_admin_has_the_permissions_and_nobody_else(make_user):
    from django.contrib.auth.models import Group

    def codenames(role):
        group = Group.objects.get(name=role)
        return {
            p.codename for p in group.permissions.filter(content_type__app_label="metra_webhooks")
        }

    assert codenames("Admin") == {
        "add_webhookendpoint", "change_webhookendpoint", "view_webhookendpoint",
        "delete_webhookendpoint", "view_webhookdelivery",
    }  # fmt: skip
    for role in ["Board", "Treasurer", "Read-only"]:
        assert codenames(role) == set()


def test_settings_page_links_to_webhooks(client, make_user, settings):
    settings.REQUIRE_MFA = False
    client.force_login(make_user("root", "Admin", is_staff=True))

    page = client.get(reverse("core:settings")).content.decode()

    assert reverse("metra_webhooks:endpoint_list") in page
