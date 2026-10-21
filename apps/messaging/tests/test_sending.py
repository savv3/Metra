import re

from django.core import mail
from django.urls import reverse

from apps.messaging import providers
from apps.messaging.models import MessageBatch, MessageTemplate
from apps.messaging.registry import ProviderError, provider_for, registry
from apps.messaging.sending import send_batch
from apps.messaging.tasks import automatic_reminders
from apps.readings.models import Reading
from apps.selfservice.models import SelfServiceLink

LINK = re.compile(r"https://register\.example\.com/m/([\w-]+)/")


def send(round_, kind="links", scope="all"):
    batch = MessageBatch.objects.create(kind=kind, scope=scope, round=round_)
    send_batch(batch)
    return batch


def test_preferred_channel_then_the_other_then_letter(open_round, make_household):
    sms = make_household(
        "A", first_name="Anna", phone="040 123 4567", email="a@example.com", preferred_channel="sms"
    )
    email = make_household("B", first_name="Bo", email="bo@example.com")
    letter = make_household("C", first_name="Cia")
    nobody = make_household("D")

    batch = send(open_round)

    by_unit = {m.unit: m for m in batch.messages.all()}
    assert (by_unit[sms].channel, by_unit[sms].status) == ("sms", "sent")
    assert (by_unit[email].channel, by_unit[email].recipient) == ("email", "bo@example.com")
    assert (by_unit[letter].channel, by_unit[letter].status) == ("letter", "to_print")
    assert by_unit[nobody].status == "failed"
    assert batch.status == MessageBatch.Status.DONE
    assert len(providers.outbox) == 1
    assert len(mail.outbox) == 1


def test_messages_carry_a_working_link_that_is_not_stored(open_round, make_household):
    unit = make_household("Byvägen 4", first_name="Anna", phone="0401234567")

    batch = send(open_round)

    sent = providers.outbox[0]["body"]
    token = LINK.search(sent)[1]
    link = SelfServiceLink.find(token)
    assert (link.unit, link.round) == (unit, open_round)
    stored = batch.messages.get()
    assert token not in stored.body
    assert "Anna" in stored.body and "31.10.2026" in stored.body
    assert "[" in stored.body  # the link placeholder


def test_failed_sms_falls_back_to_email_and_its_link_is_stopped(open_round, make_household):
    make_household(
        "A", first_name="Anna", phone="+000", email="anna@example.com", preferred_channel="sms"
    )

    batch = send(open_round)

    sms, email = batch.messages.order_by("pk")
    assert (sms.channel, sms.status, sms.error) == ("sms", "failed", "Dummy failure")
    assert (email.channel, email.status) == ("email", "sent")
    assert SelfServiceLink.objects.active().count() == 1
    assert LINK.search(mail.outbox[0].body)


def test_the_preferred_channel_comes_first(open_round, make_household):
    prefers_email = make_household(
        "A", first_name="A", phone="0401234567", email="a@example.com", preferred_channel="email"
    )
    prefers_sms = make_household(
        "B", first_name="B", phone="0402345678", email="b@example.com", preferred_channel="sms"
    )
    prefers_post = make_household(
        "C", first_name="C", phone="0403456789", email="c@example.com", preferred_channel="post"
    )
    email_but_no_address = make_household(
        "D", first_name="D", phone="0404567890", preferred_channel="email"
    )
    sms_but_no_phone = make_household(
        "E", first_name="E", email="e@example.com", preferred_channel="sms"
    )

    batch = send(open_round)

    channel = {m.unit: m.channel for m in batch.messages.all()}
    assert channel == {
        prefers_email: "email",
        prefers_sms: "sms",
        prefers_post: "letter",
        email_but_no_address: "sms",
        sms_but_no_phone: "email",
    }


def test_reminders_follow_the_preference_too(open_round, make_household):
    prefers_email = make_household(
        "A", first_name="A", phone="0401234567", email="a@example.com", preferred_channel="email"
    )
    prefers_post = make_household(
        "B", first_name="B", phone="0402345678", email="b@example.com", preferred_channel="post"
    )

    batch = send(open_round, kind="reminder", scope="missing")

    assert batch.messages.get(unit=prefers_email).channel == "email"
    assert batch.messages.get(unit=prefers_post).channel == "letter"


