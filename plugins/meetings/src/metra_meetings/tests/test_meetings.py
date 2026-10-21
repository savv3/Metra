from pathlib import Path

import pytest
from auditlog.models import LogEntry
from django.contrib.auth.models import Group
from django.urls import reverse

from metra_meetings.models import AgendaItem, Approval, Attendance, Meeting, MinutesLocked

from .conftest import weasyprint_or_skip


def url(name, *args):
    return reverse(f"metra_meetings:{name}", args=args)


def test_board_creates_a_meeting_with_an_agenda(login):
    board = login("board", "Board")
    checker = login("checker", "Read-only").user

    response = board.post(
        url("meeting_create"),
        {"kind": "annual", "title": "Annual meeting", "starts_at": "2026-04-20T18:30",
         "place": "Village hall", "votes_by_unit": "on", "members_can_read": "on",
         "secretary": board.user.pk, "checkers": [checker.pk]},
    )  # fmt: skip
    meeting = Meeting.objects.get()
    assert response.status_code == 302
    assert meeting.created_by == board.user
    assert list(meeting.checkers.all()) == [checker]

    board.post(url("item_create", meeting.pk), {"order": 1, "title": "Opening"})
    board.post(url("item_create", meeting.pk), {"order": 2, "title": "Election of a chair"})

    page = board.get(meeting.get_absolute_url()).content.decode()
    assert "§ 1. Opening" in page and "§ 2. Election of a chair" in page
    assert meeting.status == Meeting.Status.DRAFT


def test_the_menu_links_to_meetings(admin, login):
    assert 'href="/plugins/meetings/"' in admin.get(reverse("register:unit_list")).content.decode()
    nobody = login("nobody")
    assert "/plugins/meetings/" not in nobody.get("/").content.decode()


def test_one_vote_per_unit(admin, meeting, make_household):
    unit, anna = make_household("Byvägen 4", first_name="Anna", last_name="Lind")
    bo = admin_person(unit, "Bo")
    _other, cecilia = make_household("Strandvägen 1", first_name="Cecilia")
    add = url("attendance_add", meeting.pk)

    admin.post(add, {"person": anna.pk})
    admin.post(add, {"person": bo.pk, "unit": unit.pk})
    admin.post(add, {"person": cecilia.pk})

    votes = {a.name: (a.unit_name, a.votes) for a in meeting.attendances.all()}
    assert votes == {
        "Anna Lind": ("Byvägen 4", 1),
        "Bo": ("Byvägen 4", 0),
        "Cecilia": ("Strandvägen 1", 1),
    }
    assert meeting.total_votes() == 2
    page = admin.get(url("attendance", meeting.pk)).content.decode()
    assert "2 votes in total" in page and "3 people present" in page

    # A unit's vote is carried once.
    bo_present = meeting.attendances.get(name="Bo")
    response = admin.post(
        url("attendance_edit", meeting.pk, bo_present.pk),
        {"person": bo.pk, "unit": unit.pk, "votes": 1},
    )
    assert "Anna Lind already carries the vote of Byvägen 4." in response.content.decode()
    assert meeting.total_votes() == 2


def admin_person(unit, first_name):
    from apps.plugins import api

    person = api.Person.objects.create(first_name=first_name)
    api.UnitContact.objects.create(unit=unit, person=person, role="contact")
    return person


def test_one_vote_per_person(admin, meeting, make_household):
    meeting.votes_by_unit = False
    meeting.save()
    unit, anna = make_household("Byvägen 4", first_name="Anna")
    bo = admin_person(unit, "Bo")

    admin.post(url("attendance_add", meeting.pk), {"person": anna.pk})
    admin.post(url("attendance_add", meeting.pk), {"person": bo.pk, "unit": unit.pk})
    response = admin.post(url("attendance_add", meeting.pk), {"person": bo.pk})

    assert response.status_code == 400
    assert "already on the list" in response.content.decode()
    assert [a.votes for a in meeting.attendances.all()] == [1, 1]
    assert meeting.total_votes() == 2


@pytest.mark.parametrize("role", ["Treasurer", "Read-only"])
def test_treasurer_and_read_only_only_look(login, meeting, make_household, role):
    _unit, anna = make_household("Byvägen 4", first_name="Anna")
    client = login("viewer", role)
    item = meeting.items.first()
    present = Attendance.objects.create(meeting=meeting, person=anna)

    pages = [url("meeting_list"), meeting.get_absolute_url(), url("attendance", meeting.pk)]
    assert [client.get(page).status_code for page in pages] == [200] * 3
    changes = [
        ("get", url("meeting_create")),
        ("get", url("meeting_edit", meeting.pk)),
        ("get", url("item_create", meeting.pk)),
        ("get", url("item_edit", meeting.pk, item.pk)),
        ("get", url("minutes_edit", meeting.pk)),
        ("post", url("attendance_add", meeting.pk)),
        ("post", url("attendance_remove", meeting.pk, present.pk)),
        ("post", url("meeting_status", meeting.pk)),
        ("post", url("send_notice", meeting.pk)),
        ("get", url("meeting_delete", meeting.pk)),
    ]
    assert [getattr(client, method)(path).status_code for method, path in changes] == [403] * 10
    assert "New meeting" not in client.get(url("meeting_list")).content.decode()


