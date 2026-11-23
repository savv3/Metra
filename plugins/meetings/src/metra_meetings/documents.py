"""The agenda and minutes as PDFs, and the texts of the notice of meeting
(the invitation), the reminder and the update when the meeting moves."""

from django.template.defaultfilters import date as date_filter
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext as _

from apps.plugins import api


def _organisation():
    return api.Organisation.current()


def _items(meeting):
    """(paragraph number, item) for each agenda item."""
    return list(enumerate(meeting.items.all(), start=1))


def minutes_context(meeting):
    attendances = list(meeting.attendances.all())
    approvals = meeting.approvals_by_checker()
    return {
        "meeting": meeting,
        "organisation": _organisation(),
        "items": _items(meeting),
        "attendances": attendances,
        "total_votes": sum(a.votes for a in attendances),
        "checkers": [(c, approvals.get(c.pk)) for c in meeting.checkers.order_by("username")],
    }


def agenda_pdf(meeting):
    html = render_to_string(
        "metra_meetings/pdf/agenda.html",
        {"meeting": meeting, "organisation": _organisation(), "items": _items(meeting)},
    )
    return api.render_pdf(html)


def minutes_pdf(meeting):
    return api.render_pdf(
        render_to_string("metra_meetings/pdf/minutes.html", minutes_context(meeting))
    )


def filename(meeting, kind):
    """For example "agenda-2026-04-20-annual-meeting.pdf"."""
    day = timezone.localtime(meeting.starts_at).date().isoformat()
    return f"{kind}-{day}-{slugify(meeting.title) or meeting.pk}.pdf"


def agenda_filename(meeting):
    return filename(meeting, slugify(_("agenda")) or "agenda")


def minutes_filename(meeting):
    return filename(meeting, slugify(_("minutes")) or "minutes")


def _when(meeting):
    local = timezone.localtime(meeting.starts_at)
    return date_filter(local, "DATE_FORMAT"), date_filter(local, "TIME_FORMAT")


def _values(meeting):
    day, time = _when(meeting)
    return {
        "kind": meeting.get_kind_display(),
        "title": meeting.title,
        "date": day,
        "time": time,
        "place": meeting.place or "–",
    }


def _details(meeting, values):
    lines = [
        _("Date: %(date)s") % values,
        _("Time: %(time)s") % values,
        _("Place: %(place)s") % values,
    ]
    if meeting.notes:
        lines += ["", meeting.notes]
    items = meeting.items.all()
    if items:
        lines += ["", _("Agenda:")]
        lines += [f"§ {number}. {item.title}" for number, item in enumerate(items, 1)]
    return lines


def _closing(attached_pdf=True):
    lines = [""]
    if attached_pdf:
        lines.append(_("The agenda is attached as a PDF."))
    lines.append(_("Open the attached calendar file to add the meeting to your calendar."))
    return lines


def notice_texts(meeting):
    """(subject, short text, email text) for the notice of meeting, the
    invitation. The email text greets each recipient with the {first_name}
    placeholder."""
    values = _values(meeting)
    subject = _("Notice: %(title)s on %(date)s") % values
    short = (
        _(
            "Welcome to %(title)s on %(date)s at %(time)s, %(place)s. "
            "The agenda is in the attached file."
        )
        % values
    )
    lines = [
        _("Dear {first_name},"),
        "",
        _("You are welcome to %(title)s (%(kind)s).") % values,
        "",
        *_details(meeting, values),
        *_closing(),
        "",
        _("Welcome!"),
        "{organisation}",
    ]
    return subject, short, "\n".join(lines)


def reminder_texts(meeting, attached_pdf=True):
    """(subject, short text, email text) for the reminder before the meeting."""
    values = _values(meeting)
    subject = _("Reminder: %(title)s on %(date)s") % values
    short = _("Reminder: %(title)s on %(date)s at %(time)s, %(place)s. Welcome!") % values
    lines = [
        _("Dear {first_name},"),
        "",
        _("A reminder that %(title)s (%(kind)s) is coming up.") % values,
        "",
        *_details(meeting, values),
        *_closing(attached_pdf),
        "",
        _("Welcome!"),
        "{organisation}",
    ]
    return subject, short, "\n".join(lines)


def update_texts(meeting, attached_pdf=True):
    """(subject, short text, email text) when the date, time or place changed
    after the invitation."""
    values = _values(meeting)
    subject = _("Changed: %(title)s is now on %(date)s") % values
    short = _("Changed: %(title)s is now on %(date)s at %(time)s, %(place)s. Welcome!") % values
    lines = [
        _("Dear {first_name},"),
        "",
        _("The date, time or place of %(title)s (%(kind)s) has changed. It is now:") % values,
        "",
        *_details(meeting, values),
        *_closing(attached_pdf),
        _("If the meeting is already in your calendar, the file updates it."),
        "",
        _("Welcome!"),
        "{organisation}",
    ]
    return subject, short, "\n".join(lines)
