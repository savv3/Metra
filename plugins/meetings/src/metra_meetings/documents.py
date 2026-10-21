"""The agenda and minutes as PDFs, and the text of the notice of meeting."""

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


def notice_texts(meeting):
    """(subject, short text, email text) for the notice of meeting. The email
    text greets each recipient with the {first_name} placeholder."""
    day, time = _when(meeting)
    values = {
        "kind": meeting.get_kind_display(),
        "title": meeting.title,
        "date": day,
        "time": time,
        "place": meeting.place or "–",
    }
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
    lines += ["", _("The agenda is attached as a PDF."), "", _("Welcome!"), "{organisation}"]
    return subject, short, "\n".join(lines)
