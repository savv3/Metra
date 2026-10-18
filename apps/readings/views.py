from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.register import csv_io
from apps.register.history import log_view, object_history
from apps.register.models import Unit

from .forms import ReadingForm, RoundForm
from .models import Reading, ReadingRound
from .templatetags.readings import reading_value
from .usage import assess, earlier_values

SHOW_CHOICES = ["all", "missing", "submitted"]


def _is_htmx(request, target=None):
    if not request.headers.get("HX-Request"):
        return False
    return target is None or request.headers.get("HX-Target") == target


# Rounds


@login_required
@permission_required("readings.view_readinground", raise_exception=True)
def round_list(request):
    rounds = list(
        ReadingRound.objects.select_related("reading_type").annotate(submitted=Count("readings"))
    )
    for round_ in rounds:
        round_.expected = round_.expected_units().count()
    return render(request, "readings/round_list.html", {"rounds": rounds})


@login_required
@permission_required("readings.add_readinground", raise_exception=True)
def round_create(request):
    form = RoundForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        round_ = form.save()
        messages.success(request, _("Saved %(name)s.") % {"name": round_})
        return redirect(round_)
    return render(request, "readings/round_form.html", {"form": form, "round": None})


@login_required
@permission_required("readings.change_readinground", raise_exception=True)
def round_edit(request, pk):
    round_ = get_object_or_404(ReadingRound, pk=pk)
    form = RoundForm(request.POST or None, instance=round_)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Saved %(name)s.") % {"name": round_})
        return redirect(round_)
    return render(request, "readings/round_form.html", {"form": form, "round": round_})


def _round_rows(round_, units):
    """One row per unit: its reading in the round (or None), usage and warnings."""
    units = list(units)
    unit_ids = [unit.pk for unit in units]
    readings = {
        reading.unit_id: reading
        for reading in round_.readings.filter(unit_id__in=unit_ids).select_related("submitted_by")
    }
    earlier = earlier_values(round_, unit_ids)
    rows = []
    for unit in units:
        reading = readings.get(unit.pk)
        rows.append(
            {
                "unit": unit,
                "reading": reading,
                "assessment": assess(
                    round_.reading_type,
                    reading.value if reading else None,
                    earlier.get(unit.pk, []),
                ),
            }
        )
    return rows


def _round_filters(request):
    show = request.GET.get("show", "all")
    return {
        "q": request.GET.get("q", "").strip(),
        "show": show if show in SHOW_CHOICES else "all",
    }


def _filtered_units(round_, filters):
    units = round_.expected_units()
    if filters["q"]:
        q = filters["q"]
        units = units.filter(
            Q(name__icontains=q)
            | Q(street_address__icontains=q)
            | Q(contacts__first_name__icontains=q)
            | Q(contacts__last_name__icontains=q)
        ).distinct()
    if filters["show"] == "missing":
        units = units.exclude(readings__round=round_)
    elif filters["show"] == "submitted":
        units = units.filter(readings__round=round_)
    return units.order_by("name", "pk")


@login_required
@permission_required("readings.view_readinground", raise_exception=True)
def round_detail(request, pk):
    round_ = get_object_or_404(ReadingRound.objects.select_related("reading_type"), pk=pk)
    filters = _round_filters(request)
    expected = round_.expected_units().count()
    submitted = round_.readings.count()
    context = {
        "round": round_,
        "rows": _round_rows(round_, _filtered_units(round_, filters)),
        "filters": filters,
        "query": request.GET.urlencode(),
        "expected": expected,
        "submitted": submitted,
        "missing": max(expected - submitted, 0),
        "can_enter": request.user.has_perms(["readings.add_reading", "readings.change_reading"]),
    }
    if _is_htmx(request, "results"):
        return render(request, "readings/_round_results.html", context)
    return render(request, "readings/round_detail.html", context)


