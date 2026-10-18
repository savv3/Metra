"""Creating, signing and sending webhook deliveries.

Flow: an event's signal fires after the change is committed (see
``apps.plugins.events``), ``queue`` creates one ``WebhookDelivery`` per active
endpoint subscribed to it and hands each to a background task, and ``attempt``
does the POST. A failed attempt schedules the next one in the database
(``next_attempt_at``) rather than only in the task queue, and a periodic sweep
(``tasks.sweep``) picks up whatever is due, so nothing is lost when the worker
restarts.
"""

import hashlib
import hmac
import http.client
import ipaddress
import json
import logging
import socket
import ssl
import time
from datetime import UTC, timedelta
from urllib.parse import urlsplit

from auditlog.context import disable_auditlog
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import WebhookDelivery, WebhookEndpoint

logger = logging.getLogger(__name__)

TIMEOUT = 10
EXCERPT_LENGTH = 500
USER_AGENT = "Metra-Webhooks/1"
# The wait after the first, second, ... failed attempt. After the last one is
# used up and the next attempt fails too, the delivery is given up.
BACKOFF = [
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=30),
    timedelta(hours=2),
    timedelta(hours=12),
]
# While an attempt is being made, the delivery is not due, so the sweep does
# not start a second one. If the worker dies mid-attempt it is retried after this.
LEASE = timedelta(minutes=5)


class UnsafeURL(ValueError):
    """The address is not one Metra may send to."""


# -- Addresses -------------------------------------------------------------


def check_scheme(url):
    """Raise ``UnsafeURL`` unless ``url`` is https (http too in development)."""
    parts = urlsplit(url)
    allowed = ("https", "http") if settings.DEBUG else ("https",)
    if parts.scheme not in allowed or not parts.hostname:
        raise UnsafeURL(
            _("The address must start with https://.")
            if not settings.DEBUG
            else _("The address must start with https:// or http://.")
        )
    if parts.username or parts.password:
        raise UnsafeURL(_("The address must not contain a user name or password."))
    return parts


def is_public(address):
    """True for an address on the public internet. Loopback, private, link-local,
    multicast, reserved, unspecified and other non-global addresses are not."""
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def resolve(host, port):
    """The IP address to connect to for ``host``. Every address the name
    resolves to must be public (unless DEBUG), so a name cannot be pointed at
    the internal network."""
    try:
        found = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as error:
        raise UnsafeURL(_("The address %(host)s could not be found.") % {"host": host}) from error
    addresses = [info[4][0].split("%")[0] for info in found]
    if not addresses:
        raise UnsafeURL(_("The address %(host)s could not be found.") % {"host": host})
    if not settings.DEBUG:
        for address in addresses:
            if not is_public(address):
                raise UnsafeURL(
                    _("%(host)s points to an internal address, which is not allowed.")
                    % {"host": host}
                )
    return addresses[0]


# -- The request -----------------------------------------------------------


class _PinnedMixin:
    """Connect to an address that was already checked, not to the name again.

    Looking the name up a second time when connecting would let a hostile DNS
    server answer differently the second time (DNS rebinding). The name stays
    the Host header, and for https the certificate name and SNI.
    """

    pinned_ip = None

    def _connect_socket(self):
        return socket.create_connection((self.pinned_ip, self.port), self.timeout)


class _HTTPConnection(_PinnedMixin, http.client.HTTPConnection):
    def connect(self):
        self.sock = self._connect_socket()


class _HTTPSConnection(_PinnedMixin, http.client.HTTPSConnection):
    def connect(self):
        sock = self._connect_socket()
        context = ssl.create_default_context()
        self.sock = context.wrap_socket(sock, server_hostname=self.host)


def http_post(url, body, headers, timeout=TIMEOUT):
    """POST ``body`` to ``url``; returns (status code, start of the response).

    Does not follow redirects, and connects to the checked address (see
    ``_PinnedMixin``). Raises ``UnsafeURL`` or ``OSError`` (which covers
    timeouts and TLS errors). Tests replace this function.
    """
    parts = check_scheme(url)
    port = parts.port or (443 if parts.scheme == "https" else 80)
    ip = resolve(parts.hostname, port)
    connection_class = _HTTPSConnection if parts.scheme == "https" else _HTTPConnection
    connection = connection_class(parts.hostname, port, timeout=timeout)
    connection.pinned_ip = ip
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    try:
        connection.request("POST", path, body=body, headers=headers)
        response = connection.getresponse()
        excerpt = response.read(EXCERPT_LENGTH * 4).decode("utf-8", errors="replace")
        return response.status, excerpt[:EXCERPT_LENGTH]
    finally:
        connection.close()


