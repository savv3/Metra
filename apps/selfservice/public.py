"""The member page behind a personal link: no login, one page, works on a phone."""

from dataclasses import dataclass

from auditlog.context import set_extra_data
from auditlog.models import LogEntry
from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
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


@dataclass
class MemberLink:
    """The member behind a personal link, for plugins (``api.member_link``)
    and member page panels: the ``unit`` and ``person`` it belongs to, and the
    ``token`` for addresses under the same link."""

    unit: object
    person: object
    token: str
    link: SelfServiceLink

    def log_access(self, request, obj):
        """Record in the audit log that the member opened ``obj`` through the link."""
        LogEntry.objects.log_create(
            obj,
            action=LogEntry.Action.ACCESS,
            changes=None,
            force_log=True,
            additional_data={"self_service_link": self.link.pk, "person_id": self.person.pk},
            remote_addr=ratelimit.client_ip(request) or None,
        )


def member_link(request, token):
    """The MemberLink for a token, or None. Counts against the same rate limit
    as the member page; an unknown, expired or revoked token counts as a
    failure. Answer None with ``member_unavailable(request)``."""
    if not ratelimit.allow_visit(request):
        request._member_link_status = 429
        return None
    link = SelfServiceLink.find(token)
    if link is None:
        ratelimit.record_failure(request)
        return None
    return MemberLink(unit=link.unit, person=link.person, token=token, link=link)


def member_unavailable(request):
    """The page for unknown, expired and revoked links (or too many tries)."""
    return _unavailable(request, status=getattr(request, "_member_link_status", 404))


def member_response(response):
    """Mark a response made for a member link as private: not cached, not
    indexed and its address never sent to other sites."""
    response["Cache-Control"] = "private, no-store"
    return _private(response)


def member_page_url(token):
    """The full address of the member page for a token."""
    return settings.BASE_URL + reverse("selfservice:member", args=[token])


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
        "invoices": _invoices(link),
        "member_link": MemberLink(unit=link.unit, person=link.person, token=token, link=link),
    }
    return _private(render(request, "selfservice/member.html", context))


def _invoices(link):
    """The household's issued invoices and credit notes, newest first."""
    if not apps.is_installed("apps.invoicing"):
        return []
    from apps.invoicing.models import Invoice

    return Invoice.objects.issued().filter(unit=link.unit).order_by("-issue_date", "-sequence")[:20]


@never_cache
def member_invoice(request, token, pk):
    """An invoice PDF for the household behind the link."""
    if not ratelimit.allow_visit(request):
        return _unavailable(request, status=429)
    link = SelfServiceLink.find(token)
    if link is None or not apps.is_installed("apps.invoicing"):
        ratelimit.record_failure(request)
        return _unavailable(request)
    from apps.invoicing.delivery import filename
    from apps.invoicing.models import Invoice
    from apps.invoicing.pdf import PDFUnavailable, render_pdf
    from apps.invoicing.views import pdf_response

    invoice = Invoice.objects.issued().filter(pk=pk, unit=link.unit).first()
    if invoice is None:
        return _unavailable(request)
    LogEntry.objects.log_create(
        invoice,
        action=LogEntry.Action.ACCESS,
        changes=None,
        force_log=True,
        additional_data={"self_service_link": link.pk, "person_id": link.person_id},
        remote_addr=ratelimit.client_ip(request) or None,
    )
    try:
        pdf = render_pdf([invoice])
    except PDFUnavailable:
        return _unavailable(request)
    return _private(pdf_response(pdf, filename(invoice)))
