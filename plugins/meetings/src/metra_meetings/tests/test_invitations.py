import datetime

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone, translation

from apps.messaging.models import MessageBatch
from apps.plugins import api, state
from apps.plugins.models import PluginState
from metra_meetings import ical, invitations, tasks
from metra_meetings.models import INVITATION, AgendaItem, Meeting


def url(name, *args):
    return reverse(f"metra_meetings:{name}", args=args)


@pytest.fixture(autouse=True)
def english():
    """Texts made outside a request (the worker's) in English, like the pages."""
    with translation.override("en"):
        yield


@pytest.fixture
def upcoming(db):
    """A board meeting in ten days, called."""
    meeting = Meeting.objects.create(
        kind=Meeting.Kind.BOARD,
        title="Board meeting, December",
        starts_at=timezone.now().replace(second=0, microsecond=0) + datetime.timedelta(days=10),
        place="Hall, room 2; upstairs",
        notes="Coffee from 18:00.",
        status=Meeting.Status.CALLED,
    )
    AgendaItem.objects.create(meeting=meeting, order=1, title="Opening")
    return meeting


@pytest.fixture
def invited(upcoming, make_household, fake_pdf, django_capture_on_commit_callbacks):
    """Anna and Bo got the invitation by email nine days ago."""
    _unit, anna = make_household("Byvägen 4", first_name="Anna", email="anna@example.com")
    unit, bo = make_household("Strandvägen 1", first_name="Bo", email="bo@example.com")
    with django_capture_on_commit_callbacks(execute=True):
        batch = api.send_message(
            [(anna, None), (bo, unit)],
            "Notice",
            "Dear {first_name}, welcome.",
            source=upcoming.source(INVITATION),
        )
    MessageBatch.objects.filter(pk=batch.pk).update(
        created_at=timezone.now() - datetime.timedelta(days=9)
    )
    mail.outbox.clear()
    return upcoming


def reminder_day(meeting):
    return meeting.reminder_date()


# The calendar file.


def test_the_calendar_file(upcoming, settings):
    settings.BASE_URL = "https://vatten.example.org"
    upcoming.notes = "Coffee from 18:00, " + "very long text " * 10

    text = ical.ics(upcoming).decode()

    lines = text.split("\r\n")
    assert lines[0] == "BEGIN:VCALENDAR" and text.endswith("END:VCALENDAR\r\n")
    assert f"UID:meeting-{upcoming.pk}@vatten.example.org" in lines
    assert "SEQUENCE:0" in lines
    start = upcoming.starts_at.astimezone(datetime.UTC)
    assert f"DTSTART:{start:%Y%m%dT%H%M%SZ}" in lines
    assert "LOCATION:Hall\\, room 2\\; upstairs" in lines
    assert "SUMMARY:Board meeting\\, December" in lines
    assert all(len(line.encode()) <= 75 for line in lines)
    unfolded = text.replace("\r\n ", "")
    assert "Coffee from 18:00\\, very long" in unfolded
    assert "\\n\\nAgenda:\\n§ 1. Opening" in unfolded


# Reminders.


def test_the_reminder_goes_to_everyone_invited_once(invited, django_capture_on_commit_callbacks):
    day = reminder_day(invited)
    assert day == timezone.localtime(invited.starts_at).date() - datetime.timedelta(days=3)
    assert invitations.due_reminders(day - datetime.timedelta(days=1)) == []
    assert invitations.due_reminders(day) == [invited]

    with django_capture_on_commit_callbacks(execute=True):
        batch = invitations.send_reminder(invited)

    assert batch.source == f"metra_meetings:meeting:{invited.pk}:reminder"
    assert sorted(m.to[0] for m in mail.outbox) == ["anna@example.com", "bo@example.com"]
    anna = next(m for m in mail.outbox if m.to == ["anna@example.com"])
    assert anna.subject.startswith("Reminder: Board meeting, December on")
    assert "Dear Anna," in anna.body and "Place: Hall, room 2; upstairs" in anna.body
    assert [a[0] for a in anna.attachments][1].endswith(".ics")
    invited.refresh_from_db()
    assert invited.reminded_at is not None
    assert invitations.due_reminders(day) == []


def test_the_periodic_task_sends_due_reminders(
    invited, monkeypatch, django_capture_on_commit_callbacks
):
    day = reminder_day(invited)
    monkeypatch.setattr(timezone, "localdate", lambda *args: day)

    with django_capture_on_commit_callbacks(execute=True):
        tasks.meeting_reminders.call_local()

    assert len(mail.outbox) == 2


def test_no_reminders_while_the_add_on_is_off(invited, monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *args: reminder_day(invited))
    PluginState.objects.create(name="meetings", enabled=False)
    state.forget()
    try:
        tasks.meeting_reminders.call_local()
    finally:
        PluginState.objects.all().delete()
        state.forget()

    assert mail.outbox == []
    invited.refresh_from_db()
    assert invited.reminded_at is None


