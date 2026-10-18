"""Things that happen in Metra that plugins can react to, for example to send
a webhook. Each is a Django signal sent once the change is committed to the
database, so a receiver never sees a change that was rolled back.

    from apps.plugins import api

    @receiver(api.events.invoice_issued)
    def on_invoice_issued(sender, invoice, **kwargs): ...

Receivers run in the request or worker that made the change; anything slow
belongs in a background task. An error in a receiver is logged and does not
undo the change.
"""

import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import Signal

logger = logging.getLogger(__name__)

# unit, created: a unit was added or changed (archiving is a change).
unit_saved = Signal()
# person, created: a person was added or changed.
person_saved = Signal()
# reading, created: a reading was entered or corrected, by staff or a member.
reading_saved = Signal()
# invoice: an invoice or credit note was issued and got its number.
invoice_issued = Signal()
# payment: a payment was recorded on an invoice.
payment_recorded = Signal()

ALL = {
    "unit_saved": unit_saved,
    "person_saved": person_saved,
    "reading_saved": reading_saved,
    "invoice_issued": invoice_issued,
    "payment_recorded": payment_recorded,
}


def send_on_commit(signal, sender, **kwargs):
    """Send ``signal`` after the current transaction commits (now, outside one)."""

    def send():
        for receiver, error in signal.send_robust(sender=sender, **kwargs):
            if isinstance(error, Exception):
                logger.error(
                    "Plugin event receiver %r failed",
                    receiver,
                    exc_info=(type(error), error, error.__traceback__),
                )

    transaction.on_commit(send)


def _forward(signal, name):
    def receiver(sender, instance, created, raw=False, **kwargs):
        if not raw:  # not while loading fixtures
            send_on_commit(signal, sender, **{name: instance, "created": created})

    return receiver


def connect():
    """Forward saves of register and reading records; called once at startup."""
    from apps.readings.models import Reading
    from apps.register.models import Person, Unit

    for model, signal, name in [
        (Unit, unit_saved, "unit"),
        (Person, person_saved, "person"),
        (Reading, reading_saved, "reading"),
    ]:
        post_save.connect(
            _forward(signal, name), sender=model, weak=False, dispatch_uid=f"plugins.{name}"
        )
