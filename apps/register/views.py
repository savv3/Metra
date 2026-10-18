from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .custom_fields import custom_values
from .forms import PersonForm, UnitContactForm, UnitForm
from .history import history, log_view
from .models import CustomField, Person, Tag, Unit, UnitContact, UnitType

PAGE_SIZE = 50


def _list_page(request, queryset):
    return Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page"))


def _render_list(request, template, partial, context):
    """Full page on a normal request; only the results table for HTMX searches."""
    if request.headers.get("HX-Request") and request.headers.get("HX-Target") == "results":
        return render(request, partial, context)
    return render(request, template, context)


def _archive_filter(queryset, value):
    if value == "archived":
        return queryset.archived()
    if value == "all":
        return queryset
    return queryset.active()


# Units


@login_required
@permission_required("register.view_unit", raise_exception=True)
def unit_list(request):
    filters = {
        "q": request.GET.get("q", "").strip(),
        "type": request.GET.get("type", ""),
        "status": request.GET.get("status", ""),
        "tag": request.GET.get("tag", ""),
        "show": request.GET.get("show", "active"),
    }
    units = Unit.objects.select_related("unit_type").prefetch_related("tags")
    units = _archive_filter(units, filters["show"])
    if filters["q"]:
        q = filters["q"]
        units = units.filter(
            Q(name__icontains=q)
            | Q(street_address__icontains=q)
            | Q(city__icontains=q)
            | Q(contacts__first_name__icontains=q)
            | Q(contacts__last_name__icontains=q)
            | Q(contacts__email__icontains=q)
            | Q(contacts__phone__icontains=q)
        ).distinct()
    if filters["type"].isdigit():
        units = units.filter(unit_type_id=filters["type"])
    if filters["status"] in Unit.Status.values:
        units = units.filter(status=filters["status"])
    if filters["tag"].isdigit():
        units = units.filter(tags__id=filters["tag"])
    context = {
        "page": _list_page(request, units),
        "filters": filters,
        "unit_types": UnitType.objects.all(),
        "statuses": Unit.Status.choices,
        "tags": Tag.objects.all(),
    }
    return _render_list(request, "register/unit_list.html", "register/_unit_results.html", context)


@login_required
@permission_required("register.add_unit", raise_exception=True)
def unit_create(request):
    unit_types = UnitType.objects.all()
    type_id = request.GET.get("type") or request.POST.get("unit_type")
    if not type_id and unit_types.count() == 1:
        type_id = unit_types.first().pk
    if not type_id:
        return render(request, "register/unit_type_choose.html", {"unit_types": unit_types})
    unit_type = get_object_or_404(UnitType, pk=type_id)
    form = UnitForm(request.POST or None, unit_type=unit_type)
    if request.method == "POST" and form.is_valid():
        unit = form.save()
        messages.success(request, _("Saved %(name)s.") % {"name": unit})
        return redirect(unit)
    return render(
        request,
        "register/unit_form.html",
        {"form": form, "unit_type": unit_type, "unit": None},
    )


@login_required
@permission_required("register.view_unit", raise_exception=True)
def unit_detail(request, pk):
    unit = get_object_or_404(Unit.objects.select_related("unit_type"), pk=pk)
    context = {
        "unit": unit,
        "custom_values": custom_values(unit.unit_type.custom_fields.all(), unit.custom_data),
        "unit_contacts": unit.unit_contacts.select_related("person"),
        "contact_form": UnitContactForm(unit=unit),
    }
    log_view(unit)
    if request.user.has_perm("auditlog.view_logentry"):
        context["history"] = history(unit, "unit_id")
    return render(request, "register/unit_detail.html", context)


@login_required
@permission_required("register.change_unit", raise_exception=True)
def unit_edit(request, pk):
    unit = get_object_or_404(Unit.objects.select_related("unit_type"), pk=pk)
    form = UnitForm(request.POST or None, instance=unit, unit_type=unit.unit_type)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Saved %(name)s.") % {"name": unit})
        return redirect(unit)
    return render(
        request,
        "register/unit_form.html",
        {"form": form, "unit_type": unit.unit_type, "unit": unit},
    )


