import re

import pytest
from django.core import mail
from django.urls import reverse

from apps.messaging import broadcast, providers
from apps.messaging.models import Message, MessageBatch
from apps.messaging.sms import segments
from apps.register.models import Person, Tag, Unit, UnitContact, UnitType

URL = "/messages/new/"


def compose(client, step="preview", **data):
    fields = {
        "scope": "everyone",
        "contacts": "all",
        "channels": "sms_and_email",
        "body": "Vattnet stängs av kl 14. /{organisation}",
        "subject": "Vattenläcka",
        "step": step,
    }
    return client.post(URL, {**fields, **data}, HTTP_ACCEPT_LANGUAGE="en")


def test_sms_segments():
    assert segments("Hej på dig, åäö!") == (1, 16, 160)
    assert segments("a" * 160)[0] == 1
    assert segments("a" * 161) == (2, 161, 153)
    assert segments("€" * 80)[0] == 1  # extended characters count twice
    assert segments("Läcka 💧") == (1, 8, 70)
    assert segments("💧" * 40)[0] == 2


def test_people_are_listed_once_and_main_contact_option(make_household):
    a = make_household("A", first_name="Anna", phone="0401")
    b = make_household("B", first_name="Bo", phone="0402")
    anna = a.unit_contacts.get().person
    UnitContact.objects.create(unit=b, person=anna, role="contact")
    partner = Person.objects.create(first_name="Erik", phone="0403")
    UnitContact.objects.create(unit=a, person=partner, role="contact")
    units = broadcast.audience_units(broadcast.EVERYONE)

    everyone = broadcast.people_for(units, broadcast.ALL_CONTACTS)
    main = broadcast.people_for(units, broadcast.MAIN_CONTACT)

    assert sorted(p.first_name for p, _u in everyone) == ["Anna", "Bo", "Erik"]
    assert sorted(p.first_name for p, _u in main) == ["Anna", "Bo"]


def test_audience_by_tag_type_and_filters_only_active_units(make_household, household):
    north = Tag.objects.create(name="North")
    tagged = make_household("Tagged", first_name="T")
    tagged.tags.add(north)
    make_household("Other", first_name="O")
    make_household("Gone", first_name="G").archive()
    club = Unit.objects.create(unit_type=UnitType.objects.create(name="Club"), name="Club")

    assert list(broadcast.audience_units(broadcast.TAG, north.pk)) == [tagged]
    assert club not in broadcast.audience_units(broadcast.UNIT_TYPE, household.pk)
    assert [u.name for u in broadcast.audience_units(broadcast.EVERYONE)] == [
        "Club",
        "Other",
        "Tagged",
    ]
    filtered = broadcast.audience_units(broadcast.FILTERED, filters={"q": "tag"})
    assert list(filtered) == [tagged]


def test_preview_shows_counts_and_who_cannot_be_reached(admin_client, make_household):
    make_household("A", first_name="Anna", phone="0401234567", email="a@example.com")
    make_household("B", first_name="Bo", email="bo@example.com")
    make_household("C", first_name="Cia", last_name="Utan")

    response = compose(admin_client)

    body = response.content.decode()
    assert response.context["sms_count"] == 1
    assert response.context["email_count"] == 2
    assert "1 person cannot be reached this way" in body
    assert "Cia Utan" in body
    assert "The message, as Anna gets it" in body
    assert not MessageBatch.objects.exists()
    assert not providers.outbox and not mail.outbox


def test_urgent_alert_sends_sms_and_email_to_everyone(admin_client, make_household):
    a = make_household(
        "A", first_name="Anna", phone="0401234567", email="a@example.com", preferred_channel="post"
    )
    make_household("B", first_name="Bo", email="bo@example.com")
    make_household("C", first_name="Cia")

    response = compose(admin_client, step="confirm", urgent="on")

    batch = MessageBatch.objects.get()
    assert response.url == batch.get_absolute_url()
    assert batch.kind == MessageBatch.Kind.ALERT
    assert batch.status == MessageBatch.Status.DONE
    assert [m["to"] for m in providers.outbox] == ["0401234567"]
    assert sorted(m.to[0] for m in mail.outbox) == ["a@example.com", "bo@example.com"]
    assert mail.outbox[0].subject == "Vattenläcka"
    assert mail.outbox[0].extra_headers["X-Metra-Send-Out"] == str(batch.pk)
    assert batch.messages.filter(unit=a).count() == 2
    assert batch.messages.get(status="failed").error.startswith("No phone number")


