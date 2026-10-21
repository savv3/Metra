"""Telling staff, under the bell, about SMS and email that could not be delivered."""

from django.urls import reverse

from apps.notifications.service import notify

from .models import Message


def notify_failures(batch, count=None):
    """Notify the send-out's sender and the admins that ``count`` of its messages
    (by default, all its failed ones) could not be delivered. Notifications
    for one send-out are joined into one."""
    if count is None:
        count = batch.messages.filter(status=Message.Status.FAILED).count()
    if not count:
        return
    notify(
        "messages_failed",
        {"count": count},
        link=reverse("messaging:batch_detail", args=[batch.pk]),
        users=[batch.created_by_id] if batch.created_by_id else (),
        roles=["Admin"],
        group=f"batch-{batch.pk}",
    )
