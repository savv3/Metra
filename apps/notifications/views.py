"""The Notifications page, its actions and the notification settings.

These pages show and change only the signed-in user's own notifications
(every query is filtered by ``request.user``, and someone else's is a 404), so
a login is the only check: there is no model permission to hold, unlike the
register's pages (see AGENTS.md).
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import kinds
from .models import Preference, Recipient

PER_PAGE = 50


def own(request):
    """The user's notifications that are not dismissed, newest first."""
    return (
        Recipient.objects.filter(user=request.user, dismissed_at__isnull=True)
        .select_related("notification")
        .order_by("-notification__updated_at", "-notification__pk")
    )


def is_safe_link(request, link):
    """Only paths on this site, like "/backups/", are opened."""
    return (
        bool(link)
        and link.startswith("/")
        and not link.startswith("//")
        and url_has_allowed_host_and_scheme(
            link, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        )
    )


def back(request):
    """Back to the list the action was made from."""
    target = request.POST.get("next", "")
    if is_safe_link(request, target):
        return redirect(target)
    return redirect("notifications:list")


@login_required
def notification_list(request):
    unread_only = request.GET.get("show") == "unread"
    copies = own(request)
    if unread_only:
        copies = copies.filter(read_at__isnull=True)
    page = Paginator(copies, PER_PAGE).get_page(request.GET.get("page"))
    for copy in page:
        copy.openable = is_safe_link(request, copy.notification.link)
    return render(
        request,
        "notifications/list.html",
        {
            "page": page,
            "unread_only": unread_only,
            "has_unread": own(request).filter(read_at__isnull=True).exists(),
            "here": request.get_full_path(),
        },
    )


def _own_copy(request, pk):
    return get_object_or_404(
        Recipient.objects.select_related("notification"), notification_id=pk, user=request.user
    )


@login_required
@require_POST
def open_notification(request, pk):
    copy = _own_copy(request, pk)
    if copy.read_at is None:
        copy.read_at = timezone.now()
        copy.save(update_fields=["read_at"])
    if is_safe_link(request, copy.notification.link):
        return redirect(copy.notification.link)
    return back(request)


@login_required
@require_POST
def mark_read(request, pk):
    copy = _own_copy(request, pk)
    copy.read_at = copy.read_at or timezone.now()
    copy.save(update_fields=["read_at"])
    return back(request)


@login_required
@require_POST
def mark_unread(request, pk):
    copy = _own_copy(request, pk)
    copy.read_at = None
    copy.save(update_fields=["read_at"])
    return back(request)


@login_required
@require_POST
def dismiss(request, pk):
    copy = _own_copy(request, pk)
    now = timezone.now()
    copy.dismissed_at = now
    copy.read_at = copy.read_at or now
    copy.save(update_fields=["dismissed_at", "read_at"])
    messages.success(request, _("The notification was dismissed."))
    return back(request)


@login_required
@require_POST
def mark_all_read(request):
    own(request).filter(read_at__isnull=True).update(read_at=timezone.now())
    messages.success(request, _("All notifications are marked as read."))
    return back(request)


@login_required
def notification_settings(request):
    """A checkbox per kind the user could get (those whose permission they have)."""
    available = [kind for kind in kinds.all_kinds().values() if kind.allowed(request.user)]
    chosen = dict(Preference.objects.filter(user=request.user).values_list("kind", "enabled"))
    if request.method == "POST":
        wanted = set(request.POST.getlist("kinds"))
        for kind in available:
            Preference.objects.update_or_create(
                user=request.user, kind=kind.name, defaults={"enabled": kind.name in wanted}
            )
        messages.success(request, _("Your notification settings are saved."))
        return redirect(reverse("notifications:settings"))
    rows = [(kind, chosen.get(kind.name, kind.default_on)) for kind in available]
    return render(request, "notifications/settings.html", {"rows": rows})
