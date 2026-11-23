"""Invitations, reminders and updates, sent with Metra's messaging.

The invitation (the notice of meeting) opens in the New message form, so
staff choose who gets it and check it before sending. Reminders and updates
go to the same people without that step: everyone who got an invitation, on
the channels the last invitation used. Nothing about who was invited is
stored here; the send-outs under Messages are the record, so the per-person
export and erasure cover it.
"""

import logging

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.plugins import api

from . import documents, ical
from .models import INVITATION, REMINDER, UPDATE, Meeting

logger = logging.getLogger(__name__)


class PDFMissing(Exception):
    """The agenda PDF could not be made (WeasyPrint is missing)."""


def files(meeting, pdf=True):
    """The agenda PDF (if ``pdf``) and the calendar file, to attach."""
    attached = []
    if pdf:
        try:
            pdf_bytes = documents.agenda_pdf(meeting)
        except api.PDFUnavailable as error:
            raise PDFMissing() from error
        attached.append((documents.agenda_filename(meeting), pdf_bytes, "application/pdf"))
    attached.append((ical.filename(meeting), ical.ics(meeting), ical.CONTENT_TYPE))
    return attached


def _files_if_possible(meeting):
    """(files, whether the PDF is among them): without the PDF when it cannot be made."""
    try:
        return files(meeting), True
    except PDFMissing:
        return files(meeting, pdf=False), False


def invitation_url(request, meeting):
    """The New message form with the invitation written, the agenda and the
    calendar file attached, and email chosen. Raises PDFMissing, or
    ValidationError for a file that cannot be attached."""
    subject, short, email = documents.notice_texts(meeting)
    return api.message_draft(
        request,
        subject,
        short,
        files=files(meeting),
        email_body=email,
        channels="email",
        source=meeting.source(INVITATION),
    )


def _channels(meeting):
    last = meeting.invitations().first()
    return (last.channels if last and last.channels else "") or "email"


def _send(meeting, kind, texts, user):
    recipients = meeting.invitees()
    if not recipients:
        return None
    attached, with_pdf = _files_if_possible(meeting)
    subject, short, email = texts(meeting, attached_pdf=with_pdf)
    return api.send_message(
        recipients,
        subject,
        email,
        body=short,
        channels=_channels(meeting),
        files=attached,
        source=meeting.source(kind),
        audience=_("Everyone invited to %(title)s") % {"title": meeting.title},
        created_by=user,
    )


def send_reminder(meeting, user=None):
    """Remind everyone invited. Returns the send-out, or None when nobody was invited."""
    with transaction.atomic():
        batch = _send(meeting, REMINDER, documents.reminder_texts, user)
        if batch is not None:
            meeting.reminded_at = timezone.now()
            meeting.save(update_fields=["reminded_at"])
    return batch


def send_update(meeting, user=None):
    """Tell everyone invited the new date, time or place, with a calendar
    file that replaces the one they have. Returns the send-out, or None."""
    with transaction.atomic():
        meeting.calendar_sequence += 1
        meeting.save(update_fields=["calendar_sequence"])
        batch = _send(meeting, UPDATE, documents.update_texts, user)
        if batch is None:
            transaction.set_rollback(True)
    return batch


def details_changed(meeting, old_starts_at):
    """After the date, time or place was edited: remember it if invitations
    went out, so the meeting page offers an update. A meeting that moved gets
    its reminder again before the new date."""
    if not meeting.invitations().exists():
        return False
    meeting.details_changed_at = timezone.now()
    fields = ["details_changed_at"]
    if meeting.starts_at != old_starts_at and meeting.reminded_at is not None:
        meeting.reminded_at = None
        fields.append("reminded_at")
    meeting.save(update_fields=fields)
    return True


def due_reminders(today=None):
    """Meetings whose reminder is due today: called, in the future, with a
    reminder day that has come, invited before that day, and not reminded yet."""
    today = today or timezone.localdate()
    due = []
    meetings = Meeting.objects.filter(
        status=Meeting.Status.CALLED,
        starts_at__gt=timezone.now(),
        remind_days_before__isnull=False,
        reminded_at__isnull=True,
    )
    for meeting in meetings:
        first = meeting.invitations().order_by("created_at", "pk").first()
        day = meeting.reminder_date()
        if first is None or day is None or today < day:
            continue
        if timezone.localtime(first.created_at).date() >= day:
            continue  # invited on or after the reminder day: the invitation is fresh
        due.append(meeting)
    return due


def send_due_reminders():
    sent = 0
    for meeting in due_reminders():
        try:
            if send_reminder(meeting) is not None:
                sent += 1
        except Exception:
            logger.exception("The reminder for meeting %s could not be sent", meeting.pk)
    return sent


def mark_called(sender, batch, **kwargs):
    """An invitation went out: the meeting is called."""
    prefix, _sep, rest = (batch.source or "").partition(":meeting:")
    pk, _sep, kind = rest.partition(":")
    if prefix != "metra_meetings" or kind != INVITATION or not pk.isdigit():
        return
    meeting = Meeting.objects.filter(pk=int(pk), status=Meeting.Status.DRAFT).first()
    if meeting is not None:
        meeting.status = Meeting.Status.CALLED
        meeting.save(update_fields=["status"])
