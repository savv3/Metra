"""Delivery reports from SMS providers: a provider plugin's callback view
calls ``record`` with the id the provider gave the message when it was sent."""

from collections import Counter

from django.utils import timezone

from .failures import notify_failures
from .models import Message, MessageBatch
from .registry import SMS


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
