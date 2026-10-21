from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.plugins import api

from . import documents
from .forms import (
    AgendaItemForm,
    AgendaTemplateForm,
    AttendanceForm,
    MeetingForm,
    MinutesFormSet,
)
from .models import AgendaItem, AgendaTemplate, Attendance, Meeting

PREFIX = "metra_meetings"


def open_meeting(view):
    """Load the meeting from ``pk``; refuse changes once the minutes are approved."""

    @wraps(view)
    def wrapper(request, pk, *args, **kwargs):
        meeting = get_object_or_404(Meeting, pk=pk)
        if meeting.is_approved:
            messages.error(request, _("The minutes are approved and can no longer be changed."))
            return redirect(meeting)
        return view(request, meeting, *args, **kwargs)

    return wrapper


def _changed(request, meeting):
    """After a change to the minutes: approvals given so far no longer count."""
    if meeting.minutes_changed():
        messages.warning(
            request,
            _("The minutes changed, so the checkers' approvals so far were removed."),
        )


def _pdf(request, meeting, make, name):
    try:
        pdf = make(meeting)
    except api.PDFUnavailable:
        messages.error(request, _("PDFs cannot be made on this server (WeasyPrint is missing)."))
        return redirect(meeting)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{name}"'
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@permission_required(f"{PREFIX}.view_meeting", raise_exception=True)
def meeting_list(request):
    now = timezone.now()
    meetings = Meeting.objects.all()
    return render(
        request,
        "metra_meetings/meeting_list.html",
        {
            "upcoming": meetings.filter(starts_at__gte=now).order_by("starts_at", "pk"),
            "past": meetings.filter(starts_at__lt=now),
            "to_approve": [
                m
                for m in request.user.meetings_to_check.all()
                if m.can_be_approved_by(request.user)
            ],
        },
    )


@login_required
@permission_required(f"{PREFIX}.add_meeting", raise_exception=True)
def meeting_create(request):
    form = MeetingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            meeting = form.save(commit=False)
            meeting.created_by = request.user
            meeting.save()
            form.save_m2m()
            template = form.agenda_template()
            if template is not None:
                template.copy_to(meeting)
        if template is not None:
            messages.success(
                request,
                _("The meeting was added with the agenda from %(template)s. Check the items.")
                % {"template": template.name},
            )
        else:
            messages.success(request, _("The meeting was added. Now add the agenda."))
        return redirect(meeting)
    return render(request, "metra_meetings/meeting_form.html", {"form": form, "meeting": None})


@login_required
@permission_required(f"{PREFIX}.view_meeting", raise_exception=True)
def meeting_detail(request, pk):
    meeting = get_object_or_404(Meeting.objects.select_related("chair", "secretary"), pk=pk)
    context = documents.minutes_context(meeting)
    context |= {
        "can_approve": meeting.can_be_approved_by(request.user),
        "missing": meeting.missing_approvals(),
        "can_send_notice": request.user.has_perm(f"{PREFIX}.change_meeting")
        and request.user.has_perm("messaging.send_broadcast"),
    }
    return render(request, "metra_meetings/meeting_detail.html", context)


@login_required
@permission_required(f"{PREFIX}.change_meeting", raise_exception=True)
@open_meeting
def meeting_edit(request, meeting):
    form = MeetingForm(request.POST or None, instance=meeting)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            if form.has_changed():
                _changed(request, meeting)
        messages.success(request, _("The meeting was saved."))
        return redirect(meeting)
    return render(request, "metra_meetings/meeting_form.html", {"form": form, "meeting": meeting})


@login_required
@permission_required(f"{PREFIX}.delete_meeting", raise_exception=True)
@open_meeting
def meeting_delete(request, meeting):
    if request.method == "POST":
        meeting.delete()
        messages.success(request, _("The meeting was deleted."))
        return redirect("metra_meetings:meeting_list")
    return render(request, "metra_meetings/meeting_confirm_delete.html", {"meeting": meeting})


@require_POST
@login_required
@permission_required(f"{PREFIX}.change_meeting", raise_exception=True)
@open_meeting
def meeting_status(request, meeting):
    """Mark the meeting called (the notice went out) or held, or back to being prepared."""
    wanted = request.POST.get("status")
    allowed = {Meeting.Status.DRAFT, Meeting.Status.CALLED, Meeting.Status.HELD}
    if wanted not in allowed:
        return HttpResponseBadRequest()
    meeting.status = wanted
    meeting.save(update_fields=["status"])
    if wanted != Meeting.Status.HELD:
        _changed(request, meeting)
    messages.success(
        request,
        _("The meeting is now: %(status)s.") % {"status": meeting.get_status_display()},
    )
    return redirect(meeting)


