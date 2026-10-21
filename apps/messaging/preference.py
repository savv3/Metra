"""Which channel a person gets: the one rule every sender follows.

A person's preferred channel comes first and the other one is the fallback:
someone who prefers email gets email, or an SMS when they have no email
address (or the email fails); someone who prefers SMS gets an SMS, or else
an email. Someone who prefers post gets a letter wherever the send-out has
letters (reading links and reminders, invoices, payment reminders). Messages
staff write have no letters, so there they get an SMS, or else an email, as
everyone did before preferences were followed.

A channel counts only when the person has the address for it and a
provider is set up for it.
"""

from apps.register.models import Person

from .registry import EMAIL, SMS, provider_for

ORDER = {
    Person.Channel.EMAIL: (EMAIL, SMS),
    Person.Channel.SMS: (SMS, EMAIL),
    Person.Channel.POST: (SMS, EMAIL),  # used only where there are no letters
}


def reachable(person, channel):
    """Whether a person can get something on a channel here."""
    address = person.phone if channel == SMS else person.email
    return bool(address) and provider_for(channel) is not None


def channel_order(person, offered=(SMS, EMAIL), letters=True):
    """The channels to try for a person, in order, out of those the send-out
    ``offered``. Empty means a letter, or nobody to reach when there are no
    ``letters``."""
    if letters and person.preferred_channel == Person.Channel.POST:
        return []
    order = ORDER.get(person.preferred_channel, ORDER[Person.Channel.EMAIL])
    return [channel for channel in order if channel in offered and reachable(person, channel)]
