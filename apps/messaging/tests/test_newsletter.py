import re

from auditlog.models import LogEntry
from django.core import mail
from django.urls import reverse

from apps.messaging import newsletter
from apps.messaging.models import ConsentRecord, MessageBatch
from apps.messaging.tasks import send_batch_task
from apps.register.models import Person, UnitContact
from apps.selfservice.models import SelfServiceLink

URL = "/messages/newsletter/new/"


def person(first_name, email="", **extra):
    return Person.objects.create(first_name=first_name, email=email, **extra)


def subscribe(*people):
    for p in people:
        ConsentRecord.record(p, True, ConsentRecord.Source.STAFF)


def test_only_people_who_said_yes_are_recipients(db):
    yes, no, changed, silent = (
        person(name, f"{name.lower()}@example.com") for name in ["Yes", "No", "Changed", "Silent"]
    )
    no_email = person("NoEmail")
    gone = person("Gone", "gone@example.com")
    subscribe(yes, changed, no_email, gone)
    ConsentRecord.record(no, False, ConsentRecord.Source.STAFF)
    ConsentRecord.record(changed, False, ConsentRecord.Source.UNSUBSCRIBE_LINK)
    gone.archive()

    assert list(newsletter.recipients()) == [yes]


def test_recording_the_same_answer_adds_nothing(db):
    p = person("Anna", "a@example.com")

    first = ConsentRecord.record(p, True, ConsentRecord.Source.STAFF)
    again = ConsentRecord.record(p, True, ConsentRecord.Source.SELF_SERVICE)

    assert first == again
    assert ConsentRecord.objects.count() == 1


def test_compose_preview_and_send(admin_client, db):
    anna = person("Anna", "anna@example.com")
    person("Bo", "bo@example.com")
    subscribe(anna)
    data = {"subject": "Nytt från {organisation}", "body": "Hej {first_name}!\n\nÅrsmöte i maj."}

    preview = admin_client.post(URL, {**data, "step": "preview"}, HTTP_ACCEPT_LANGUAGE="en")
    sent = admin_client.post(URL, {**data, "step": "confirm"})

    assert "Hej Anna!" in preview.content.decode()
    assert "Unsubscribe:" in preview.content.decode()
    batch = MessageBatch.objects.get()
    assert sent.url == batch.get_absolute_url()
    assert batch.kind == MessageBatch.Kind.NEWSLETTER
    assert batch.status == MessageBatch.Status.DONE
    assert [m.to for m in mail.outbox] == [["anna@example.com"]]
    email = mail.outbox[0]
    assert email.body.startswith("Hej Anna!")
    link = re.search(r"https://register\.example\.com/unsubscribe/([^/]+)/", email.body)
    assert link
    assert email.extra_headers["List-Unsubscribe"] == f"<{link[0]}>"
    assert email.extra_headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


def test_newsletter_goes_out_in_parts(db, settings, monkeypatch):
    people = [person(f"P{i}", f"p{i}@example.com") for i in range(5)]
    subscribe(*people)
    settings.MESSAGING = {**settings.MESSAGING, "newsletter_batch_size": 2}
    scheduled = []
    monkeypatch.setattr(
        send_batch_task, "schedule", lambda args, delay: scheduled.append((args, delay))
    )
    batch = MessageBatch.objects.create(
        kind=MessageBatch.Kind.NEWSLETTER,
        subject="S",
        email_body="B",
        recipients=[[p.pk, None] for p in people],
    )

    send_batch_task(batch.pk)

    assert len(mail.outbox) == 2
    assert scheduled == [((batch.pk,), settings.MESSAGING["newsletter_pause_seconds"])]
    assert newsletter.send_part(batch) == 1
    assert newsletter.send_part(batch) == 0
    batch.refresh_from_db()
    assert len(mail.outbox) == 5
    assert batch.status == MessageBatch.Status.DONE


