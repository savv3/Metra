"""Messages prepared elsewhere (for example by a plugin) and opened in the
New message form, so staff check the recipients and the text before sending.

A draft lives in the user's session for a few hours: its texts and the ids of
files already stored as the user's unsent attachments. The New message form
reads it from ``?draft=<id>``.
"""

import secrets
import time

from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils.http import urlencode

from . import attachments

SESSION_PREFIX = "messaging:draft:"
KEPT_SECONDS = 6 * 60 * 60


def create(request, subject, body, files=(), email_body=""):
    """Store a draft for ``request.user`` and return the New message form's URL.

    ``files`` are (filename, bytes, mimetype); they become the user's unsent
    attachments, ticked in the form. Raises ValidationError for a file type or
    size that could not be sent.
    """
    uploads = [ContentFile(content, name=name) for name, content, _mimetype in files]
    attachments.validate(uploads)
    saved = attachments.save(uploads, request.user)
    _forget_old(request.session)
    draft_id = secrets.token_urlsafe(8)
    request.session[SESSION_PREFIX + draft_id] = {
        "subject": subject,
        "body": body,
        "email_body": email_body,
        "attachments": [a.pk for a in saved],
        "created": time.time(),
    }
    return f"{reverse('messaging:compose')}?{urlencode({'draft': draft_id})}"


def get(request, draft_id):
    """The draft's data, or None when it is unknown or too old."""
    draft = request.session.get(SESSION_PREFIX + (draft_id or ""))
    if not draft or time.time() - draft.get("created", 0) > KEPT_SECONDS:
        return None
    return draft


def _forget_old(session):
    now = time.time()
    for key in [k for k in session.keys() if k.startswith(SESSION_PREFIX)]:
        if now - session[key].get("created", 0) > KEPT_SECONDS:
            del session[key]
