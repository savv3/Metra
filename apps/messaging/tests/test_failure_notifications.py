"""Messages that could not be delivered show up under the bell."""

from django.urls import reverse

from apps.messaging.models import Message, MessageBatch
from apps.messaging.sending import send_batch
from apps.notifications.models import Notification, Recipient
from apps.plugins import api


def test_a_send_out_with_failures_notifies_its_sender_and_the_admins(
    open_round, make_household, make_user, django_capture_on_commit_callbacks
):
    sender, admin = make_user("sender", "Board"), make_user("admin", "Admin")
    make_user("other", "Board")
    make_household("A", first_name="Anna", phone="040 123 4567")
    make_household("B")  # no contact: fails
    make_household("C")
    batch = MessageBatch.objects.create(kind="links", round=open_round, created_by=sender)

    with django_capture_on_commit_callbacks(execute=True):
        send_batch(batch)

    notification = Notification.objects.get(kind="messages_failed")
    assert notification.params["count"] == 2
    assert notification.link == reverse("messaging:batch_detail", args=[batch.pk])
    assert set(notification.recipients.values_list("user", flat=True)) == {sender.pk, admin.pk}


def test_a_send_out_without_failures_notifies_nobody(
    open_round, make_household, make_user, django_capture_on_commit_callbacks
):
    make_user("admin", "Admin")
    make_household("A", first_name="Anna", phone="040 123 4567")

    with django_capture_on_commit_callbacks(execute=True):
        send_batch(MessageBatch.objects.create(kind="links", round=open_round))

    assert not Notification.objects.exists()


def test_a_failed_delivery_report_joins_the_send_outs_notification(
    open_round, make_user, django_capture_on_commit_callbacks
):
    admin = make_user("admin", "Admin")
    batch = MessageBatch.objects.create(kind="links", round=open_round, status="done")
    for provider_id in ["s1", "s2"]:
        Message.objects.create(
            batch=batch, channel="sms", provider="some-sms", provider_id=provider_id, status="sent"
        )

    with django_capture_on_commit_callbacks(execute=True):
        api.record_delivery("some-sms", "s1", delivered=False)
    Recipient.objects.filter(user=admin).update(read_at="2026-01-01T00:00Z")
    with django_capture_on_commit_callbacks(execute=True):
        api.record_delivery("some-sms", "s1", delivered=False)  # the same report again
        api.record_delivery("some-sms", "s2", delivered=True)

    notification = Notification.objects.get(kind="messages_failed")
    assert notification.params["count"] == 1
    assert Recipient.objects.get(user=admin).read_at is not None