@login_required
@permission_required("register.change_unit", raise_exception=True)
@require_POST
def unit_archive(request, pk):
    unit = get_object_or_404(Unit, pk=pk)
    if unit.is_archived:
        unit.restore()
        messages.success(request, _("Restored %(name)s.") % {"name": unit})
    else:
        unit.archive()
        messages.success(request, _("Archived %(name)s.") % {"name": unit})
    return redirect(unit)


@login_required
@permission_required("register.add_unitcontact", raise_exception=True)
@require_POST
def unit_contact_add(request, pk):
    unit = get_object_or_404(Unit, pk=pk)
    form = UnitContactForm(request.POST, unit=unit)
    if form.is_valid():
        contact = form.save()
        messages.success(request, _("Added %(name)s.") % {"name": contact.person})
    else:
        for error in form.non_field_errors() or [_("Choose a person and a role.")]:
            messages.error(request, error)
    return redirect(unit)


@login_required
@permission_required("register.delete_unitcontact", raise_exception=True)
@require_POST
def unit_contact_remove(request, pk, contact_pk):
    contact = get_object_or_404(UnitContact, pk=contact_pk, unit_id=pk)
    contact.delete()
    messages.success(request, _("Removed %(name)s.") % {"name": contact.person})
    return redirect(contact.unit)


# People


@login_required
@permission_required("register.view_person", raise_exception=True)
def person_list(request):
    filters = {
        "q": request.GET.get("q", "").strip(),
        "tag": request.GET.get("tag", ""),
        "show": request.GET.get("show", "active"),
    }
    people = _archive_filter(Person.objects.prefetch_related("tags"), filters["show"])
    if filters["q"]:
        q = filters["q"]
        people = people.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(email__icontains=q)
            | Q(phone__icontains=q)
            | Q(street_address__icontains=q)
            | Q(city__icontains=q)
        )
    if filters["tag"].isdigit():
        people = people.filter(tags__id=filters["tag"])
    context = {"page": _list_page(request, people), "filters": filters, "tags": Tag.objects.all()}
    return _render_list(
        request, "register/person_list.html", "register/_person_results.html", context
    )


@login_required
@permission_required("register.add_person", raise_exception=True)
def person_create(request):
    form = PersonForm(request.POST or None)
    unit = None
    if unit_id := request.GET.get("unit") or request.POST.get("for_unit"):
        if not request.user.has_perm("register.add_unitcontact"):
            raise PermissionDenied
        unit = get_object_or_404(Unit, pk=unit_id)
    if request.method == "POST" and form.is_valid():
        person = form.save()
        messages.success(request, _("Saved %(name)s.") % {"name": person})
        if unit:
            role = request.POST.get("role")
            if role not in UnitContact.Role.values:
                role = UnitContact.Role.CONTACT
            UnitContact.objects.create(unit=unit, person=person, role=role)
            return redirect(unit)
        return redirect(person)
    return render(
        request,
        "register/person_form.html",
        {"form": form, "person": None, "for_unit": unit, "roles": UnitContact.Role.choices},
    )


@login_required
@permission_required("register.view_person", raise_exception=True)
def person_detail(request, pk):
    person = get_object_or_404(Person, pk=pk)
    definitions = CustomField.objects.filter(target=CustomField.Target.PERSON)
    context = {
        "person": person,
        "custom_values": custom_values(definitions, person.custom_data),
        "unit_contacts": person.unit_contacts.select_related("unit", "unit__unit_type"),
    }
    log_view(person)
    if request.user.has_perm("auditlog.view_logentry"):
        context["history"] = history(person, "person_id")
    return render(request, "register/person_detail.html", context)


@login_required
@permission_required("register.change_person", raise_exception=True)
def person_edit(request, pk):
    person = get_object_or_404(Person, pk=pk)
    form = PersonForm(request.POST or None, instance=person)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Saved %(name)s.") % {"name": person})
        return redirect(person)
    return render(
        request,
        "register/person_form.html",
        {"form": form, "person": person, "for_unit": None, "roles": UnitContact.Role.choices},
    )


@login_required
@permission_required("register.change_person", raise_exception=True)
@require_POST
def person_archive(request, pk):
    person = get_object_or_404(Person, pk=pk)
    if person.is_archived:
        person.restore()
        messages.success(request, _("Restored %(name)s.") % {"name": person})
    else:
        person.archive()
        messages.success(request, _("Archived %(name)s.") % {"name": person})
    return redirect(person)