# Agenda and minutes.


@login_required
@permission_required(f"{PREFIX}.add_agendaitem", raise_exception=True)
@open_meeting
def item_create(request, meeting):
    last = meeting.items.order_by("-order").first()
    form = AgendaItemForm(request.POST or None, initial={"order": (last.order + 1) if last else 1})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.instance.meeting = meeting
            form.save()
            _changed(request, meeting)
        messages.success(request, _("The item was added to the agenda."))
        if "another" in request.POST:
            return redirect("metra_meetings:item_create", pk=meeting.pk)
        return redirect(meeting)
    return render(
        request, "metra_meetings/item_form.html", {"form": form, "meeting": meeting, "item": None}
    )


@login_required
@permission_required(f"{PREFIX}.change_agendaitem", raise_exception=True)
@open_meeting
def item_edit(request, meeting, item_pk):
    item = get_object_or_404(AgendaItem, pk=item_pk, meeting=meeting)
    form = AgendaItemForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            if form.has_changed():
                _changed(request, meeting)
        messages.success(request, _("The item was saved."))
        return redirect(meeting)
    return render(
        request, "metra_meetings/item_form.html", {"form": form, "meeting": meeting, "item": item}
    )


@require_POST
@login_required
@permission_required(f"{PREFIX}.change_agendaitem", raise_exception=True)
@open_meeting
def item_delete(request, meeting, item_pk):
    item = get_object_or_404(AgendaItem, pk=item_pk, meeting=meeting)
    with transaction.atomic():
        item.delete()
        _changed(request, meeting)
    messages.success(request, _("The item was removed from the agenda."))
    return redirect(meeting)


@login_required
@permission_required(f"{PREFIX}.change_agendaitem", raise_exception=True)
@open_meeting
def minutes_edit(request, meeting):
    """The minutes and decisions of every item, on one page for the secretary."""
    formset = MinutesFormSet(request.POST or None, queryset=meeting.items.all())
    if request.method == "POST" and formset.is_valid():
        with transaction.atomic():
            formset.save()
            if formset.has_changed():
                _changed(request, meeting)
        messages.success(request, _("The minutes were saved."))
        if "stay" in request.POST:
            return redirect("metra_meetings:minutes_edit", pk=meeting.pk)
        return redirect(meeting)
    forms = list(zip(range(1, len(formset.forms) + 1), formset.forms, strict=True))
    return render(
        request,
        "metra_meetings/minutes_form.html",
        {"formset": formset, "numbered_forms": forms, "meeting": meeting},
    )


# Attendance.


@login_required
@permission_required(f"{PREFIX}.view_attendance", raise_exception=True)
def attendance(request, pk):
    meeting = get_object_or_404(Meeting, pk=pk)
    can_add = request.user.has_perm(f"{PREFIX}.add_attendance") and not meeting.is_approved
    form = AttendanceForm(meeting=meeting) if can_add else None
    return _attendance_page(request, meeting, form)


def _attendance_page(request, meeting, form, status=200):
    attendances = list(meeting.attendances.select_related("unit"))
    return render(
        request,
        "metra_meetings/attendance.html",
        {
            "meeting": meeting,
            "attendances": attendances,
            "total_votes": sum(a.votes for a in attendances),
            "units_present": len({a.unit_id for a in attendances if a.unit_id}),
            "form": form,
        },
        status=status,
    )


@require_POST
@login_required
@permission_required(f"{PREFIX}.add_attendance", raise_exception=True)
@open_meeting
def attendance_add(request, meeting):
    form = AttendanceForm(request.POST, meeting=meeting)
    if form.is_valid():
        with transaction.atomic():
            form.instance.meeting = meeting
            form.instance.votes = form.cleaned_data["votes"]
            form.save()
            _changed(request, meeting)
        messages.success(
            request, _("%(name)s was added as present.") % {"name": form.instance.name}
        )
        return redirect("metra_meetings:attendance", pk=meeting.pk)
    return _attendance_page(request, meeting, form, status=400)


@login_required
@permission_required(f"{PREFIX}.change_attendance", raise_exception=True)
@open_meeting
def attendance_edit(request, meeting, attendance_pk):
    present = get_object_or_404(Attendance, pk=attendance_pk, meeting=meeting)
    form = AttendanceForm(request.POST or None, instance=present, meeting=meeting)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.instance.votes = form.cleaned_data["votes"]
            form.save()
            _changed(request, meeting)
        messages.success(request, _("The attendance was saved."))
        return redirect("metra_meetings:attendance", pk=meeting.pk)
    return render(
        request,
        "metra_meetings/attendance_form.html",
        {"form": form, "meeting": meeting, "present": present},
    )