def test_sms_or_email_sends_one_message_each(admin_client, make_household):
    make_household("A", first_name="Anna", phone="0401234567", email="a@example.com")
    make_household("B", first_name="Bo", email="bo@example.com")

    compose(admin_client, step="confirm", channels="sms_or_email")

    assert len(providers.outbox) == 1
    assert [m.to for m in mail.outbox] == [["bo@example.com"]]


def test_failed_sms_falls_back_to_email_when_one_is_enough(admin_client, make_household):
    make_household("A", first_name="Anna", phone="+000", email="a@example.com")

    compose(admin_client, step="confirm", channels="sms_or_email")

    statuses = list(Message.objects.order_by("pk").values_list("channel", "status"))
    assert statuses == [("sms", "failed"), ("email", "sent")]


def test_placeholders_are_filled_per_person(admin_client, make_household):
    from apps.register.models import Organisation

    Organisation.objects.create(name="Byns vatten", phone="018-123")
    make_household("Byvägen 4", first_name="Anna", phone="0401234567")

    compose(
        admin_client,
        step="confirm",
        channels="sms",
        body="Hej {first_name} på {unit}! Ring {organisation_phone}.",
    )

    assert providers.outbox[0]["body"] == "Hej Anna på Byvägen 4! Ring 018-123."
    assert Message.objects.get().body == "Hej Anna på Byvägen 4! Ring 018-123."


def test_edit_goes_back_without_sending(admin_client, make_household):
    make_household("A", first_name="Anna", phone="0401234567")

    response = compose(admin_client, step="confirm", edit="1")

    assert response.context["step"] == "edit"
    assert not MessageBatch.objects.exists()


def test_email_needs_a_subject(admin_client, make_household):
    response = compose(admin_client, subject="")

    assert "subject" in response.context["form"].errors


def test_urgent_link_preselects_both_channels(admin_client):
    form = admin_client.get(URL + "?urgent=1").context["form"]

    assert form.initial["channels"] == "sms_and_email"
    assert form.initial["urgent"] is True


def test_filtered_unit_list_link(admin_client, make_household):
    make_household("Byvägen 4", first_name="Anna", phone="0401234567")

    units = admin_client.get(reverse("register:unit_list"), {"q": "byv"}).content.decode()
    form = admin_client.get(URL, {"filters": "q=byv"}).context["form"]

    assert "/messages/new/?filters=q%3Dbyv" in units
    assert form.initial["scope"] == "filtered"


def test_sms_count_endpoint(admin_client):
    response = admin_client.get(
        reverse("messaging:sms_count"), {"body": "x" * 200}, HTTP_ACCEPT_LANGUAGE="en"
    )

    assert "2 SMS each" in response.content.decode()


def test_only_admin_can_send_to_everyone(role_client, make_household):
    for role in ["Board", "Treasurer", "Read-only"]:
        client = role_client(role)
        assert client.get(URL).status_code == 403, role
        assert compose(client, step="confirm").status_code == 403, role
        page = client.get(reverse("messaging:batch_list")).content.decode()
        assert "Urgent alert" not in page, role
    assert not MessageBatch.objects.exists()