@login_required
@permission_required(["readings.view_reading", "register.view_unit"], raise_exception=True)
def round_export(request, pk):
    round_ = get_object_or_404(ReadingRound.objects.select_related("reading_type"), pk=pk)
    filters = _round_filters(request)
    rows = _round_rows(round_, _filtered_units(round_, filters))
    reading_type = round_.reading_type
    header = [
        _("Unit"),
        _("Address"),
        _("Period"),
        _("Previous reading"),
        _("Reading"),
        _("Usage"),
        _("Unit of measure"),
        _("Source"),
        _("Entered by"),
        _("Submitted"),
        _("Note"),
        _("Warnings"),
    ]
    lines = []
    for row in rows:
        reading, assessment = row["reading"], row["assessment"]
        lines.append(
            [
                row["unit"].name,
                row["unit"].address_line,
                round_.period_label,
                reading_value(assessment.previous, reading_type, unit=False),
                reading_value(reading and reading.value, reading_type, unit=False),
                reading_value(assessment.usage, reading_type, unit=False),
                reading_type.unit_label,
                reading.get_source_display() if reading else "",
                (reading.submitted_by or "") if reading else "",
                timezone.localtime(reading.submitted_at).strftime("%Y-%m-%d %H:%M")
                if reading
                else "",
                reading.note if reading else "",
                " ".join(assessment.warnings),
            ]
        )
    readings = [row["reading"] for row in rows if row["reading"]]
    csv_io.log_export(request, Reading, readings, {**filters, "round": round_.pk})
    filename = f"readings-{round_.reading_type.name}-{round_.period_label}.csv"
    return csv_io.csv_response(_safe_filename(filename), header, lines)


def _safe_filename(name):
    return "".join(c if c.isalnum() or c in "-_." else "-" for c in name)


# Readings


@login_required
@permission_required(["readings.add_reading", "readings.change_reading"], raise_exception=True)
def reading_entry(request, pk, unit_pk):
    """Enter or correct one unit's reading. From the round's table (HTMX, value
    only) the response is the updated table row; otherwise a full form page."""
    round_ = get_object_or_404(ReadingRound.objects.select_related("reading_type"), pk=pk)
    unit = get_object_or_404(Unit, pk=unit_pk)
    reading = Reading.objects.filter(round=round_, unit=unit).first()
    if reading is None and unit.unit_type_id != round_.reading_type.unit_type_id:
        raise Http404
    inline = _is_htmx(request) and request.POST.get("inline")
    form = ReadingForm(request.POST or None, instance=reading, round_=round_, unit=unit)
    if inline:
        del form.fields["note"]
    if request.method == "POST" and form.is_valid():
        reading = form.save(commit=False)
        if "value" in form.changed_data or reading.pk is None:
            reading.source = Reading.Source.STAFF
            reading.submitted_by = request.user
            reading.submitted_at = timezone.now()
        reading.save()
        assessment = assess(
            round_.reading_type, reading.value, earlier_values(round_, [unit.pk]).get(unit.pk, [])
        )
        if inline:
            row = {"unit": unit, "reading": reading, "assessment": assessment, "saved": True}
            return render(
                request,
                "readings/_round_row.html",
                {"round": round_, "row": row, "can_enter": True},
            )
        messages.success(request, _("Saved the reading for %(name)s.") % {"name": unit})
        for warning in assessment.warnings:
            messages.warning(request, warning)
        if request.POST.get("next") == "unit":
            return redirect(unit)
        return redirect(f"{round_.get_absolute_url()}#unit-{unit.pk}")
    if inline:
        row = _round_rows(round_, [unit])[0]
        row["errors"] = form.errors.get("value")
        row["posted"] = request.POST.get("value", "")
        return render(
            request, "readings/_round_row.html", {"round": round_, "row": row, "can_enter": True}
        )
    assessment = assess(
        round_.reading_type,
        reading.value if reading else None,
        earlier_values(round_, [unit.pk]).get(unit.pk, []),
    )
    context = {
        "round": round_,
        "unit": unit,
        "reading": reading,
        "form": form,
        "assessment": assessment,
        "next": request.GET.get("next") or request.POST.get("next", ""),
    }
    if reading is not None:
        log_view(reading)
        if request.user.has_perm("auditlog.view_logentry"):
            context["history"] = object_history(reading)
    return render(request, "readings/reading_form.html", context)