@require_POST
@login_required
@permission_required(f"{PREFIX}.change_attendance", raise_exception=True)
@open_meeting
def attendance_remove(request, meeting, attendance_pk):
    present = get_object_or_404(Attendance, pk=attendance_pk, meeting=meeting)
    with transaction.atomic():
        present.delete()
        _changed(request, meeting)
    messages.success(request, _("%(name)s was removed from the list.") % {"name": present.name})
    return redirect("metra_meetings:attendance", pk=meeting.pk)


# Documents and the notice.


@login_required
@permission_required(f"{PREFIX}.view_meeting", raise_exception=True)
def agenda_pdf(request, pk):
    meeting = get_object_or_404(Meeting, pk=pk)
    return _pdf(request, meeting, documents.agenda_pdf, documents.agenda_filename(meeting))


@login_required
@permission_required(f"{PREFIX}.view_meeting", raise_exception=True)
def minutes_pdf(request, pk):
    meeting = get_object_or_404(Meeting, pk=pk)
    return _pdf(request, meeting, documents.minutes_pdf, documents.minutes_filename(meeting))


@require_POST
@login_required
@permission_required(f"{PREFIX}.change_meeting", raise_exception=True)
@permission_required("messaging.send_broadcast", raise_exception=True)
def send_notice(request, pk):
    """Open the New message form with the notice written and the agenda attached."""
    meeting = get_object_or_404(Meeting, pk=pk)
    try:
        pdf = documents.agenda_pdf(meeting)
    except api.PDFUnavailable:
        messages.error(request, _("PDFs cannot be made on this server (WeasyPrint is missing)."))
        return redirect(meeting)
    subject, short, email = documents.notice_texts(meeting)
    try:
        url = api.message_draft(
            request,
            subject,
            short,
            files=[(documents.agenda_filename(meeting), pdf, "application/pdf")],
            email_body=email,
        )
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
        return redirect(meeting)
    messages.info(
        request,
        _(
            "The notice is ready with the agenda attached. Choose who gets it, check and send. "
            "Then mark the meeting as called."
        ),
    )
    return redirect(url)


# Approval by the minute checkers.


@login_required
@permission_required(f"{PREFIX}.view_meeting", raise_exception=True)
def approve(request, pk):
    meeting = get_object_or_404(Meeting, pk=pk)
    if not meeting.can_be_approved_by(request.user):
        raise PermissionDenied
    if request.method == "POST":
        with transaction.atomic():
            done = meeting.approve(request.user)
        if done:
            messages.success(
                request,
                _("The minutes are approved by every checker and can no longer be changed."),
            )
        else:
            messages.success(
                request, _("Thank you. The minutes are approved when every checker has approved.")
            )
        return redirect(meeting)
    context = documents.minutes_context(meeting)
    return render(request, "metra_meetings/approve.html", context)


# Agenda templates.


@login_required
@permission_required(f"{PREFIX}.view_agendatemplate", raise_exception=True)
def template_list(request):
    return render(
        request,
        "metra_meetings/template_list.html",
        {"templates": AgendaTemplate.objects.all()},
    )


@login_required
@permission_required(f"{PREFIX}.add_agendatemplate", raise_exception=True)
def template_create(request):
    return _template_form(request, AgendaTemplate())


@login_required
@permission_required(f"{PREFIX}.change_agendatemplate", raise_exception=True)
def template_edit(request, pk):
    return _template_form(request, get_object_or_404(AgendaTemplate, pk=pk))


def _template_form(request, template):
    form = AgendaTemplateForm(request.POST or None, instance=template)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("The agenda template was saved."))
        return redirect("metra_meetings:template_list")
    return render(
        request,
        "metra_meetings/template_form.html",
        {"form": form, "template": template if template.pk else None},
    )


@login_required
@permission_required(f"{PREFIX}.delete_agendatemplate", raise_exception=True)
def template_delete(request, pk):
    template = get_object_or_404(AgendaTemplate, pk=pk)
    if request.method == "POST":
        template.delete()
        messages.success(request, _("The agenda template was deleted."))
        return redirect("metra_meetings:template_list")
    return render(request, "metra_meetings/template_confirm_delete.html", {"template": template})