def test_board_cannot_delete_meetings_or_send_the_notice(login, meeting):
    board = login("board", "Board")

    assert board.get(url("meeting_delete", meeting.pk)).status_code == 403
    # Messages to everyone are for admins unless they give the board the right.
    assert board.post(url("send_notice", meeting.pk)).status_code == 403
    assert "Send the notice" not in board.get(meeting.get_absolute_url()).content.decode()


def test_board_keeps_the_attendance_and_agenda(login, meeting, make_household):
    board = login("board", "Board")
    _unit, anna = make_household("Byvägen 4", first_name="Anna")
    board.post(url("attendance_add", meeting.pk), {"person": anna.pk})
    present = meeting.attendances.get()
    item = meeting.items.first()

    board.post(url("attendance_remove", meeting.pk, present.pk))
    board.post(url("item_delete", meeting.pk, item.pk))

    assert not meeting.attendances.exists()
    assert list(meeting.items.values_list("title", flat=True)) == ["Accounts for 2025"]
    page = board.get(meeting.get_absolute_url(), HTTP_ACCEPT_LANGUAGE="sv")
    assert page.status_code == 200


def test_anonymous_is_sent_to_login(client, meeting):
    response = client.get(meeting.get_absolute_url())

    assert response.status_code == 302 and "login" in response["Location"]


def test_secretary_writes_the_minutes(admin, meeting):
    first, second = meeting.items.all()

    admin.post(
        url("minutes_edit", meeting.pk),
        {"form-TOTAL_FORMS": 2, "form-INITIAL_FORMS": 2,
         "form-0-id": first.pk, "form-0-minutes": "The chair opened the meeting at 18.30.",
         "form-0-decision": "",
         "form-1-id": second.pk, "form-1-minutes": "Presented.",
         "form-1-decision": "The accounts were approved."},
    )  # fmt: skip

    second.refresh_from_db()
    assert second.decision == "The accounts were approved."
    page = admin.get(meeting.get_absolute_url()).content.decode()
    assert "The chair opened the meeting at 18.30." in page


@pytest.fixture
def held(meeting, make_user):
    """A held meeting with two minute checkers (who have only the Read-only role)."""
    first, second = make_user("first", "Read-only"), make_user("second", "Read-only")
    meeting.checkers.set([first, second])
    meeting.status = Meeting.Status.HELD
    meeting.save()
    return meeting


def checker_client(login_user, client, settings):
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
    client.force_login(login_user)
    return client


def test_only_listed_checkers_approve(held, admin, client, settings):
    first = held.checkers.get(username="first")

    assert admin.get(url("approve", held.pk)).status_code == 403
    assert admin.post(url("approve", held.pk)).status_code == 403
    checker = checker_client(first, client, settings)
    assert "Check and approve the minutes" in checker.get(held.get_absolute_url()).content.decode()
    assert checker.get(url("approve", held.pk)).status_code == 200
    checker.post(url("approve", held.pk))

    held.refresh_from_db()
    assert held.status == Meeting.Status.HELD  # the second checker has not approved yet
    assert list(Approval.objects.values_list("checker__username", flat=True)) == ["first"]
    # Approving twice is not possible.
    assert checker.post(url("approve", held.pk)).status_code == 403


def test_minutes_cannot_be_approved_before_the_meeting_is_held(
    meeting, make_user, client, settings
):
    first = make_user("first", "Read-only")
    meeting.checkers.set([first])

    assert (
        checker_client(first, client, settings).get(url("approve", meeting.pk)).status_code == 403
    )


