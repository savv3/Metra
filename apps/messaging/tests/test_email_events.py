from apps.messaging.models import Message, MessageBatch
from apps.notifications.models import Notification
from apps.plugins import api


def email(person, provider_id="m1", **extra):
    return Message.objects.create(
        channel="email",
        person=person,
        recipient=person.email,
        provider="mailer",
        provider_id=provider_id,
        status="sent",
        **extra,
    )


def test_a_bounce_fails_the_message_and_flags_the_address(
    person, make_user, django_capture_on_commit_callbacks
):
    batch = MessageBatch.objects.create(kind="newsletter", created_by=make_user("sender", "Board"))
    message = email(person, batch=batch)

    with django_capture_on_commit_callbacks(execute=True):
        assert api.record_email_event("mailer", "m1", api.BOUNCED, "550 No such user") == 1

    message.refresh_from_db()
    person.refresh_from_db()
    assert message.status == Message.Status.FAILED
    assert message.error == "Bounced: 550 No such user"
    assert person.email_bounce_reason == "550 No such user"
    assert person.email_bounced_at is not None
    assert Notification.objects.filter(kind="messages_failed").exists()


def test_a_new_address_clears_the_flag(person):
    email(person)
    api.record_email_event("mailer", "m1", api.BOUNCED)
    person.refresh_from_db()
    assert person.email_bounced_at is not None

    person.email = "anna.new@example.com"
    person.save()

    person.refresh_from_db()
    assert person.email_bounced_at is None
    assert person.email_bounce_reason == ""


def test_an_address_changed_since_sending_is_not_flagged(person):
    email(person)
    person.email = "anna.new@example.com"
    person.save()

    api.record_email_event("mailer", "m1", api.BOUNCED)

    person.refresh_from_db()
    assert person.email_bounced_at is None


def test_delivery_after_a_bounce_does_not_undo_it(person):
    message = email(person)

    api.record_email_event("mailer", "m1", api.BOUNCED)
    api.record_email_event("mailer", "m1", api.DELIVERED)

    message.refresh_from_db()
    assert message.status == Message.Status.FAILED


def test_other_providers_ids_and_unknown_events_are_ignored(person):
    message = email(person)

    assert api.record_email_event("other", "m1", api.DELIVERED) == 0
    assert api.record_email_event("mailer", "", api.DELIVERED) == 0
    assert api.record_email_event("mailer", "m1", "opened") == 0
    message.refresh_from_db()
    assert message.status == Message.Status.SENT