def test_someone_who_unsubscribes_meanwhile_is_skipped(db):
    anna, bo = person("Anna", "a@example.com"), person("Bo", "b@example.com")
    subscribe(anna, bo)
    batch = MessageBatch.objects.create(
        kind=MessageBatch.Kind.NEWSLETTER,
        subject="S",
        email_body="B",
        recipients=[[anna.pk, None], [bo.pk, None]],
    )
    ConsentRecord.record(bo, False, ConsentRecord.Source.UNSUBSCRIBE_LINK)

    newsletter.send_part(batch)

    assert [m.to for m in mail.outbox] == [["a@example.com"]]
    assert batch.messages.get(person=bo).status == "failed"


def test_unsubscribe_link_asks_then_unsubscribes(client, db):
    anna = person("Anna", "a@example.com")
    subscribe(anna)
    url = reverse("messaging:unsubscribe", args=[newsletter.unsubscribe_token(anna)])

    page = client.get(url, HTTP_ACCEPT_LANGUAGE="en")
    assert "Unsubscribe from the newsletter?" in page.content.decode()
    assert ConsentRecord.current(anna).subscribed  # opening the link changes nothing

    done = client.post(url, HTTP_ACCEPT_LANGUAGE="en")

    assert "You are unsubscribed" in done.content.decode()
    record = ConsentRecord.current(anna)
    assert (record.subscribed, record.source) == (False, "unsubscribe_link")
    assert done["X-Robots-Tag"] == "noindex, nofollow"


def test_one_click_unsubscribe_needs_no_csrf_token(db):
    from django.test import Client

    anna = person("Anna", "a@example.com")
    subscribe(anna)
    url = reverse("messaging:unsubscribe", args=[newsletter.unsubscribe_token(anna)])

    response = Client(enforce_csrf_checks=True).post(url, {"List-Unsubscribe": "One-Click"})

    assert response.status_code == 200
    assert not ConsentRecord.current(anna).subscribed


def test_forged_unsubscribe_tokens_are_refused(client, db):
    anna = person("Anna", "a@example.com")
    subscribe(anna)
    token = newsletter.unsubscribe_token(anna)

    response = client.post(f"/unsubscribe/{token[:-2]}xx/")

    assert response.status_code == 404
    assert ConsentRecord.current(anna).subscribed


def test_member_chooses_the_newsletter_on_the_self_service_page(client, unit, db):
    anna = person("Anna", "anna@example.com")
    UnitContact.objects.create(unit=unit, person=anna, role="owner")
    link, token = SelfServiceLink.create_for(unit, anna)
    url = f"/m/{token}/"

    page = client.get(url, HTTP_ACCEPT_LANGUAGE="en").content.decode()
    client.post(url, {"action": "newsletter", "subscribed": "1"})

    assert "Do you want the newsletter?" in page
    record = ConsentRecord.current(anna)
    assert (record.subscribed, record.source) == (True, "self_service")
    entry = LogEntry.objects.get_for_object(record).get()
    assert entry.additional_data["self_service_link"] == link.pk
    client.post(url, {"action": "newsletter", "subscribed": "0"})
    assert not ConsentRecord.current(anna).subscribed


def test_staff_record_consent_on_the_person_page(board_client, db):
    anna = person("Anna", "anna@example.com")

    board_client.post(
        reverse("messaging:person_consent", args=[anna.pk]),
        {"subscribed": "1", "note": "Blankett på årsmötet"},
    )
    page = board_client.get(anna.get_absolute_url(), HTTP_ACCEPT_LANGUAGE="en").content.decode()

    record = ConsentRecord.current(anna)
    assert (record.subscribed, record.source, record.note) == (
        True,
        "staff",
        "Blankett på årsmötet",
    )
    assert record.recorded_by.username == "board"
    assert "Wants the newsletter" in page


def test_only_admin_sends_newsletters(role_client, db):
    for role in ["Board", "Treasurer", "Read-only"]:
        assert role_client(role).get(URL).status_code == 403, role
    assert role_client("Admin").get(URL).status_code == 200


def test_read_only_cannot_record_consent(role_client, db):
    anna = person("Anna", "anna@example.com")

    response = role_client("Read-only").post(
        reverse("messaging:person_consent", args=[anna.pk]), {"subscribed": "1"}
    )

    assert response.status_code == 403
    assert ConsentRecord.current(anna) is None