def test_reminder_goes_only_to_units_missing_a_reading(open_round, make_household):
    done = make_household("A", first_name="A", email="a@example.com")
    missing = make_household("B", first_name="B", email="b@example.com")
    Reading.objects.create(round=open_round, unit=done, value=1)

    batch = send(open_round, kind="reminder", scope="missing")

    assert [m.unit for m in batch.messages.all()] == [missing]
    assert mail.outbox[0].subject == "Påminnelse: Vattenmätare 2026"


def test_edited_template_is_used(open_round, make_household):
    MessageTemplate.objects.filter(purpose="link", channel="sms").update(
        body="Läs mätaren, {name}: {link} ({unknown})"
    )
    make_household("A", first_name="Anna", last_name="L", phone="0401234567")

    send(open_round)

    body = providers.outbox[0]["body"]
    assert body.startswith("Läs mätaren, Anna L: https://register.example.com/m/")
    assert body.endswith("({unknown})")


def test_a_batch_is_sent_only_once(open_round, make_household):
    make_household("A", first_name="A", phone="0401234567")
    batch = send(open_round)

    send_batch(batch)

    assert len(providers.outbox) == 1


def test_no_sms_provider_means_email(open_round, make_household, settings):
    settings.MESSAGING = {**settings.MESSAGING, "sms_provider": ""}
    make_household("A", first_name="A", phone="0401234567", email="a@example.com")

    batch = send(open_round)

    assert provider_for("sms") is None
    assert batch.messages.get().channel == "email"


def test_automatic_reminders_are_off_by_default(open_round, make_household, settings):
    make_household("A", first_name="A", phone="0401234567")
    assert settings.MESSAGING["reminder_days_before_close"] is None

    automatic_reminders.call_local()

    assert not MessageBatch.objects.exists()


def test_automatic_reminder_runs_once_per_round(open_round, make_household, settings):
    import datetime

    from django.utils import timezone

    make_household("A", first_name="A", phone="0401234567")
    settings.MESSAGING = {**settings.MESSAGING, "reminder_days_before_close": 3}
    open_round.closes_on = timezone.localdate() + datetime.timedelta(days=3)
    open_round.save()

    automatic_reminders.call_local()
    automatic_reminders.call_local()

    batch = MessageBatch.objects.get()
    assert batch.kind == MessageBatch.Kind.AUTO_REMINDER
    assert len(providers.outbox) == 1


def test_registry_rejects_unknown_providers():
    import pytest

    with pytest.raises(ProviderError):
        registry.get("sms", "nope")
    assert {"46elks", "console", "dummy"} <= set(registry.names("sms"))


def test_staff_send_and_see_the_batch(board_client, open_round, make_household):
    make_household("A", first_name="Anna", phone="0401234567")
    make_household("B", first_name="Bo")

    response = board_client.post(
        reverse("messaging:round_send", args=[open_round.pk]), {"kind": "links"}
    )

    batch = MessageBatch.objects.get()
    assert response.url == batch.get_absolute_url()
    assert batch.created_by.username == "board"
    page = board_client.get(batch.get_absolute_url(), HTTP_ACCEPT_LANGUAGE="en")
    body = page.content.decode()
    assert "1 household needs a letter" in body
    assert reverse("selfservice:round_print", args=[open_round.pk]) in body


def test_print_letters_for_unreached_units_only(board_client, open_round, make_household):
    from apps.register.models import Unit

    make_household("A", first_name="Anna", phone="0401234567")
    paper = make_household("B", first_name="Bo")

    board_client.post(
        reverse("selfservice:round_print", args=[open_round.pk]),
        {"units": [paper.pk], "layout": "letters"},
    )

    assert [link.unit for link in SelfServiceLink.objects.all()] == [paper]
    assert Unit.objects.count() == 2


def test_round_pages_offer_sending(board_client, open_round):
    detail = board_client.get(open_round.get_absolute_url(), HTTP_ACCEPT_LANGUAGE="en")
    links = board_client.get(
        reverse("selfservice:round_links", args=[open_round.pk]), HTTP_ACCEPT_LANGUAGE="en"
    )

    for page in (detail, links):
        assert "Send reminder to units missing a reading" in page.content.decode()


def test_read_only_cannot_send(role_client, open_round):
    client = role_client("Read-only")

    response = client.post(reverse("messaging:round_send", args=[open_round.pk]), {"kind": "links"})
    page = client.get(open_round.get_absolute_url(), HTTP_ACCEPT_LANGUAGE="en").content.decode()

    assert response.status_code == 403
    assert "Send links to all units" not in page
    assert client.get(reverse("messaging:batch_list")).status_code == 200
