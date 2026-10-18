"""Import units with their contacts from CSV: upload, map columns, preview, import.

The parsed file is kept in the session between the steps and removed when the
import is done or a new file is uploaded; it is never written to disk.
"""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from . import csv_io
from .models import UnitContact, UnitType

SESSION_KEY = "register_csv_import"
IMPORT_PERMISSIONS = ["register.add_unit", "register.add_person", "register.add_unitcontact"]


class UploadForm(forms.Form):
    unit_type = forms.ModelChoiceField(
        label=gettext_lazy("Unit type"), queryset=UnitType.objects.all(), empty_label=None
    )
    file = forms.FileField(
        label=gettext_lazy("CSV file"),
        help_text=gettext_lazy(
            "UTF-8, with semicolons or commas between the columns and one header row."
        ),
    )
    skip_existing = forms.BooleanField(
        label=gettext_lazy("Skip rows whose unit name is already in the register"),
        required=False,
        initial=True,
    )

    def clean(self):
        cleaned = super().clean()
        if upload := cleaned.get("file"):
            try:
                cleaned["headers"], cleaned["rows"] = csv_io.read_csv(upload)
            except csv_io.CSVError as error:
                self.add_error("file", str(error))
        return cleaned


class MappingForm(forms.Form):
    def __init__(self, *args, targets, headers, **kwargs):
        super().__init__(*args, **kwargs)
        self.targets = targets
        columns = [("", _("Not in the file"))] + [
            (str(index), header or _("Column %(number)s") % {"number": index + 1})
            for index, header in enumerate(headers)
        ]
        for target in targets:
            self.fields[target.key] = forms.ChoiceField(
                label=target.label, choices=columns, required=target.required
            )
        self.fields["default_role"] = forms.ChoiceField(
            label=_("Role for contacts without one"),
            choices=UnitContact.Role.choices,
            initial=UnitContact.Role.OWNER,
        )

    def unit_fields(self):
        return [self[t.key] for t in self.targets if not t.key.startswith("contact:")]

    def contact_fields(self):
        return [self[t.key] for t in self.targets if t.key.startswith("contact:")]

    def mapping(self):
        return {
            t.key: int(self.cleaned_data[t.key]) for t in self.targets if self.cleaned_data[t.key]
        }


def _pending(request):
    data = request.session.get(SESSION_KEY)
    if not data:
        return None, None
    return data, get_object_or_404(UnitType, pk=data["unit_type"])


@login_required
@permission_required(IMPORT_PERMISSIONS, raise_exception=True)
def unit_import(request):
    form = UploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        request.session[SESSION_KEY] = {
            "unit_type": form.cleaned_data["unit_type"].pk,
            "filename": form.cleaned_data["file"].name,
            "headers": form.cleaned_data["headers"],
            "rows": form.cleaned_data["rows"],
            "skip_existing": form.cleaned_data["skip_existing"],
        }
        return redirect("register:unit_import_map")
    return render(request, "register/import_upload.html", {"form": form})


@login_required
@permission_required(IMPORT_PERMISSIONS, raise_exception=True)
def unit_import_map(request):
    data, unit_type = _pending(request)
    if data is None:
        return redirect("register:unit_import")
    targets = csv_io.build_targets(unit_type)
    if "mapping" in data:
        initial = {key: str(index) for key, index in data["mapping"].items()}
        initial["default_role"] = data["default_role"]
    else:
        guessed = csv_io.guess_mapping(targets, data["headers"])
        initial = {key: str(index) for key, index in guessed.items()}
    form = MappingForm(
        request.POST or None, initial=initial, targets=targets, headers=data["headers"]
    )
    if request.method == "POST" and form.is_valid():
        data["mapping"] = form.mapping()
        data["default_role"] = form.cleaned_data["default_role"]
        request.session.modified = True
        return redirect("register:unit_import_preview")
    context = {"form": form, "data": data, "unit_type": unit_type, "sample": data["rows"][:3]}
    return render(request, "register/import_map.html", context)


@login_required
@permission_required(IMPORT_PERMISSIONS, raise_exception=True)
def unit_import_preview(request):
    data, unit_type = _pending(request)
    if data is None:
        return redirect("register:unit_import")
    if "mapping" not in data:
        return redirect("register:unit_import_map")

    with transaction.atomic():
        results = csv_io.validate_rows(
            unit_type,
            data["headers"],
            data["rows"],
            data["mapping"],
            data["default_role"],
            data["skip_existing"],
        )
        errors = [r for r in results if r.status == "error"]
        if request.method == "POST" and not errors:
            units, people = csv_io.import_rows(results)
            del request.session[SESSION_KEY]
            skipped = sum(1 for r in results if r.status == "skip")
            messages.success(
                request,
                _("Imported %(units)s units and %(people)s new people; skipped %(skipped)s.")
                % {"units": units, "people": people, "skipped": skipped},
            )
            return redirect("register:unit_list")

    context = {
        "unit_type": unit_type,
        "data": data,
        "results": results,
        "error_count": len(errors),
        "ok_count": sum(1 for r in results if r.status == "ok"),
        "skip_count": sum(1 for r in results if r.status == "skip"),
    }
    return render(request, "register/import_preview.html", context)
