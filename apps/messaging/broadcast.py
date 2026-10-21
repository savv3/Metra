"""Messages staff write to many people at once, including urgent alerts.

These are service messages about the organisation's own service (a water
leak, a change of opening hours), sent on the basis of membership, so they
do not need newsletter consent. Newsletters come with their own consent.
"""

from dataclasses import dataclass, field

from django.utils import timezone, translation
from django.utils.translation import gettext as _

from apps.register.models import Person, Unit, UnitContact
from apps.register.views import filter_units
from apps.selfservice.models import ROLE_PREFERENCE

from . import attachments
from .models import Channel, Message, MessageBatch, MessageTemplate, organisation_placeholders
from .preference import channel_order, reachable
from .registry import EMAIL, SMS, ProviderError, provider_for
from .sms import segments

EVERYONE = "everyone"
TAG = "tag"
UNIT_TYPE = "unit_type"
FILTERED = "filtered"

ALL_CONTACTS = "all"
MAIN_CONTACT = "main"


@dataclass
class Recipient:
    person: Person
    unit: Unit
    channels: list = field(default_factory=list)  # what this person will get


@dataclass
class Plan:
    """Who gets what, shown before sending and used to send."""

    recipients: list
    unreachable: list

    def count(self, channel):
        return sum(1 for r in self.recipients if channel in r.channels)


def audience_units(scope, value="", filters=None):
    """Active units for a scope: everyone, a tag, a unit type, or the unit list's filters."""
    units = Unit.objects.active().filter(status=Unit.Status.ACTIVE)
    if scope == TAG:
        units = units.filter(tags__id=value)
    elif scope == UNIT_TYPE:
        units = units.filter(unit_type_id=value)
    elif scope == FILTERED:
        filtered, _filters = filter_units(filters or {})
        units = units.filter(pk__in=filtered.values("pk"))
    return units.order_by("name", "pk").distinct()


def people_for(units, contacts):
    """(person, unit) pairs: every active contact, or each unit's main contact.
    A person who is a contact of several units is listed once."""
    pairs, seen = [], set()
    links = (
        UnitContact.objects.filter(unit__in=units, person__archived_at__isnull=True)
        .select_related("person", "unit")
        .order_by("unit__name", "unit_id", "role", "person__last_name")
    )
    if contacts == MAIN_CONTACT:
        by_unit = {}
        for link in links:
            by_unit.setdefault(link.unit_id, []).append(link)
        # Owner first, then billing contact, then other contacts.
        links = [
            min(unit_links, key=lambda link: ROLE_PREFERENCE.index(link.role))
            for unit_links in by_unit.values()
        ]
    for link in links:
        if link.person_id not in seen:
            seen.add(link.person_id)
            pairs.append((link.person, link.unit))
    return pairs


# Send-outs where each person gets one message, on the first channel that works.
ONE_EACH = (MessageBatch.Channels.PREFERRED, MessageBatch.Channels.SMS_OR_EMAIL)


def channels_for(person, mode):
    """The channels a person gets in this send-out, given what is set up.
    For one message each, they are tried in order when sending."""
    if mode == MessageBatch.Channels.PREFERRED:
        # There are no letters here, so those who prefer post get SMS or email.
        return channel_order(person, letters=False)
    if mode == MessageBatch.Channels.SMS:
        wanted = [SMS]
    elif mode == MessageBatch.Channels.EMAIL:
        wanted = [EMAIL]
    else:
        # Both (urgent: everyone gets everything they can, whatever they
        # prefer), or SMS and email for those without a phone.
        wanted = [SMS, EMAIL]
    return [channel for channel in wanted if reachable(person, channel)]


def plan(pairs, mode):
    recipients, unreachable = [], []
    for person, unit in pairs:
        channels = channels_for(person, mode)
        (recipients if channels else unreachable).append(Recipient(person, unit, channels))
    if mode in ONE_EACH:
        # Counted as what they will get first.
        for recipient in recipients:
            recipient.channels = recipient.channels[:1]
    return Plan(recipients, unreachable)


def placeholders(person=None, unit=None):
    values = organisation_placeholders()
    if person is not None:
        values |= {"name": person.full_name, "first_name": person.first_name}
    if unit is not None:
        values["unit"] = unit.name
    return values


def sms_estimate(text, plan_, files=False):
    """(SMS per person, SMS in total) for the text with each person's own values,
    and the link to the files when there are any."""
    if files:
        text += attachments.sms_line_estimate()
    per_person = [
        segments(MessageTemplate.fill(text, placeholders(r.person, r.unit)))[0]
        for r in plan_.recipients
        if SMS in r.channels
    ]
    longest = max(per_person, default=segments(MessageTemplate.fill(text, placeholders()))[0])
    return longest, sum(per_person)


def send_written(batch):
    """Send a staff-written message to the recipients confirmed for the batch."""
    people = Person.objects.in_bulk([person_id for person_id, _unit in batch.recipients])
    units = Unit.objects.in_bulk([unit_id for _person, unit_id in batch.recipients])
    with translation.override(translation.get_language() or "sv"):
        for person_id, unit_id in batch.recipients:
            person, unit = people.get(person_id), units.get(unit_id)
            if person is None:
                continue  # erased since the send-out was confirmed
            channels = channels_for(person, batch.channels)
            if not channels:
                Message.objects.create(
                    batch=batch,
                    person=person,
                    unit=unit,
                    channel=Channel.LETTER,
                    status=Message.Status.FAILED,
                    error=_("No phone number or email address to send to."),
                )
                continue
            for channel in channels:
                message = _send(batch, person, unit, channel)
                if batch.channels in ONE_EACH and message.status != Message.Status.FAILED:
                    break  # one channel is enough, unless it is urgent


def _send(batch, person, unit, channel):
    provider = provider_for(channel)
    values = placeholders(person, unit)
    if channel == SMS:
        recipient, subject, body = person.phone, "", batch.body
    else:
        recipient, subject, body = person.email, batch.subject, batch.email_body or batch.body
    subject = MessageTemplate.fill(subject, values)
    body = stored = MessageTemplate.fill(body, values)
    if channel == SMS:
        line, stored_line = attachments.sms_line(batch)
        body, stored = body + line, stored + stored_line
    message = Message.objects.create(
        batch=batch,
        person=person,
        unit=unit,
        channel=channel,
        recipient=recipient,
        subject=subject,
        body=stored,
        provider=provider.name,
    )
    try:
        extra = attachments.email_kwargs(provider, batch) if channel == EMAIL else {}
        result = provider.send(
            recipient,
            body,
            subject=subject,
            callback_url=provider.delivery_callback_url(),
            **extra,
        )
    except ProviderError as error:
        message.status = Message.Status.FAILED
        message.error = str(error)
    else:
        message.status = result.status
        message.provider_id = result.provider_id
        message.sent_at = timezone.now()
    message.status_changed_at = timezone.now()
    message.save()
    return message