def test_minutes_lock_when_every_checker_approved(held, admin, make_household):
    first, second = held.checkers.order_by("username")
    _unit, anna = make_household("Byvägen 4", first_name="Anna")
    item = held.items.first()

    assert held.approve(first) is False
    assert held.approve(second) is True

    held.refresh_from_db()
    assert held.status == Meeting.Status.APPROVED and held.approved_at
    # Edits are refused on the pages...
    response = admin.post(url("item_edit", held.pk, item.pk), {"order": 1, "title": "Changed"})
    assert response.status_code == 302
    admin.post(url("attendance_add", held.pk), {"person": anna.pk})
    admin.post(url("meeting_status", held.pk), {"status": "called"})
    admin.post(url("meeting_delete", held.pk))
    item.refresh_from_db()
    held.refresh_from_db()
    assert item.title == "Opening of the meeting"
    assert not held.attendances.exists()
    assert held.status == Meeting.Status.APPROVED
    page = admin.get(held.get_absolute_url()).content.decode()
    assert "can no longer be changed" in page
    assert url("meeting_edit", held.pk) not in page
    # ...and in the models.
    item.title = "Changed"
    with pytest.raises(MinutesLocked):
        item.save()
    with pytest.raises(MinutesLocked):
        held.save()
    with pytest.raises(MinutesLocked):
        held.delete()
    with pytest.raises(MinutesLocked):
        AgendaItem.objects.create(meeting=held, title="Late addition")
    with pytest.raises(MinutesLocked):
        Attendance.objects.create(meeting=held, person=anna)


def test_changing_the_minutes_clears_approvals(held, admin):
    first = held.checkers.get(username="first")
    held.approve(first)
    item = held.items.first()

    admin.post(
        url("item_edit", held.pk, item.pk),
        {"order": 1, "title": item.title, "minutes": "Corrected"},
    )

    assert not held.approvals.exists()
    assert held.can_be_approved_by(first)


def test_minutes_and_agenda_pdfs(admin, held, make_household):
    weasyprint_or_skip()
    _unit, anna = make_household("Byvägen 4", first_name="Anna")
    Attendance.objects.create(meeting=held, person=anna, votes=1)
    for checker in held.checkers.all():
        held.approve(checker)

    agenda = admin.get(url("agenda_pdf", held.pk))
    minutes = admin.get(url("minutes_pdf", held.pk))

    assert agenda.content.startswith(b"%PDF") and minutes.content.startswith(b"%PDF")
    assert agenda["Content-Type"] == "application/pdf"
    assert "minutes-2026-04-20-annual-meeting-2026.pdf" in minutes["Content-Disposition"]


def test_minutes_html_shows_attendance_votes_and_approvals(held, make_household):
    from django.template.loader import render_to_string

    from metra_meetings import documents

    _unit, anna = make_household("Byvägen 4", first_name="Anna")
    Attendance.objects.create(meeting=held, person=anna, unit=_unit, votes=1)
    for checker in held.checkers.all():
        held.approve(checker)

    html = render_to_string("metra_meetings/pdf/minutes.html", documents.minutes_context(held))

    assert "Anna" in html and "Byvägen 4" in html
    assert "1 person present" in html
    assert "approved in Metra on" in html
    assert "NOT APPROVED" not in html


def test_roles_get_the_permissions(db):
    def codenames(role):
        return set(
            Group.objects.get(name=role)
            .permissions.filter(content_type__app_label="metra_meetings")
            .values_list("codename", flat=True)
        )

    view = {
        "view_meeting",
        "view_agendaitem",
        "view_attendance",
        "view_approval",
        "view_agendatemplate",
    }
    assert {"add_meeting", "delete_meeting", "change_attendance"} <= codenames("Admin")
    board = codenames("Board")
    assert {"add_meeting", "change_meeting", "change_agendaitem", "add_attendance"} <= board
    assert "delete_meeting" not in board
    assert {"add_agendatemplate", "change_agendatemplate"} <= board
    assert "delete_agendatemplate" not in board
    assert codenames("Treasurer") == codenames("Read-only") == view


def test_changes_are_in_the_audit_log(admin, meeting, make_household):
    _unit, anna = make_household("Byvägen 4", first_name="Anna")

    admin.post(url("attendance_add", meeting.pk), {"person": anna.pk})

    present = Attendance.objects.get()
    entry = LogEntry.objects.get_for_object(present).get()
    assert entry.actor.username == "admin"
    assert entry.additional_data["person_id"] == anna.pk
    assert LogEntry.objects.get_for_object(meeting).exists()


def test_help_is_written_in_every_language():
    folder = Path(__file__).resolve().parent.parent / "help"

    for language in ("sv", "en", "fi"):
        text = (folder / language / "meetings.md").read_text()
        assert text.startswith("# ")


def test_the_meetings_guide_is_in_help(board_client):
    from django.urls import reverse

    page = board_client.get(reverse("help:index"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert reverse("help:article", args=["meetings"]) in page
    meetings = board_client.get(reverse("metra_meetings:meeting_list")).content.decode()
    assert f'href="{reverse("help:article", args=["meetings"])}" class="help-link"' in meetings
