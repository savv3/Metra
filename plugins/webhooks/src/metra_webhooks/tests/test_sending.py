import hashlib
import hmac
import json
import socket
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone, translation

from apps.plugins import api
from apps.plugins.hooks import WEBHOOK_EVENTS, hooks
from metra_webhooks import events, service, tasks
from metra_webhooks.models import WebhookDelivery, WebhookEndpoint

from .conftest import REAL_HTTP_POST


def make_delivery(endpoint, event="unit.saved"):
    return service.create_delivery(endpoint, event, {"unit_id": 1})


def test_delivery_only_for_subscribed_active_endpoints(endpoint, network):
    WebhookEndpoint.objects.create(url="https://b.example.org", events=["person.saved"])
    WebhookEndpoint.objects.create(url="https://c.example.org", events=["unit.saved"], active=False)
    WebhookEndpoint.objects.create(url="https://d.example.org", events=[])

    deliveries = service.queue("unit.saved", {"unit_id": 5})

    assert [d.endpoint for d in deliveries] == [endpoint]
    assert [r["url"] for r in network.requests] == [endpoint.url]


def test_a_saved_unit_is_sent_after_commit(
    django_capture_on_commit_callbacks, household, endpoint, network
):
    from apps.register.models import Unit

    with django_capture_on_commit_callbacks(execute=True):
        unit = Unit.objects.create(unit_type=household, name="Byvägen 4")

    body = json.loads(network.requests[0]["body"])
    assert body["event"] == "unit.saved"
    assert body["data"] == {
        "unit_id": unit.pk,
        "unit_type_id": household.pk,
        "status": "active",
        "archived": False,
        "created": True,
    }
    assert "Byvägen" not in network.requests[0]["body"].decode()


def test_request_is_signed_and_verifiable(endpoint, network):
    delivery = make_delivery(endpoint)

    service.attempt(delivery)

    request = network.requests[0]
    headers = request["headers"]
    assert headers["Content-Type"] == "application/json"
    assert headers["User-Agent"] == "Metra-Webhooks/1"
    assert headers["Metra-Event"] == "unit.saved"
    assert headers["Metra-Delivery"] == str(delivery.pk)
    timestamp, signature = (part.split("=", 1)[1] for part in headers["Metra-Signature"].split(","))
    expected = hmac.new(
        endpoint.secret.encode(), f"{timestamp}.".encode() + request["body"], hashlib.sha256
    ).hexdigest()
    assert signature == expected
    assert abs(int(timestamp) - timezone.now().timestamp()) < 5
    body = json.loads(request["body"])
    assert body["id"] == str(delivery.pk)
    assert body["occurred_at"].endswith("Z")
    assert b", " not in request["body"] and b": " not in request["body"]  # compact


def test_secret_is_random_and_rotates(endpoint):
    first = endpoint.secret
    assert len(first) >= 40

    endpoint.rotate_secret()

    assert endpoint.secret != first


def test_builtin_payloads_have_no_personal_data():
    unit = SimpleNamespace(pk=1, unit_type_id=2, status="active", archived_at=None, name="Anna")
    person = SimpleNamespace(pk=3, archived_at=timezone.now(), first_name="Anna", email="a@b.fi")
    reading = SimpleNamespace(pk=4, unit_id=1, round_id=9)
    invoice = SimpleNamespace(
        pk=5, number="2026-1", kind="invoice", unit_id=1, total=12, due_date=None
    )
    payment = SimpleNamespace(pk=6, invoice_id=5, amount=12, paid_on=timezone.localdate())
    by_name = {e.name: e for e in api.webhook_events()}

    data = {
        "unit.saved": by_name["unit.saved"].payload(unit=unit, created=False),
        "person.saved": by_name["person.saved"].payload(person=person, created=True),
        "reading.saved": by_name["reading.saved"].payload(reading=reading, created=True),
        "invoice.issued": by_name["invoice.issued"].payload(invoice=invoice),
        "payment.recorded": by_name["payment.recorded"].payload(payment=payment),
    }

    assert data["person.saved"] == {"person_id": 3, "archived": True, "created": True}
    assert data["invoice.issued"]["total"] == "12"
    assert data["invoice.issued"]["due_date"] is None
    assert data["payment.recorded"]["invoice_id"] == 5
    text = json.dumps(data, default=str)
    assert "Anna" not in text and "@" not in text


@pytest.mark.parametrize("code", [200, 204])
def test_2xx_is_delivered(endpoint, network, code):
    network.answer = (code, "thanks")
    delivery = make_delivery(endpoint)

    service.attempt(delivery)

    delivery.refresh_from_db()
    assert delivery.status == "delivered"
    assert delivery.delivered_at and delivery.response_status == code
    assert delivery.response_excerpt == "thanks"


