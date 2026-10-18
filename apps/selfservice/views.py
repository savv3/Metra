import segno
from auditlog.models import LogEntry
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.readings.models import ReadingRound
from apps.register.history import describe
from apps.register.models import Organisation, Unit

from .models import SelfServiceLink, primary_contact
from .service import issue_links

CHANGES_SHOWN = 100

SCOPES = {
    "all": gettext_lazy("All units"),
    "missing": gettext_lazy("Units missing a reading"),
    "unreachable": gettext_lazy("Units whose contact has no phone or email"),
}


def _qr_svg(url):
    return mark_safe(segno.make(url, error="m").svg_inline(scale=4, border=2))


def _round_units(round_, scope):
    units = round_.expected_units().prefetch_related("unit_contacts__person").order_by("name")
    if scope == "missing":
        units = units.exclude(readings__round=round_)
    return list(units)


@login_required
@permission_required("selfservice.view_selfservicelink", raise_exception=True)
def round_links(request, pk):
    round_ = get_object_or_404(ReadingRound.objects.select_related("reading_type"), pk=pk)
    links = round_.self_service_links.select_related("unit", "person", "created_by")
    return render(
        request,
        "selfservice/round_links.html",
        {"round": round_, "links": links, "scopes": SCOPES},
    )


def _print(request, issued, skipped, round_, layout):
    response = render(
        request,
        "selfservice/print.html",
        {
            "letters": [
                {"issued": item, "url": item.url, "qr": _qr_svg(item.url)} for item in issued
            ],
            "skipped": skipped,
            "round": round_,
            "layout": layout if layout in ("letters", "list") else "letters",
            "organisation": Organisation.current(),
        },
    )
    # The links are only on this page; never keep a copy of it anywhere.
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "no-referrer"
    return response


@never_cache
@login_required
@permission_required("selfservice.add_selfservicelink", raise_exception=True)
@require_POST
def round_print(request, pk):
    """Make new links for the chosen units and show them as letters or a list."""
    round_ = get_object_or_404(ReadingRound.objects.select_related("reading_type"), pk=pk)
    scope = request.POST.get("scope", "all")
    units = _round_units(round_, scope)
    if scope == "unreachable":
        units = [
            u
            for u in units
            if (person := primary_contact(u)) is not None and not (person.phone or person.email)
        ]
    if chosen := request.POST.getlist("units"):
        # Specific units, e.g. those a send-out could not reach.
        units = [u for u in units if str(u.pk) in chosen]
    issued, skipped = issue_links(units, round_, request.user)
    return _print(request, issued, skipped, round_, request.POST.get("layout"))


@never_cache
@login_required
@permission_required("selfservice.add_selfservicelink", raise_exception=True)
@require_POST
def unit_print(request, pk):
    """A letter for one unit, for the newest open round of its type if there is one."""
    unit = get_object_or_404(Unit.objects.prefetch_related("unit_contacts__person"), pk=pk)
    round_ = (
        ReadingRound.objects.filter(
            reading_type__unit_type_id=unit.unit_type_id,
            reading_type__archived_at__isnull=True,
            status=ReadingRound.Status.OPEN,
        )
        .select_related("reading_type")
        .order_by("-opens_on", "-pk")
        .first()
    )
    issued, skipped = issue_links([unit], round_, request.user)
    if skipped:
        messages.error(request, _("Add a contact person before printing a letter."))
        return redirect(unit)
    return _print(request, issued, skipped, round_, "letters")


@login_required
@permission_required("selfservice.change_selfservicelink", raise_exception=True)
@require_POST
def link_revoke(request, pk):
    link = get_object_or_404(SelfServiceLink, pk=pk)
    if not link.revoked:
        link.revoked = True
        link.save(update_fields=["revoked"])
    messages.success(request, _("The link no longer works."))
    if link.round_id and request.POST.get("next") != "unit":
        return redirect("selfservice:round_links", link.round_id)
    return redirect(link.unit)


@login_required
@permission_required("selfservice.change_selfservicelink", raise_exception=True)
@require_POST
def round_revoke(request, pk):
    round_ = get_object_or_404(ReadingRound, pk=pk)
    count = 0
    for link in round_.self_service_links.active():
        link.revoked = True
        link.save(update_fields=["revoked"])
        count += 1
    messages.success(request, _("%(count)s links no longer work.") % {"count": count})
    return redirect("selfservice:round_links", round_.pk)


@login_required
@permission_required(
    ["selfservice.view_selfservicelink", "register.view_person", "auditlog.view_logentry"],
    raise_exception=True,
)
def recent_changes(request):
    """What members changed through their links, newest first."""
    entries = (
        LogEntry.objects.filter(additional_data__has_key="self_service_link")
        .filter(~Q(action=LogEntry.Action.ACCESS))
        .select_related("content_type")
        .order_by("-timestamp")[:CHANGES_SHOWN]
    )
    entries = list(entries)
    links = SelfServiceLink.objects.in_bulk(
        {e.additional_data["self_service_link"] for e in entries}
    )
    changes = []
    for entry, described in zip(entries, describe(entries), strict=True):
        described["link"] = links.get(entry.additional_data["self_service_link"])
        changes.append(described)
    return render(request, "selfservice/recent_changes.html", {"changes": changes})
