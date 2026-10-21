"""Delivery reports from SMS and email providers: a provider plugin's
callback view calls ``record`` (SMS) or ``record_email`` with the id the
provider gave the message when it was sent."""

from collections import Counter

from django.utils import timezone
from django.utils.translation import gettext as _

from .failures import notify_failures
from .models import Message, MessageBatch
from .registry import EMAIL, SMS

DELIVERED = "delivered"
BOUNCED = "bounced"
COMPLAINED = "complained"
EMAIL_EVENTS = (DELIVERED, BOUNCED, COMPLAINED)


def record(provider, provider_id, delivered):
    """Mark the SMS the provider knows as ``provider_id`` delivered (True) or
    failed (False). Unknown ids are ignored; returns how many were updated."""
    if not provider_id:
        return 0
    status = Message.Status.DELIVERED if delivered else Message.Status.FAILED
    found = Message.objects.filter(channel=SMS, provider=provider, provider_id=provider_id)
    newly_failed = Counter()
    if not delivered:
        newly_failed.update(
            found.exclude(status=Message.Status.FAILED)
            .filter(batch__isnull=False)
            .values_list("batch_id", flat=True)
        )
    updated = found.update(status=status, status_changed_at=timezone.now())
    for batch in MessageBatch.objects.filter(pk__in=newly_failed):
        notify_failures(batch, newly_failed[batch.pk])
    return updated


def record_email(provider, provider_id, event, reason=""):
    """Record what the email provider reports about the email it calls
    ``provider_id``: DELIVERED, BOUNCED (it will not arrive; the person's
    address is flagged) or COMPLAINED (the recipient marked it as spam).
    Unknown ids and events are ignored; returns how many messages matched."""
    if not provider_id or event not in EMAIL_EVENTS:
        return 0
    found = list(
        Message.objects.filter(
            channel=EMAIL, provider=provider, provider_id=provider_id
        ).select_related("person", "batch")
    )
    now = timezone.now()
    for message in found:
        if event == DELIVERED:
            if message.status == Message.Status.FAILED:
                continue  # a bounce reported first stays
            message.status = Message.Status.DELIVERED
        elif event == BOUNCED:
            newly_failed = message.status != Message.Status.FAILED
            message.status = Message.Status.FAILED
            message.error = (
                (_("Bounced: %(reason)s") % {"reason": reason}) if reason else _("Bounced.")
            )
            _flag_person(message, reason, now)
            if newly_failed and message.batch is not None:
                notify_failures(message.batch, 1)
        else:
            message.error = _("The recipient marked this email as spam.")
        message.status_changed_at = now
        message.save(update_fields=["status", "error", "status_changed_at"])
    return len(found)


def _flag_person(message, reason, when):
    person = message.person
    # Only the address the email went to; one changed since has not bounced.
    if person is None or person.email.lower() != message.recipient.lower():
        return
    person.email_bounced_at = when
    person.email_bounce_reason = reason[:300]
    person.save(update_fields=["email_bounced_at", "email_bounce_reason"])
