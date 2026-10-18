"""Newsletters: email to people who said yes, each with its own unsubscribe link.

Unlike service messages and alerts, a newsletter needs the person's consent.
A newsletter goes out in parts of METRA_NEWSLETTER_BATCH_SIZE emails with a
pause between them, so a mail server's rate limits are respected.
"""

import inspect

from django.conf import settings
from django.core import signing
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from apps.register.models import Person

from . import attachments
from .models import ConsentRecord, Message, MessageBatch, MessageTemplate, organisation_placeholders
from .registry import EMAIL, ProviderError, provider_for

SALT = "scr.messaging.unsubscribe"


def unsubscribe_token(person):
    """A signed token naming the person: it cannot be guessed or changed."""
    return signing.dumps(person.pk, salt=SALT)


def person_for_token(token):
    try:
        person_id = signing.loads(token, salt=SALT)
    except signing.BadSignature:
        return None
    return Person.objects.filter(pk=person_id).first()


def unsubscribe_url(person):
    return settings.BASE_URL + reverse("messaging:unsubscribe", args=[unsubscribe_token(person)])


def recipients():
    """Active people who want the newsletter and have an email address."""
    return (
        ConsentRecord.subscribed_people()
        .filter(archived_at__isnull=True)
        .exclude(email="")
        .order_by("last_name", "first_name", "pk")
    )


def footer(person):
    return "\n\n-- \n" + _("You get this because you subscribed. Unsubscribe: %(url)s") % {
        "url": unsubscribe_url(person)
    }


def send_part(batch, limit=None):
    """Send the next ``limit`` emails of a newsletter. Returns how many are left."""
    limit = limit or settings.MESSAGING["newsletter_batch_size"]
    if batch.status == MessageBatch.Status.QUEUED:
        batch.status = MessageBatch.Status.SENDING
        batch.save(update_fields=["status"])
    done = set(batch.messages.values_list("person_id", flat=True))
    waiting = [person_id for person_id, _unit in batch.recipients if person_id not in done]
    # Someone may have unsubscribed since the newsletter was confirmed.
    still_subscribed = set(recipients().filter(pk__in=waiting).values_list("pk", flat=True))
    people = Person.objects.in_bulk(waiting[:limit])
    provider = provider_for(EMAIL)
    with translation.override(translation.get_language() or settings.LANGUAGE_CODE):
        for person_id in waiting[:limit]:
            person = people.get(person_id)
            if person is None:
                continue
            if person_id not in still_subscribed:
                Message.objects.create(
                    batch=batch,
                    person=person,
                    channel=EMAIL,
                    status=Message.Status.FAILED,
                    error=_("Unsubscribed before it was sent."),
                )
                continue
            _send(batch, person, provider)
    left = len(waiting) - min(limit, len(waiting))
    if left == 0:
        batch.status = MessageBatch.Status.DONE
        batch.finished_at = timezone.now()
        batch.save(update_fields=["status", "finished_at"])
    return left


def _send(batch, person, provider):
    values = organisation_placeholders() | {
        "name": person.full_name,
        "first_name": person.first_name,
    }
    subject = MessageTemplate.fill(batch.subject, values)
    body = MessageTemplate.fill(batch.email_body, values) + footer(person)
    message = Message.objects.create(
        batch=batch,
        person=person,
        channel=EMAIL,
        recipient=person.email,
        subject=subject,
        body=body,
        provider=provider.name if provider else "",
    )
    try:
        if provider is None:
            raise ProviderError(_("Email is not set up."))
        url = unsubscribe_url(person)
        extra = {}
        # Providers written before headers existed (e.g. in a plugin) still work.
        if "headers" in inspect.signature(provider.send).parameters:
            extra["headers"] = {
                # One-click unsubscribe in mail programs (RFC 8058).
                "List-Unsubscribe": f"<{url}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            }
        extra |= attachments.email_kwargs(provider, batch)
        result = provider.send(person.email, body, subject=subject, **extra)
    except ProviderError as error:
        message.status = Message.Status.FAILED
        message.error = str(error)
    else:
        message.status = result.status
        message.provider_id = result.provider_id
        message.sent_at = timezone.now()
    message.status_changed_at = timezone.now()
    message.save()
