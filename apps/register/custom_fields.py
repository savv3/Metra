"""Turn admin-defined CustomField rows into form fields and JSON values."""

import datetime
from decimal import Decimal

from django import forms

from .models import CustomField

FIELD_PREFIX = "custom__"


def form_field_for(definition):
    common = {
        "label": definition.label,
        "required": definition.required,
        "help_text": definition.help_text,
    }
    match definition.field_type:
        case CustomField.FieldType.NUMBER:
            return forms.DecimalField(**common)
        case CustomField.FieldType.DATE:
            return forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), **common)
        case CustomField.FieldType.CHOICE:
            options = [("", "---")] + [(c, c) for c in definition.choice_list]
            return forms.ChoiceField(choices=options, **common)
        case CustomField.FieldType.BOOLEAN:
            # An unticked box is a valid answer, so a yes/no field is never required.
            common["required"] = False
            return forms.BooleanField(**common)
        case _:
            return forms.CharField(max_length=500, **common)


def to_json(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime.date):
        return value.isoformat()
    return value


def from_json(definition, value):
    if value in (None, ""):
        return None
    if definition.field_type == CustomField.FieldType.DATE:
        return datetime.date.fromisoformat(value)
    if definition.field_type == CustomField.FieldType.NUMBER:
        return Decimal(value)
    return value


def display_value(definition, value):
    """A value as shown on detail pages and in CSV exports."""
    if value in (None, ""):
        return ""
    if definition.field_type == CustomField.FieldType.BOOLEAN:
        from django.utils.translation import gettext

        return gettext("Yes") if value else gettext("No")
    return str(value)


class CustomFieldsFormMixin:
    """Adds one form field per definition and stores the answers in
    ``instance.custom_data``. Values for fields that no longer exist are kept,
    so deleting a field definition never silently destroys data."""

    def setup_custom_fields(self, definitions):
        self.custom_definitions = list(definitions)
        stored = self.instance.custom_data or {}
        for definition in self.custom_definitions:
            name = FIELD_PREFIX + definition.key
            self.fields[name] = form_field_for(definition)
            self.initial[name] = from_json(definition, stored.get(definition.key))

    def custom_field_names(self):
        return [FIELD_PREFIX + d.key for d in self.custom_definitions]

    def apply_custom_fields(self):
        data = dict(self.instance.custom_data or {})
        for definition in self.custom_definitions:
            value = self.cleaned_data.get(FIELD_PREFIX + definition.key)
            if value in (None, ""):
                data.pop(definition.key, None)
            else:
                data[definition.key] = to_json(value)
        self.instance.custom_data = data


def custom_values(definitions, custom_data):
    """(label, display value) pairs for a detail page, in definition order."""
    custom_data = custom_data or {}
    return [(d.label, display_value(d, custom_data.get(d.key))) for d in definitions]