@pytest.mark.parametrize("answer", [(301, ""), (302, ""), (500, "oops"), (404, "x")])
def test_other_answers_fail_and_are_retried(endpoint, network, answer):
    network.answer = answer
    delivery = make_delivery(endpoint)

    service.attempt(delivery)

    delivery.refresh_from_db()
    assert delivery.status == "failed"
    assert delivery.response_status == answer[0]
    assert delivery.attempts == 1
    assert delivery.next_attempt_at > timezone.now()


def test_timeout_fails(endpoint, network):
    network.answer = TimeoutError("timed out")
    delivery = make_delivery(endpoint)

    service.attempt(delivery)

    delivery.refresh_from_db()
    assert delivery.status == "failed"
    assert "timed out" in delivery.error
    assert delivery.response_status is None


def test_response_excerpt_is_kept_short(endpoint, network):
    network.answer = (200, "x" * 5000)
    delivery = make_delivery(endpoint)

    service.attempt(delivery)

    delivery.refresh_from_db()
    assert len(delivery.response_excerpt) == 500


def test_retry_schedule_then_given_up(endpoint, network):
    network.answer = (500, "")
    delivery = make_delivery(endpoint)

    for index, wait in enumerate(service.BACKOFF, start=1):
        before = timezone.now()
        service.attempt(delivery)
        delivery.refresh_from_db()
        assert delivery.status == "failed" and delivery.attempts == index
        assert abs(delivery.next_attempt_at - before - wait) < timedelta(seconds=5)
    service.attempt(delivery)

    delivery.refresh_from_db()
    assert delivery.status == "given_up"
    assert delivery.attempts == len(service.BACKOFF) + 1
    assert [m for m in service.BACKOFF][0] == timedelta(minutes=1)
    assert service.BACKOFF[-1] == timedelta(hours=12)


def test_a_delivery_is_only_claimed_when_due_and_once(endpoint):
    delivery = make_delivery(endpoint)

    assert service.claim(delivery.pk) is not None
    assert service.claim(delivery.pk) is None  # leased: not due again until the lease ends

    later = make_delivery(endpoint)
    WebhookDelivery.objects.filter(pk=later.pk).update(
        next_attempt_at=timezone.now() + timedelta(hours=1), status="failed"
    )
    assert service.claim(later.pk) is None


def test_sweep_sends_what_is_due(endpoint, network):
    due = make_delivery(endpoint)
    WebhookDelivery.objects.filter(pk=due.pk).update(status="failed")
    waiting = make_delivery(endpoint)
    WebhookDelivery.objects.filter(pk=waiting.pk).update(
        status="failed", next_attempt_at=timezone.now() + timedelta(hours=1)
    )
    done = make_delivery(endpoint)
    WebhookDelivery.objects.filter(pk=done.pk).update(status="delivered")

    tasks.sweep()

    assert [json.loads(r["body"])["id"] for r in network.requests] == [str(due.pk)]
    due.refresh_from_db()
    assert due.status == "delivered"


def test_inactive_endpoint_is_given_up(endpoint, network):
    delivery = make_delivery(endpoint)
    endpoint.active = False
    endpoint.save()

    service.attempt(WebhookDelivery.objects.select_related("endpoint").get(pk=delivery.pk))

    delivery.refresh_from_db()
    assert delivery.status == "given_up"
    assert network.requests == []


def test_another_plugins_event_can_be_delivered(db, endpoint, network):
    from django.dispatch import Signal

    signal = Signal()
    endpoint.events = ["thing.saved"]
    endpoint.save()
    event = api.WebhookEvent(
        "thing.saved", "A thing was saved", signal, lambda thing, **kw: {"id": thing}
    )

    api.add_webhook_event(event)  # a plugin loading after the webhooks plugin
    try:
        signal.send(sender=None, thing=7)
    finally:
        signal.disconnect(dispatch_uid="metra_webhooks.thing.saved")
        hooks._items[WEBHOOK_EVENTS].remove(event)  # the registry is shared

    body = json.loads(network.requests[0]["body"])
    assert body["event"] == "thing.saved" and body["data"] == {"id": 7}
    assert ("thing.saved", "A thing was saved") not in events.event_choices()


def test_old_deliveries_are_deleted(endpoint, monkeypatch):
    old = make_delivery(endpoint)
    WebhookDelivery.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=31))
    recent = make_delivery(endpoint)

    assert service.delete_old() == 1
    assert list(WebhookDelivery.objects.all()) == [recent]

    monkeypatch.delenv("METRA_WEBHOOK_KEEP_DAYS", raising=False)
    assert service.keep_days() == 30
    monkeypatch.setenv("METRA_WEBHOOK_KEEP_DAYS", "7")
    assert service.keep_days() == 7


# -- Addresses -------------------------------------------------------------


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.1.2.3", "192.168.0.5", "172.16.0.1", "169.254.169.254", "::1", "fe80::1",
     "0.0.0.0", "224.0.0.1", "100.64.0.1", "::ffff:127.0.0.1", "fc00::1"],
)  # fmt: skip
def test_internal_addresses_are_refused(settings, address, monkeypatch):
    settings.DEBUG = False
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", (address, 443))])

    with pytest.raises(service.UnsafeURL):
        service.resolve("anything.example.org", 443)


