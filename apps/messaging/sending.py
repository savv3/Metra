"""Sending send-outs: a round's self-service links and reminders here, and
messages staff write in apps.messaging.broadcast.

Each unit's primary contact gets a new link on their preferred channel,
then on the other one when they have no address for it or it fails, or
else a letter to print. A person whose preferred channel is post gets a
letter. See apps.messaging.preference.
The link's token exists only in memory here and in the message that goes
out; the stored copy of the message has a placeholder instead.
"""

from django.utils import timezone, translation
from django.utils.translation import gettext as _

from apps.selfservice.models import SelfServiceLink, primary_contact

from .broadcast import send_written
from .failures import notify_failures
from .models import Channel, Message, MessageBatch, MessageTemplate, organisation_placeholders
from .preference import channel_order
from .registry import SMS, ProviderError, provider_for


def channels_for(person):
    """The channels to try for a person, in order, with their providers."""
    return [(channel, provider_for(channel)) for channel in channel_order(person)]


def template_text(purpose, channel):
    template = MessageTemplate.objects.filter(purpose=purpose, channel=channel).first()
    if template is None:
        raise ProviderError(_("There is no message template for this. Add one under Settings."))
    return template.subject, template.body


def placeholders(person, unit, round_, link_text):
    return organisation_placeholders() | {
        "name": person.full_name,
        "first_name": person.first_name,
        "link": link_text,
        "closes": _date(round_.closes_on) if round_ else "",
        "period": round_.period_label if round_ else "",
        "reading_type": round_.reading_type.name if round_ else "",
        "unit": unit.name,
    }


def _date(value):
    return f"{value.day}.{value.month}.{value.year}"


def _units(batch):
    round_ = batch.round
    units = round_.expected_units().prefetch_related("unit_contacts__person").order_by("name")
    if batch.scope == MessageBatch.Scope.MISSING:
        units = units.exclude(readings__round=round_)
    return units


def send_batch(batch):
    """Send every message of a batch. Safe to run once; a finished batch is left alone."""
    if batch.status != MessageBatch.Status.QUEUED:
        return
    batch.status = MessageBatch.Status.SENDING
    batch.save(update_fields=["status"])
    if batch.is_written:
        send_written(batch)
        return _finish(batch)
    purpose = (
        MessageTemplate.Purpose.LINK
        if batch.kind == MessageBatch.Kind.LINKS
        else MessageTemplate.Purpose.REMINDER
    )
    with translation.override(translation.get_language() or "sv"):
        for unit in _units(batch):
            send_to_unit(batch, unit, purpose)
    _finish(batch)


def _finish(batch):
    batch.status = MessageBatch.Status.DONE
    batch.finished_at = timezone.now()
    batch.save(update_fields=["status", "finished_at"])
    notify_failures(batch)


def send_to_unit(batch, unit, purpose):
    person = primary_contact(unit)
    if person is None:
        return Message.objects.create(
            batch=batch,
            unit=unit,
            channel=Channel.LETTER,
            status=Message.Status.FAILED,
            error=_("The unit has no contact person."),
        )
    for channel, provider in channels_for(person):
        message = _send(batch, unit, person, purpose, channel, provider)
        if message.status != Message.Status.FAILED:
            return message
    # No phone or email that works: the board prints a letter instead (it
    # makes its own link then, so none is made here).
    return Message.objects.create(
        batch=batch,
        unit=unit,
        person=person,
        channel=Channel.LETTER,
        status=Message.Status.TO_PRINT,
    )


def _send(batch, unit, person, purpose, channel, provider):
    recipient = person.phone if channel == SMS else person.email
    message = Message.objects.create(
        batch=batch,
        unit=unit,
        person=person,
        channel=channel,
        recipient=recipient,
        provider=provider.name,
    )
    try:
        subject, body = template_text(purpose, channel)
    except ProviderError as error:
        return _failed(message, error)
    link, token = SelfServiceLink.create_for(unit, person, batch.round, batch.created_by)
    real = placeholders(person, unit, batch.round, SelfServiceLink.url_for(token))
    stored = placeholders(person, unit, batch.round, _("[personal link]"))
    message.subject = MessageTemplate.fill(subject, stored)
    message.body = MessageTemplate.fill(body, stored)
    try:
        result = provider.send(
            recipient,
            MessageTemplate.fill(body, real),
            subject=MessageTemplate.fill(subject, real),
            callback_url=provider.delivery_callback_url(),
        )
    except ProviderError as error:
        link.revoked = True
        link.save(update_fields=["revoked"])
        return _failed(message, error)
    message.status = result.status
    message.provider_id = result.provider_id
    message.sent_at = message.status_changed_at = timezone.now()
    message.save()
    return message


def _failed(message, error):
    message.status = Message.Status.FAILED
    message.error = str(error)
    message.status_changed_at = timezone.now()
    message.save()
    return message