def sign(secret, timestamp, body):
    """The hex HMAC-SHA256 of "<timestamp>.<body>"; see docs/webhooks.md."""
    message = f"{timestamp}.".encode() + body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def encode(payload):
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()


def headers_for(delivery, body, now=None):
    timestamp = int(now if now is not None else time.time())
    return {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "Metra-Event": delivery.event,
        "Metra-Delivery": str(delivery.pk),
        "Metra-Signature": f"t={timestamp},v1={sign(delivery.endpoint.secret, timestamp, body)}",
    }


# -- Deliveries ------------------------------------------------------------


def envelope(event, data, delivery_id):
    return {
        "id": str(delivery_id),
        "event": event,
        "occurred_at": timezone.now().astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "data": data,
    }


def create_delivery(endpoint, event, data):
    delivery = WebhookDelivery(endpoint=endpoint, event=event)
    delivery.payload = envelope(event, data, delivery.pk)
    delivery.save()
    return delivery


def queue(event, data):
    """Create a delivery for each active endpoint subscribed to ``event`` and
    start sending them."""
    from . import tasks

    endpoints = [
        endpoint
        for endpoint in WebhookEndpoint.objects.filter(active=True)
        if event in endpoint.events
    ]
    deliveries = [create_delivery(endpoint, event, data) for endpoint in endpoints]
    for delivery in deliveries:
        tasks.deliver(str(delivery.pk))
    return deliveries


def claim(delivery_id):
    """Take a delivery that is due, so only one worker sends it. Returns it, or None."""
    now = timezone.now()
    with transaction.atomic():
        taken = WebhookDelivery.objects.filter(
            pk=delivery_id,
            status__in=[WebhookDelivery.Status.PENDING, WebhookDelivery.Status.FAILED],
            next_attempt_at__lte=now,
        ).update(next_attempt_at=now + LEASE)
    if not taken:
        return None
    return WebhookDelivery.objects.select_related("endpoint").get(pk=delivery_id)


def attempt(delivery):
    """Make one attempt and record how it went."""
    endpoint = delivery.endpoint
    now = timezone.now()
    delivery.attempts += 1
    delivery.last_attempt_at = now
    delivery.response_status = None
    delivery.response_excerpt = ""
    delivery.error = ""

    if not endpoint.active:
        delivery.status = WebhookDelivery.Status.GIVEN_UP
        delivery.error = _("The endpoint is switched off.")
    else:
        try:
            body = encode(delivery.payload)
            status, excerpt = http_post(endpoint.url, body, headers_for(delivery, body))
        except UnsafeURL as error:
            delivery.error = str(error)[:EXCERPT_LENGTH]
        except (OSError, http.client.HTTPException) as error:
            # Never put the request itself in the message: keep it to the kind of failure.
            delivery.error = f"{type(error).__name__}: {error}"[:EXCERPT_LENGTH]
        else:
            delivery.response_status = status
            delivery.response_excerpt = excerpt[:EXCERPT_LENGTH]
            if 200 <= status < 300:
                delivery.status = WebhookDelivery.Status.DELIVERED
                delivery.delivered_at = now
            else:
                delivery.error = _("The receiver answered %(status)s.") % {"status": status}

        if delivery.status != WebhookDelivery.Status.DELIVERED:
            if delivery.attempts <= len(BACKOFF):
                delivery.status = WebhookDelivery.Status.FAILED
                delivery.next_attempt_at = now + BACKOFF[delivery.attempts - 1]
            else:
                delivery.status = WebhookDelivery.Status.GIVEN_UP
    delivery.save()
    return delivery


def retry_now(delivery):
    """Send a failed or given-up delivery again, from the start of the schedule."""
    from . import tasks

    delivery.status = WebhookDelivery.Status.PENDING
    delivery.attempts = 0
    delivery.next_attempt_at = timezone.now()
    delivery.save(update_fields=["status", "attempts", "next_attempt_at"])
    tasks.deliver(str(delivery.pk))


def send_ping(endpoint):
    from . import events, tasks

    delivery = create_delivery(endpoint, events.PING, {"message": "test"})
    tasks.deliver(str(delivery.pk))
    return delivery


def keep_days():
    import os

    try:
        return int(os.environ.get("METRA_WEBHOOK_KEEP_DAYS") or 30)
    except ValueError:
        return 30


def delete_old(now=None):
    """Delete deliveries older than METRA_WEBHOOK_KEEP_DAYS. Returns how many."""
    cutoff = (now or timezone.now()) - timedelta(days=keep_days())
    # Clearing out history is not worth an audit log entry per row.
    with disable_auditlog():
        return WebhookDelivery.objects.filter(created_at__lt=cutoff).delete()[0]