def test_alert_can_publish_a_notice(admin_client, make_household):
    from apps.core.models import Notice

    make_household("A", first_name="Anna", phone="0401234567")

    compose(
        admin_client,
        step="confirm",
        urgent="on",
        notice="on",
        notice_until="2030-01-01T18:00",
        body="Vattnet är avstängt. Ring {organisation_phone}.",
    )

    notice = Notice.objects.get()
    batch = MessageBatch.objects.get()
    assert batch.notice == notice
    assert notice.level == "urgent"
    assert notice.text.startswith("Vattnet är avstängt. Ring")
    assert notice.ends_at.year == 2030
    page = admin_client.get(batch.get_absolute_url(), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert "Remove the notice" in page

    admin_client.post(reverse("messaging:notice_end", args=[notice.pk]))

    notice.refresh_from_db()
    assert not notice.is_current


def test_notice_needs_its_own_text_when_the_message_is_personal(admin_client, make_household):
    response = compose(admin_client, notice="on", body="Hej {first_name}, vattnet är avstängt.")

    assert "notice_text" in response.context["form"].errors


def test_notice_option_needs_the_permission(client, make_user):
    from django.contrib.auth.models import Group, Permission

    senders = Group.objects.create(name="Senders")
    senders.permissions.add(Permission.objects.get(codename="send_broadcast"))
    sender = make_user("sender")
    sender.groups.add(senders)
    client.force_login(sender)

    form = client.get(URL).context["form"]

    assert "notice" not in form.fields


def test_email_only_needs_no_sms_text(admin_client, make_household):
    make_household("A", first_name="Anna", phone="0401234567", email="a@example.com")

    response = compose(
        admin_client, step="confirm", channels="email", body="", email_body="Hej {first_name}!"
    )

    batch = MessageBatch.objects.get()
    assert response.url == batch.get_absolute_url()
    assert [m.body for m in mail.outbox] == ["Hej Anna!"]
    assert providers.outbox == []
    assert "Hej {first_name}!" in str(batch)


def test_email_only_shows_the_email_text_in_the_preview(admin_client, make_household):
    make_household("A", first_name="Anna", email="a@example.com")

    page = compose(admin_client, channels="email", body="", email_body="Hej {first_name}!")

    assert "Hej Anna!" in page.content.decode()


def test_sms_only_needs_no_email_fields(admin_client, make_household):
    make_household("A", first_name="Anna", phone="0401234567", email="a@example.com")

    compose(admin_client, step="confirm", channels="sms", subject="", email_body="")

    assert len(providers.outbox) == 1
    assert mail.outbox == []


@pytest.mark.parametrize(
    "channels, missing, field",
    [
        ("email", {"body": "", "email_body": ""}, "email_body"),
        ("sms", {"body": ""}, "body"),
        ("sms_or_email", {"body": ""}, "body"),
        ("sms_and_email", {"body": ""}, "body"),
        ("preferred", {"body": ""}, "body"),
        ("preferred", {"subject": ""}, "subject"),
    ],
)
def test_the_chosen_channels_text_is_needed(admin_client, make_household, channels, missing, field):
    make_household("A", first_name="Anna", phone="0401234567", email="a@example.com")

    response = compose(admin_client, step="confirm", channels=channels, **missing)

    assert response.status_code == 200
    assert response.context["form"].errors[field]
    assert not MessageBatch.objects.exists()


def test_the_form_shows_only_the_chosen_channels_fields(admin_client):
    page = admin_client.get(URL + "?urgent=1").content.decode()
    assert 'data-channels="preferred sms sms_or_email sms_and_email">' in page  # both shown

    page = compose(admin_client, channels="email", body="", email_body="").content.decode()
    assert 'data-channels="preferred sms sms_or_email sms_and_email" hidden>' in page
    assert 'data-channels="preferred email sms_or_email sms_and_email">' in page

    page = admin_client.get(URL).content.decode()  # the preferred channel needs both texts
    assert 'data-channels="preferred sms sms_or_email sms_and_email">' in page
    assert 'data-channels="preferred email sms_or_email sms_and_email">' in page


def test_the_preferred_channel_is_the_default_and_the_others_are_tucked_away(admin_client):
    page = admin_client.get(URL, HTTP_ACCEPT_LANGUAGE="en").content.decode()

    assert re.search(r'value="preferred"[^>]*checked', page)
    assert "<details>" in page and "Other options" in page
    assert page.index('value="preferred"') < page.index("<details>") < page.index('value="sms"')


def test_other_options_are_open_when_one_of_them_is_chosen(admin_client):
    # After a validation error, the choice made stays visible.
    page = compose(admin_client, channels="sms", body="").content.decode()
    assert "<details open>" in page
    assert re.search(r'value="sms"[^>]*checked', page)

    # Urgent alerts still default to both.
    page = admin_client.get(URL + "?urgent=1").content.decode()
    assert "<details open>" in page
    assert re.search(r'value="sms_and_email"[^>]*checked', page)


def test_preferred_channel_is_followed(admin_client, make_household):
    email = make_household(
        "A", first_name="Anna", phone="0401", email="a@example.com", preferred_channel="email"
    )
    sms = make_household(
        "B", first_name="Bo", phone="0402", email="bo@example.com", preferred_channel="sms"
    )
    no_email = make_household("C", first_name="Cia", phone="0403", preferred_channel="email")
    post = make_household(
        "D", first_name="Dan", phone="0404", email="d@example.com", preferred_channel="post"
    )
    post_email = make_household(
        "E", first_name="Eva", email="e@example.com", preferred_channel="post"
    )
    make_household("F", first_name="Fia", last_name="Utan", preferred_channel="sms")

    response = compose(admin_client, channels="preferred")

    assert response.context["sms_count"] == 3  # Bo, Cia, Dan
    assert response.context["email_count"] == 2  # Anna, Eva
    assert [r.person.first_name for r in response.context["plan"].unreachable] == ["Fia"]
    assert "The message, as Anna gets it" in response.content.decode()

    compose(admin_client, step="confirm", channels="preferred")

    channel = {m.unit: m.channel for m in Message.objects.exclude(status="failed")}
    assert channel == {
        email: "email",
        sms: "sms",
        no_email: "sms",
        post: "sms",
        post_email: "email",
    }
    assert MessageBatch.objects.get().channels == "preferred"


def test_failed_preferred_channel_falls_back_to_the_other(admin_client, make_household):
    make_household(
        "A", first_name="Anna", phone="+000", email="a@example.com", preferred_channel="sms"
    )

    compose(admin_client, step="confirm", channels="preferred")

    statuses = list(Message.objects.order_by("pk").values_list("channel", "status"))
    assert statuses == [("sms", "failed"), ("email", "sent")]


def test_explicit_options_ignore_the_preference(admin_client, make_household):
    make_household(
        "A", first_name="Anna", phone="0401", email="a@example.com", preferred_channel="email"
    )

    response = compose(admin_client, channels="sms_or_email")
    assert (response.context["sms_count"], response.context["email_count"]) == (1, 0)
    response = compose(admin_client, channels="sms")
    assert (response.context["sms_count"], response.context["email_count"]) == (1, 0)


def test_a_tag_reaches_people_who_carry_it_themselves(admin_client, make_household):
    sms_test = Tag.objects.create(name="sms-test")
    tagged_unit = make_household("Tagged", first_name="Unit", last_name="Contact", phone="0401")
    tagged_unit.tags.add(sms_test)
    loner = Person.objects.create(first_name="Christian", phone="0402")
    loner.tags.add(sms_test)
    member = Person.objects.create(first_name="Member", phone="0403")
    member.tags.add(sms_test)
    UnitContact.objects.create(unit=make_household("Own"), person=member, role="owner")

    response = compose(admin_client, scope="tag", tag=sms_test.pk, channels="sms")

    recipients = {r.person.first_name: r.unit for r in response.context["plan"].recipients}
    assert set(recipients) == {"Unit", "Christian", "Member"}
    assert recipients["Christian"] is None
    assert recipients["Member"].name == "Own"

    compose(admin_client, step="confirm", scope="tag", tag=sms_test.pk, channels="sms")

    batch = MessageBatch.objects.get()
    assert [loner.pk, None] in batch.recipients
    assert Message.objects.get(person=loner).recipient == "0402"


def test_the_check_page_says_why_nobody_matches(admin_client, make_household):
    sms_test = Tag.objects.create(name="sms-test")
    make_household("Empty").tags.add(sms_test)

    response = compose(admin_client, scope="tag", tag=sms_test.pk, channels="sms")

    body = response.content.decode()
    assert "Nobody matches these choices" in body
    assert "The unit that matches has no contacts." in body
    assert ">Empty</a>" in body

    unused = Tag.objects.create(name="unused")
    response = compose(admin_client, scope="tag", tag=unused.pk, channels="sms")
    assert "No active unit has this tag, and nobody carries it themselves." in (
        response.content.decode()
    )
