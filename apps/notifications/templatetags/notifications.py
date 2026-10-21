from django import template
from django.db import DatabaseError

from ..service import unread_count

register = template.Library()


@register.inclusion_tag("notifications/_bell.html", takes_context=True)
def notification_bell(context):
    """The bell in the header with the number of unread notifications. One
    indexed count per page, for signed-in users only."""
    request = context.get("request")
    user = getattr(request, "user", None)
    try:
        count = unread_count(user) if user is not None and user.is_authenticated else 0
    except DatabaseError:  # e.g. a page shown before the migrations ran
        count = 0
    match = getattr(request, "resolver_match", None)
    return {
        "count": count,
        "shown": "99+" if count > 99 else str(count),
        "current": bool(match and match.namespace == "notifications"),
    }
