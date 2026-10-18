import datetime

import pytest
from django.utils import timezone

from apps.register.models import Person, UnitContact
from apps.selfservice.models import SelfServiceLink, default_expiry, hash_token, primary_contact
from apps.selfservice.service import issue_links


def test_token_is_long_random_and_stored_only_as_hash(unit, owner):
    link, token = SelfServiceLink.create_for(unit, owner)

    assert len(token) >= 43  # 32 bytes, base64: 256 bits
    assert link.token_hash == hash_token(token)
    assert token not in link.token_hash
    assert SelfServiceLink.find(token) == link


def test_expiry_defaults_to_end_of_round_or_configured_days(open_round, settings):
    settings.SELF_SERVICE_LINK_DAYS = 7

    round_end = timezone.localtime(default_expiry(open_round))
    plain = default_expiry()

    assert round_end.date() == open_round.closes_on
    assert round_end.hour == 23
    assert abs(plain - (timezone.now() + datetime.timedelta(days=7))) < datetime.timedelta(
        minutes=1
    )


def test_expired_and_revoked_links_are_not_found(unit, owner):
    expired, expired_token = SelfServiceLink.create_for(
        unit, owner, expires_at=timezone.now() - datetime.timedelta(seconds=1)
    )
    revoked, revoked_token = SelfServiceLink.create_for(unit, owner)
    revoked.revoked = True
    revoked.save()

    assert SelfServiceLink.find(expired_token) is None
    assert SelfServiceLink.find(revoked_token) is None
    assert SelfServiceLink.find("nonsense") is None
    assert SelfServiceLink.find("") is None


def test_a_new_link_stops_the_previous_one(unit, owner, open_round):
    first, first_token = SelfServiceLink.create_for(unit, owner, open_round)
    second, second_token = SelfServiceLink.create_for(unit, owner, open_round)

    assert SelfServiceLink.find(first_token) is None
    assert SelfServiceLink.find(second_token) == second


def test_primary_contact_prefers_owner_then_billing(unit, person):
    billing = Person.objects.create(first_name="Bo")
    contact = Person.objects.create(first_name="Cia")
    UnitContact.objects.create(unit=unit, person=contact, role="contact")
    UnitContact.objects.create(unit=unit, person=billing, role="billing")

    assert primary_contact(unit) == billing
    UnitContact.objects.create(unit=unit, person=person, role="owner")
    assert primary_contact(unit) == person
    person.archive()
    assert primary_contact(unit) == billing


def test_issue_links_skips_units_without_contacts(unit, owner, household, open_round):
    from apps.register.models import Unit

    lonely = Unit.objects.create(unit_type=household, name="Empty")

    issued, skipped = issue_links([unit, lonely], open_round)

    assert [i.unit for i in issued] == [unit]
    assert skipped == [lonely]
    assert issued[0].url.startswith("https://register.example.com/m/")


@pytest.mark.django_db
def test_link_is_audit_logged_without_its_hash(unit, owner):
    from auditlog.models import LogEntry

    link, _token = SelfServiceLink.create_for(unit, owner)

    entry = LogEntry.objects.get_for_object(link).get()
    assert "token_hash" not in entry.changes_dict
