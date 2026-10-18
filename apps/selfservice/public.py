"""The member page behind a personal link: no login, one page, works on a phone."""

from auditlog.context import set_extra_data
from auditlog.models import LogEntry
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache

from apps.core.language import switch_language
from apps.core.models import Notice
from apps.messaging.models import ConsentRecord
from apps.readings.models import Reading
from apps.readings.usage import earlier_values
from apps.register.models import Organisation

from . import ratelimit
from .forms import MemberContactForm, MemberReadingForm
from .models import SelfServiceLink


def _private(response):
    """Keep the page out of search engines, caches and other sites' logs."""
    response["X-Robots-Tag"] = "noindex, nofollow"
    # same-origin, not no-referrer: the address (with its token) never goes to
    # other sites, and browsers still send a real Origin on the page's own
    # form posts, which Django's CSRF check needs.
    response["Referrer-Policy"] = "same-origin"
    return response


def _unavailable(request, status=404):
    """The same page for unknown, expired and revoked links, so none can be told apart."""
    template = "selfservice/unavailable.html" if status == 404 else "selfservice/too_many.html"
    return _private(render(request, template, status=status))


def _log_context(request, link, **extra):
    """Audit entries made through a link name the link and the person behind it."""
    return set_extra_data(
        {
            "additional_data": {
                "self_service_link": link.pk,
                "person_id": link.person_id,
                "unit_id": link.unit_id,
                **extra,
            },
            "remote_addr": ratelimit.client_ip(request) or None,
        }
    )


def _log_visit(request, link):
    LogEntry.objects.log_create(
        link,
        action=LogEntry.Action.ACCESS,
        changes=None,
        force_log=True,
        additional_data={"self_service_link": link.pk, "person_id": link.person_id},
        remote_addr=ratelimit.client_ip(request) or None,
    )
    SelfServiceLink.objects.filter(pk=link.pk).update(last_used_at=timezone.now())


@never_cache
def member_page(request, token):
    if switched := switch_language(request):
        return _private(switched)
    if not ratelimit.allow_visit(request):
        return _unavailable(request, status=429)
    link = SelfServiceLink.find(token)
    if link is None:
        ratelimit.record_failure(request)
        return _unavailable(request)

    round_ = link.round
    reading = None
    reading_form = None
    previous = None
    if round_ is not None and round_.reading_type.unit_type_id == link.unit.unit_type_id:
        reading = Reading.objects.filter(round=round_, unit=link.unit).first()
        earlier = earlier_values(round_, [link.unit_id]).get(link.unit_id, [])
        previous = earlier[0] if earlier else None
        if round_.accepts_member_readings:
            initial = {"value": reading.value} if reading else None
            reading_form = MemberReadingForm(
                request.POST if request.POST.get("action") == "reading" else None,
                initial=initial,
                reading_type=round_.reading_type,
            )
    contact_form = MemberContactForm(
        request.POST if request.POST.get("action") == "contact" else None, instance=link.person
    )

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "reading" and reading_form is not None and reading_form.is_valid():
            reading = reading or Reading(round=round_, unit=link.unit)
            reading.value = reading_form.cleaned_data["value"]
            reading.source = Reading.Source.MEMBER
            reading.submitted_by = None
            reading.submitted_by_person = link.person
            reading.submitted_at = timezone.now()
            with _log_context(request, link, round_id=round_.pk):
                reading.save()
            messages.success(request, _("Thank you. Your reading is saved."))
            return _private(redirect(request.path + "#reading"))
        if action == "newsletter":
            wanted = request.POST.get("subscribed") == "1"
            with _log_context(request, link):
                ConsentRecord.record(link.person, wanted, ConsentRecord.Source.SELF_SERVICE)
            if wanted:
                messages.success(request, _("Thank you. You will get the newsletter."))
            else:
                messages.success(request, _("You will not get the newsletter."))
            return _private(redirect(request.path + "#newsletter"))
        if action == "contact" and contact_form.is_valid():
            if contact_form.has_changed():
                with _log_context(request, link):
                    contact_form.save()
                messages.success(request, _("Thank you. Your contact details are updated."))
            else:
                messages.info(request, _("Nothing was changed."))
            return _private(redirect(request.path + "#contact"))
    else:
        _log_visit(request, link)

    household = [
        c
        for c in link.unit.unit_contacts.select_related("person")
        if not c.person.is_archived and c.person_id != link.person_id
    ]
    context = {
        "link": link,
        "unit": link.unit,
        "person": link.person,
        "round": round_,
        "reading": reading,
        "previous": previous,
        "reading_form": reading_form,
        "contact_form": contact_form,
        "household": household,
        "organisation": Organisation.current(),
        "notices": Notice.objects.current(),
        "consent": ConsentRecord.current(link.person),
    }
    return _private(render(request, "selfservice/member.html", context))
