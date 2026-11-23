"""The meeting as a calendar file (iCalendar, RFC 5545), attached to the
invitation and the reminders so that people can add it to their calendar.

Every file of a meeting has the same UID, so a calendar that already holds the
meeting updates it when an updated invitation (with a higher SEQUENCE) is
opened, instead of adding a second one.
"""

import datetime
from urllib.parse import urlsplit

from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext as _

# Meetings have a start but no end; calendars get this length.
LENGTH = datetime.timedelta(hours=2)
CONTENT_TYPE = "text/calendar"


def filename(meeting):
    """For example "annual-meeting-2026-2026-04-20.ics"."""
    day = timezone.localtime(meeting.starts_at).date().isoformat()
    return f"{slugify(meeting.title) or meeting.pk}-{day}.ics"


def uid(meeting):
    host = urlsplit(settings.BASE_URL).hostname or "metra"
    return f"meeting-{meeting.pk}@{host}"


def _escape(text):
    """A TEXT value: backslashes, commas, semicolons and line breaks escaped."""
    text = str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")


def _fold(line):
    """Lines longer than 75 octets go on in lines that start with a space,
    without splitting a UTF-8 character."""
    out, current = [], b""
    for char in line:
        encoded = char.encode()
        if len(current) + len(encoded) > (75 if not out else 74):
            out.append(current)
            current = b""
        current += encoded
    out.append(current)
    return b"\r\n ".join(out)


def _utc(value):
    return value.astimezone(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")


def description(meeting):
    lines = []
    if meeting.notes:
        lines += [meeting.notes, ""]
    items = meeting.items.all()
    if items:
        lines.append(_("Agenda:"))
        lines += [f"§ {number}. {item.title}" for number, item in enumerate(items, 1)]
    return "\n".join(lines).strip()


def ics(meeting):
    """The calendar file's bytes."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Metra//Meetings//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid(meeting)}",
        f"SEQUENCE:{meeting.calendar_sequence}",
        f"DTSTAMP:{_utc(timezone.now())}",
        f"DTSTART:{_utc(meeting.starts_at)}",
        f"DTEND:{_utc(meeting.starts_at + LENGTH)}",
        f"SUMMARY:{_escape(meeting.title)}",
    ]
    if meeting.place:
        lines.append(f"LOCATION:{_escape(meeting.place)}")
    if text := description(meeting):
        lines.append(f"DESCRIPTION:{_escape(text)}")
    lines += ["STATUS:CONFIRMED", "TRANSP:OPAQUE", "END:VEVENT", "END:VCALENDAR"]
    return b"\r\n".join(_fold(line) for line in lines) + b"\r\n"
