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