def test_no_reminder_when_turned_off_or_invited_late(invited):
    day = reminder_day(invited)
    invited.invitations().update(created_at=timezone.now() + datetime.timedelta(days=8))
    assert invitations.due_reminders(day) == []

    invited.invitations().update(created_at=timezone.now())
    invited.remind_days_before = None
    invited.save()
    assert invitations.due_reminders(day) == []


def test_no_reminder_without_invitations_or_before_the_meeting_is_called(upcoming, invited):
    other = Meeting.objects.create(
        title="Not invited", starts_at=upcoming.starts_at, status=Meeting.Status.CALLED
    )
    invited.status = Meeting.Status.DRAFT
    invited.save()

    assert invitations.due_reminders(reminder_day(other)) == []


def test_people_archived_since_get_no_reminder(invited, django_capture_on_commit_callbacks):
    api.Person.objects.filter(first_name="Bo").update(archived_at=timezone.now())

    with django_capture_on_commit_callbacks(execute=True):
        invitations.send_reminder(invited)

    assert [m.to for m in mail.outbox] == [["anna@example.com"]]


def test_staff_send_a_reminder_by_hand(admin, invited, django_capture_on_commit_callbacks):
    page = admin.get(invited.get_absolute_url()).content.decode()
    assert "2 people are invited." in page
    assert "Send a reminder to 2 people now" in page

    with django_capture_on_commit_callbacks(execute=True):
        response = admin.post(url("send_reminder", invited.pk))

    assert response.status_code == 302
    assert len(mail.outbox) == 2
    page = admin.get(invited.get_absolute_url()).content.decode()
    assert "The reminder was sent on" in page


def test_a_reminder_needs_invitations(admin, upcoming):
    admin.post(url("send_reminder", upcoming.pk))

    assert not MessageBatch.objects.exists()


def test_board_cannot_send_reminders(login, invited):
    board = login("board", "Board")

    assert board.post(url("send_reminder", invited.pk)).status_code == 403
    assert board.post(url("send_update", invited.pk)).status_code == 403


# When the meeting moves.


def edit(client, meeting, **changes):
    data = {
        "kind": meeting.kind,
        "title": meeting.title,
        "starts_at": timezone.localtime(meeting.starts_at).strftime("%Y-%m-%dT%H:%M"),
        "place": meeting.place,
        "notes": meeting.notes,
        "remind_days_before": meeting.remind_days_before or "",
        "votes_by_unit": "on",
        "members_can_read": "on",
    } | changes
    return client.post(url("meeting_edit", meeting.pk), data, follow=True)


def test_moving_the_meeting_offers_an_updated_invitation(
    admin, invited, django_capture_on_commit_callbacks
):
    invited.reminded_at = timezone.now()
    invited.save()
    later = timezone.localtime(invited.starts_at) + datetime.timedelta(days=2)

    page = edit(admin, invited, starts_at=later.strftime("%Y-%m-%dT%H:%M")).content.decode()

    assert "Send an updated invitation" in page
    invited.refresh_from_db()
    assert invited.needs_update()
    assert invited.reminded_at is None  # it goes again before the new date

    with django_capture_on_commit_callbacks(execute=True):
        admin.post(url("send_update", invited.pk))

    invited.refresh_from_db()
    assert invited.calendar_sequence == 1
    assert not invited.needs_update()
    assert len(mail.outbox) == 2
    message = mail.outbox[0]
    assert message.subject.startswith("Changed: Board meeting, December is now on")
    ics = next(a for a in message.attachments if a[0].endswith(".ics"))[1]
    ics = ics.decode() if isinstance(ics, bytes) else ics
    assert "SEQUENCE:1" in ics


def test_other_changes_need_no_update(admin, invited):
    edit(admin, invited, notes="Tea instead.")

    invited.refresh_from_db()
    assert not invited.needs_update()


def test_changes_before_the_invitations_need_no_update(admin, upcoming):
    edit(admin, upcoming, place="Somewhere else")

    upcoming.refresh_from_db()
    assert upcoming.details_changed_at is None


def test_an_invitation_marks_the_meeting_called(
    upcoming, make_household, django_capture_on_commit_callbacks
):
    upcoming.status = Meeting.Status.DRAFT
    upcoming.save()
    _unit, anna = make_household("Byvägen 4", first_name="Anna", email="anna@example.com")

    with django_capture_on_commit_callbacks(execute=True):
        api.send_message([(anna, None)], "Hi", "Hi", source=upcoming.source("reminder"))
    upcoming.refresh_from_db()
    assert upcoming.status == Meeting.Status.DRAFT

    with django_capture_on_commit_callbacks(execute=True):
        api.send_message([(anna, None)], "Hi", "Hi", source=upcoming.source(INVITATION))
    upcoming.refresh_from_db()
    assert upcoming.status == Meeting.Status.CALLED
