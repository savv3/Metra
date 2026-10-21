import re

import pytest
from auditlog.models import LogEntry
from django.core import mail
from django.urls import reverse

from apps.messaging.models import MessageBatch
from apps.selfservice.models import SelfServiceLink
from metra_meetings.models import Meeting


def test_send_the_notice_with_the_agenda(admin, meeting, make_household, fake_pdf):
    make_household("Byvägen 4", first_name="Anna", email="anna@example.com")
    make_household("Strandvägen 1", first_name="Bo", email="bo@example.com")
    url = reverse("metra_meetings:send_notice", args=[meeting.pk])

    response = admin.post(url)

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("messaging:compose") + "?draft=")
    form = admin.get(response["Location"]).content.decode()
    assert "Notice: Annual meeting 2026 on" in form
    assert "Village hall" in form
    assert "§ 2. Accounts for 2025" in form
    ticked = re.findall(r'name="attachments" value="(\d+)"[^>]*checked', form)
    assert len(ticked) == 1 and "agenda-2026-04-20-annual-meeting-2026.pdf" in form

    # Staff choose the recipients and send as with any message.
    data = {
        "scope": "everyone",
        "contacts": "all",
        "channels": "email",
        "subject": "Notice: Annual meeting 2026",
        "email_body": "Dear {first_name}, welcome.",
        "attachments": ticked,
    }
    compose = response["Location"]
    preview = admin.post(compose, {**data, "step": "preview"}).content.decode()
    assert "Send now to 2 people" in preview
    admin.post(compose, {**data, "step": "confirm"})

    batch = MessageBatch.objects.get()
    assert [a.name for a in batch.attachments.all()] == [
        "agenda-2026-04-20-annual-meeting-2026.pdf"
    ]
    assert sorted(m.to[0] for m in mail.outbox) == ["anna@example.com", "bo@example.com"]
    assert mail.outbox[0].attachments == [
        ("agenda-2026-04-20-annual-meeting-2026.pdf", fake_pdf, "application/pdf")
    ]
    assert "Dear Anna" in next(m for m in mail.outbox if m.to == ["anna@example.com"]).body


@pytest.fixture
def member(make_household):
    """(token, person) of a member with a personal link."""
    unit, anna = make_household("Byvägen 4", first_name="Anna")
    _link, token = SelfServiceLink.create_for(unit, anna)
    return token, anna


@pytest.fixture
def approved(meeting, make_user):
    checker = make_user("checker", "Read-only")
    meeting.checkers.set([checker])
    meeting.status = Meeting.Status.HELD
    meeting.save()
    meeting.approve(checker)
    return meeting


def member_page(client, token):
    return client.get(f"/m/{token}/", HTTP_ACCEPT_LANGUAGE="en").content.decode()


def minutes_url(token, meeting):
    return reverse("metra_meetings:member_minutes", args=[token, meeting.pk])


def test_members_see_minutes_only_once_approved(client, meeting, member, make_user):
    token, _anna = member

    assert "Meeting minutes" not in member_page(client, token)
    assert client.get(minutes_url(token, meeting)).status_code == 404

    checker = make_user("checker", "Read-only")
    meeting.checkers.set([checker])
    meeting.status = Meeting.Status.HELD
    meeting.save()
    meeting.approve(checker)

    page = member_page(client, token)
    assert "Meeting minutes" in page
    assert minutes_url(token, meeting) in page


def test_member_downloads_the_approved_minutes(client, approved, member, fake_pdf):
    token, anna = member

    response = client.get(minutes_url(token, approved))

    assert response.status_code == 200
    assert response.content == fake_pdf
    assert response["Content-Type"] == "application/pdf"
    assert "no-store" in response["Cache-Control"]
    assert response["X-Robots-Tag"] == "noindex, nofollow"
    assert response["Referrer-Policy"] == "same-origin"
    view = LogEntry.objects.get_for_object(approved).get(action=LogEntry.Action.ACCESS)
    assert view.additional_data["person_id"] == anna.pk


def test_bad_token_gets_nothing(client, approved, fake_pdf):
    response = client.get(minutes_url("not-a-real-token", approved))

    assert response.status_code == 404
    assert response["Referrer-Policy"] == "same-origin"


def test_minutes_not_for_members_stay_hidden(client, meeting, member, make_user, fake_pdf):
    token, _anna = member
    meeting.members_can_read = False
    meeting.save()
    checker = make_user("checker", "Read-only")
    meeting.checkers.set([checker])
    meeting.status = Meeting.Status.HELD
    meeting.save()
    meeting.approve(checker)

    assert "Meeting minutes" not in member_page(client, token)
    assert client.get(minutes_url(token, meeting)).status_code == 404
