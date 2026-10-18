"""Delivery reports from SMS providers: a provider plugin's callback view
calls ``record`` with the id the provider gave the message when it was sent."""

from django.utils import timezone

from .models import Message
from .registry import SMS


def record(provider, provider_id, delivered):
    """Mark the SMS the provider knows as ``provider_id`` delivered (True) or
    failed (False). Unknown ids are ignored; returns how many were updated."""
    if not provider_id:
        return 0
    status = Message.Status.DELIVERED if delivered else Message.Status.FAILED
    return Message.objects.filter(channel=SMS, provider=provider, provider_id=provider_id).update(
        status=status, status_changed_at=timezone.now()
    )