def test_a_name_with_one_internal_address_is_refused(settings, monkeypatch):
    settings.DEBUG = False
    answers = [(0, 0, 0, "", ("93.184.216.34", 443)), (0, 0, 0, "", ("10.0.0.7", 443))]
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: answers)

    with pytest.raises(service.UnsafeURL):
        service.resolve("rebind.example.org", 443)


def test_public_address_is_allowed(settings, monkeypatch):
    settings.DEBUG = False
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("93.184.216.34", 443))]
    )

    assert service.resolve("example.org", 443) == ["93.184.216.34"]


def test_internal_addresses_are_allowed_in_development(settings, monkeypatch):
    settings.DEBUG = True
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("127.0.0.1", 80))])

    assert "127.0.0.1" in service.resolve("localhost", 80)


def test_http_is_refused_unless_debugging(settings):
    settings.DEBUG = False
    with pytest.raises(service.UnsafeURL):
        service.check_scheme("http://example.org/hook")
    with pytest.raises(service.UnsafeURL):
        service.check_scheme("https://user:pw@example.org/hook")
    assert service.check_scheme("https://example.org/hook")
    settings.DEBUG = True
    assert service.check_scheme("http://localhost:9000/hook")


def test_real_request_refuses_internal_hosts_without_connecting(settings, monkeypatch):
    settings.DEBUG = False
    monkeypatch.setattr(service, "http_post", REAL_HTTP_POST)
    connected = []
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: connected.append(a))

    for url in [
        "https://127.0.0.1/",
        "https://10.0.0.1/x",
        "https://169.254.169.254/",
        "https://[::1]/",
    ]:
        with pytest.raises(service.UnsafeURL):
            service.http_post(url, b"{}", {})

    assert connected == []


def test_unsafe_address_fails_the_delivery_with_a_reason(endpoint, settings, monkeypatch):
    settings.DEBUG = False
    monkeypatch.setattr(service, "http_post", REAL_HTTP_POST)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("10.0.0.7", 443))])
    delivery = make_delivery(endpoint)

    with translation.override("en"):
        service.attempt(delivery)

    delivery.refresh_from_db()
    assert delivery.status == "failed"
    assert "internal" in delivery.error


def test_real_request_to_a_local_server_in_development(settings, monkeypatch):
    """The one test that opens a socket: to a throwaway server on this machine."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append((self.headers["Host"], self.headers["Metra-Signature"]))
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(302 if self.path == "/redirect" else 200)
            self.send_header("Location", "http://example.org/")
            self.end_headers()
            self.wfile.write(b"hello")

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        settings.DEBUG = True
        port = server.server_port
        status, text = REAL_HTTP_POST(
            f"http://localhost:{port}/hook", b'{"a":1}', {"Metra-Signature": "x"}
        )
        redirected, _text = REAL_HTTP_POST(f"http://localhost:{port}/redirect", b"{}", {})
    finally:
        server.shutdown()

    assert (status, text) == (200, "hello")
    assert redirected == 302  # not followed
    assert seen[0] == (f"localhost:{port}", "x")
    assert len(seen) == 2  # the redirect target was not requested


def test_the_next_checked_address_is_tried_when_one_does_not_answer(monkeypatch):
    tried = []

    def create_connection(address, timeout):
        tried.append(address[0])
        if address[0] == "2001:db8::1":
            raise ConnectionRefusedError("unreachable")
        return "socket"

    monkeypatch.setattr(socket, "create_connection", create_connection)
    connection = service._HTTPConnection("example.org", 80)
    connection.pinned_ips = ["2001:db8::1", "93.184.216.34"]

    assert connection._connect_socket() == "socket"
    assert tried == ["2001:db8::1", "93.184.216.34"]


def test_a_given_up_delivery_shows_up_under_the_admins_bell(
    endpoint, network, role_client, django_capture_on_commit_callbacks
):
    client = role_client("Admin")
    network.answer = (500, "")
    delivery = make_delivery(endpoint)
    WebhookDelivery.objects.filter(pk=delivery.pk).update(attempts=len(service.BACKOFF))
    delivery.refresh_from_db()

    with django_capture_on_commit_callbacks(execute=True):
        service.attempt(delivery)

    page = client.get("/notifications/", HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert "A webhook to hooks.example.org could not be delivered and was given up." in page
    assert 'aria-label="Notifications, 1 unread"' in page


def test_a_switched_off_endpoint_notifies_nobody(
    endpoint, network, role_client, django_capture_on_commit_callbacks
):
    client = role_client("Admin")
    delivery = make_delivery(endpoint)
    endpoint.active = False
    endpoint.save()

    with django_capture_on_commit_callbacks(execute=True):
        service.attempt(delivery)

    page = client.get("/notifications/", HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert "given up" not in page
