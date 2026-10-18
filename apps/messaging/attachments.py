"""Files attached to messages and newsletters.

Files are uploaded while a message is written and kept without a send-out
until it is confirmed; unsent ones are removed after a day. Email recipients
get the files attached. SMS recipients get one link per send-out to a page
with the files; the link expires like a self-service link, and only its hash
is stored.
"""

import datetime
import hashlib
import inspect
import secrets
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import Attachment
from .registry import ProviderError

# What may be attached: documents people open on a phone or computer, nothing
# that runs. Checked by extension; the type sent is the one listed here.
TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".rtf": "application/rtf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".odp": "application/vnd.oasis.opendocument.presentation",
}
ACCEPT = ",".join(TYPES)
UNSENT_KEPT = datetime.timedelta(days=1)
# 16 random bytes (128 bits) keep the SMS link short.
TOKEN_BYTES = 16
# Stands in for the real link in the stored copy of an SMS.
STORED_LINK = "[file link]"


def max_file_bytes():
    return settings.MESSAGING["attachment_file_mb"] * 1024 * 1024


def max_total_bytes():
    return settings.MESSAGING["attachment_total_mb"] * 1024 * 1024


def validate(uploads, kept=()):
    """Check new uploads, together with files already attached, against the
    allowed types and the size limits."""
    errors = []
    for upload in uploads:
        if Path(upload.name).suffix.lower() not in TYPES:
            errors.append(
                _("%(name)s: this kind of file cannot be attached.") % {"name": upload.name}
            )
        elif upload.size > max_file_bytes():
            errors.append(
                _("%(name)s is larger than %(limit)s.")
                % {"name": upload.name, "limit": filesizeformat(max_file_bytes())}
            )
    total = sum(upload.size for upload in uploads) + sum(a.size for a in kept)
    if total > max_total_bytes():
        errors.append(
            _("The files are %(size)s together; at most %(limit)s can be sent.")
            % {"size": filesizeformat(total), "limit": filesizeformat(max_total_bytes())}
        )
    if errors:
        raise ValidationError(errors)


def save(uploads, user):
    """Store new uploads as unsent attachments of ``user``."""
    saved = []
    for upload in uploads:
        name = Path(upload.name).name[:200]
        attachment = Attachment(
            name=name,
            size=upload.size,
            content_type=TYPES[Path(name).suffix.lower()],
            uploaded_by=user,
        )
        attachment.file.save(name, upload, save=False)
        attachment.save()
        saved.append(attachment)
    return saved


def unsent(user):
    """Attachments ``user`` has uploaded for a message not sent yet."""
    return Attachment.objects.filter(batch=None, uploaded_by=user)


def remove_unsent():
    """Delete files uploaded for messages that were never sent."""
    for attachment in Attachment.objects.filter(
        batch=None, uploaded_at__lt=timezone.now() - UNSENT_KEPT
    ):
        attachment.delete()


def for_email(batch):
    """(filename, content, type) for each of the batch's files, read once."""
    if not hasattr(batch, "_email_attachments"):
        batch._email_attachments = []
        for attachment in batch.attachments.all():
            with attachment.file.open("rb") as file:
                batch._email_attachments.append(
                    (attachment.name, file.read(), attachment.content_type)
                )
    return batch._email_attachments


def email_kwargs(provider, batch):
    """The ``attachments`` argument for an email provider, if there are files."""
    files = for_email(batch)
    if not files:
        return {}
    # Providers written before attachments existed (e.g. in a plugin) cannot send them.
    if "attachments" not in inspect.signature(provider.send).parameters:
        raise ProviderError(_("This email provider cannot send attachments."))
    return {"attachments": files}


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def link_url(token):
    return settings.BASE_URL + reverse("messaging:files", args=[token])


def sms_line(batch):
    """(line to send, line to store) with the link to the batch's files, or
    ("", "") when it has none. The link is made on first use."""
    if not batch.attachments.exists():
        return "", ""
    if not getattr(batch, "_files_token", None):
        batch._files_token = secrets.token_urlsafe(TOKEN_BYTES)
        batch.files_token_hash = hash_token(batch._files_token)
        batch.files_expire_at = timezone.now() + datetime.timedelta(
            days=settings.SELF_SERVICE_LINK_DAYS
        )
        batch.save(update_fields=["files_token_hash", "files_expire_at"])
    label = _("Files:")
    return f"\n{label} {link_url(batch._files_token)}", f"\n{label} {STORED_LINK}"


def sms_line_estimate():
    """A line as long as the real one, for counting SMS before sending."""
    return f"\n{_('Files:')} {link_url('x' * len(secrets.token_urlsafe(TOKEN_BYTES)))}"


def batch_for_token(token):
    """The send-out a file link opens, or None if it is unknown or expired."""
    from .models import MessageBatch

    return MessageBatch.objects.filter(
        files_token_hash=hash_token(token), files_expire_at__gt=timezone.now()
    ).first()
