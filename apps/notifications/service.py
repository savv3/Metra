"""Sending notifications.

    from apps.notifications.service import notify

    notify("backup_failed", {"error": message}, link=reverse("backups:list"))

``notify`` is safe to call from anywhere: it never raises into the caller,
and it sends once the surrounding transaction is committed, so a change that
is rolled back notifies nobody. Recipients are worked out when it sends.
"""

import datetime
import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from . import kinds

logger = logging.getLogger(__name__)

# Notifications of the same kind and group are joined within this time.
GROUP_WINDOW = datetime.timedelta(hours=24)
# Read and dismissed notifications are deleted after this many days.
KEEP_DAYS = 90


def notify(kind, params=None, link="", users=(), roles=(), group=""):
    """Notify ``users`` and the active users in ``roles`` (or, when neither is
    given, the kind's default roles) about ``kind``, after the current
    transaction commits.

    Only users with the kind's permission who have not turned it off get it.
    With a ``group``, an unread notification of the same kind and group from
    the last 24 hours is updated instead (its "count" grows and it is unread
    again), so a busy day does not flood the bell.
    """
    try:
        user_ids = [getattr(user, "pk", user) for user in users if user is not None]
        args = (kind, dict(params or {}), link or "", user_ids, list(roles), group or "")
        transaction.on_commit(lambda: _send_safely(*args))
    except Exception:
        logger.exception("Could not send a %s notification", kind)


def _send_safely(*args):
    try:
        return send_now(*args)
    except Exception:
        # A notification is never worth breaking what triggered it (or a table
        # may not exist yet, for a snapshot taken before the migrations).
        logger.exception("Could not send a %s notification", args[0])
        return None


def recipients(kind, user_ids=(), roles=()):
    """The users who get a notification of ``kind`` (a Kind)."""
    from .models import Preference

    User = get_user_model()
    if not user_ids and not roles:
        roles = kind.roles
    wanted = User.objects.filter(is_active=True).filter(
        Q(pk__in=list(user_ids)) | Q(groups__name__in=list(roles))
    )
    choices = dict(
        Preference.objects.filter(kind=kind.name, user__in=wanted).values_list("user_id", "enabled")
    )
    return [
        user
        for user in wanted.distinct().order_by("pk")
        if choices.get(user.pk, kind.default_on) and kind.allowed(user)
    ]


def send_now(kind_name, params=None, link="", user_ids=(), roles=(), group=""):
    """Send a notification straight away. Returns it, or None when nobody gets it."""
    from .models import Notification, Recipient

    kind = kinds.get(kind_name)
    if kind is None:
        logger.warning("Unknown notification kind %r", kind_name)
        return None
    params = dict(params or {})
    users = recipients(kind, user_ids, roles)
    if not users:
        return None
    now = timezone.now()
    with transaction.atomic():
        notification = None
        if group:
            notification = (
                Notification.objects.filter(
                    kind=kind_name,
                    group=group,
                    created_at__gte=now - GROUP_WINDOW,
                    recipients__read_at__isnull=True,
                    recipients__dismissed_at__isnull=True,
                )
                .order_by("-created_at")
                .first()
            )
        if notification is None:
            notification = Notification.objects.create(
                kind=kind_name,
                params=params,
                link=link,
                group=group,
                created_at=now,
                updated_at=now,
            )
        else:
            merged = {**notification.params, **params}
            if "count" in params:
                merged["count"] = notification.params.get("count", 0) + params["count"]
            notification.params = merged
            notification.link = link or notification.link
            notification.updated_at = now
            notification.save(update_fields=["params", "link", "updated_at"])
            # New news: unread again, and back for whoever had dismissed it.
            notification.recipients.filter(user__in=users).update(read_at=None, dismissed_at=None)
        Recipient.objects.bulk_create(
            [Recipient(notification=notification, user=user) for user in users],
            ignore_conflicts=True,
        )
    return notification


def unread_count(user):
    from .models import Recipient

    return Recipient.objects.filter(
        user=user, read_at__isnull=True, dismissed_at__isnull=True
    ).count()


def delete_old(now=None):
    """Delete copies read or dismissed more than KEEP_DAYS ago, and notifications
    nobody has left. Returns how many copies were deleted."""
    from .models import Notification, Recipient

    now = now or timezone.now()
    cutoff = now - datetime.timedelta(days=KEEP_DAYS)
    old = Recipient.objects.filter(Q(read_at__lt=cutoff) | Q(dismissed_at__lt=cutoff))
    deleted, _by_model = old.delete()
    nobody_left = Notification.objects.filter(recipients__isnull=True)
    nobody_left.filter(updated_at__lt=now - GROUP_WINDOW).delete()
    return deleted
