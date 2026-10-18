"""The events webhook endpoints can subscribe to.

Any plugin can add its own with ``api.add_webhook_event``; this module adds
Metra's built-in ones through that same hook and connects a receiver to the
signal of every registered event, including those of plugins that load after
this one.

Payloads are thin on purpose. A webhook goes to an outside system, so it
carries ids and non-personal facts, never names, email addresses, phone numbers
or addresses (see the GDPR rule in AGENTS.md). The receiver fetches what it
needs through the REST API, with its own credentials.
"""

import logging

from django.utils.translation import gettext_lazy as _

from apps.plugins import api

logger = logging.getLogger(__name__)

# The event staff can send to check an endpoint; not subscribable.
PING = "ping"


def _unit(unit, created, **kwargs):
    return {
        "unit_id": unit.pk,
        "unit_type_id": unit.unit_type_id,
        "status": unit.status,
        "archived": unit.archived_at is not None,
        "created": created,
    }


def _person(person, created, **kwargs):
    return {"person_id": person.pk, "archived": person.archived_at is not None, "created": created}


def _reading(reading, created, **kwargs):
    return {
        "reading_id": reading.pk,
        "unit_id": reading.unit_id,
        "round_id": reading.round_id,
        "created": created,
    }


def _invoice(invoice, **kwargs):
    return {
        "invoice_id": invoice.pk,
        "number": invoice.number,
        "kind": invoice.kind,
        "unit_id": invoice.unit_id,
        "total": str(invoice.total),
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
    }


def _payment(payment, **kwargs):
    return {
        "payment_id": payment.pk,
        "invoice_id": payment.invoice_id,
        "amount": str(payment.amount),
        "paid_on": payment.paid_on.isoformat(),
    }


def register_builtin():
    for name, label, signal, payload in [
        ("unit.saved", _("A unit was added or changed"), api.events.unit_saved, _unit),
        ("person.saved", _("A person was added or changed"), api.events.person_saved, _person),
        (
            "reading.saved",
            _("A reading was entered or corrected"),
            api.events.reading_saved,
            _reading,
        ),
        ("invoice.issued", _("An invoice was issued"), api.events.invoice_issued, _invoice),
        (
            "payment.recorded",
            _("A payment was recorded"),
            api.events.payment_recorded,
            _payment,
        ),
    ]:
        api.add_webhook_event(api.WebhookEvent(name, label, signal, payload))


def event_choices():
    """[(name, label)] of every registered event, for the endpoint form."""
    return [(event.name, event.label) for event in api.webhook_events()]


def known_names():
    return {event.name for event in api.webhook_events()}


def connect(event):
    """Queue deliveries whenever ``event``'s signal is sent."""

    def receiver(sender, signal=None, **kwargs):
        from . import service

        try:
            data = event.payload(**kwargs)
        except Exception:
            # A faulty payload builder must not stop the change that caused it.
            logger.exception("Webhook payload for %s failed", event.name)
            return
        service.queue(event.name, data)

    event.signal.connect(receiver, weak=False, dispatch_uid=f"metra_webhooks.{event.name}")


def connect_all():
    for event in api.webhook_events():
        connect(event)
    api.on_webhook_event(connect)
