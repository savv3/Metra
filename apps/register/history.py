"""Audit history shown on unit and person pages, built on django-auditlog."""

from decimal import Decimal, InvalidOperation

from auditlog.models import LogEntry
from auditlog.signals import accessed
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist
from django.db.models import DecimalField
from django.utils.translation import gettext as _

from .models import UnitContact

CHANGES_SHOWN = 50
VIEWS_SHOWN = 20


def log_view(obj):
    """Record that the logged-in user opened this record's page."""
    accessed.send(sender=obj.__class__, instance=obj)


def history(obj, contact_key):
    """Recent changes and views of a unit or person, including its contact links.

    ``contact_key`` is "unit_id" or "person_id": the contact links are found
    through the ids each UnitContact entry stores in ``additional_data``.
    """
    contact_type = ContentType.objects.get_for_model(UnitContact)
    entries = (
        LogEntry.objects.get_for_object(obj)
        | LogEntry.objects.filter(
            content_type=contact_type, **{f"additional_data__{contact_key}": obj.pk}
        )
    ).select_related("actor", "content_type")
    changes = entries.exclude(action=LogEntry.Action.ACCESS)[:CHANGES_SHOWN]
    views = entries.filter(action=LogEntry.Action.ACCESS)[:VIEWS_SHOWN]
    return {
        "changes": [_describe(entry, contact_type) for entry in changes],
        "views": views,
    }


def object_history(obj):
    """Recent changes and views of one record, e.g. a reading."""
    contact_type = ContentType.objects.get_for_model(UnitContact)
    entries = LogEntry.objects.get_for_object(obj).select_related("actor", "content_type")
    changes = entries.exclude(action=LogEntry.Action.ACCESS)[:CHANGES_SHOWN]
    return {
        "changes": [_describe(entry, contact_type) for entry in changes],
        "views": entries.filter(action=LogEntry.Action.ACCESS)[:VIEWS_SHOWN],
    }


def _describe(entry, contact_type):
    actions = {
        LogEntry.Action.CREATE: _("Created"),
        LogEntry.Action.UPDATE: _("Changed"),
        LogEntry.Action.DELETE: _("Deleted"),
    }
    action = actions.get(entry.action, "")
    if entry.content_type_id == contact_type.pk:
        actions = {
            LogEntry.Action.CREATE: _("Contact added"),
            LogEntry.Action.DELETE: _("Contact removed"),
        }
        return {
            "entry": entry,
            "action": actions.get(entry.action, action),
            "summary": entry.object_repr,
            "fields": [],
        }
    return {"entry": entry, "action": action, "summary": "", "fields": _fields(entry)}


def _fields(entry):
    """(label, old, new) for every changed field; old or new is None when absent."""
    model = entry.content_type.model_class()
    rows = []
    for name, values in entry.changes_dict.items():
        try:
            field = model._meta.get_field(name)
        except FieldDoesNotExist:
            label = name
            field = None
        else:
            if field.auto_created or field.primary_key:
                continue  # ids and reverse relations say nothing to a reader
            label = field.verbose_name
        if isinstance(values, dict) and values.get("type") == "m2m":
            names = ", ".join(values.get("objects", []))
            if values.get("operation") == "add":
                rows.append((label, None, _("added %(names)s") % {"names": names}))
            else:
                rows.append((label, None, _("removed %(names)s") % {"names": names}))
            continue
        old, new = (_display(field, value) for value in values)
        if entry.action == LogEntry.Action.CREATE:
            if new == "–":
                continue  # a new record's empty fields are not worth listing
            old = None
        elif entry.action == LogEntry.Action.DELETE:
            new = None
        rows.append((label, old, new))
    return rows


def _display(field, value):
    if value is None or value == "None":
        return "–"
    choices = dict(field.choices) if field is not None and field.choices else None
    if choices and value in choices:
        return str(choices[value])
    if value in ("", {}, []):
        return "–"
    if isinstance(field, DecimalField):
        try:
            # The database keeps trailing zeros (10.000); show 10.
            return format(Decimal(str(value)).normalize(), "f")
        except InvalidOperation:
            return str(value)
    if isinstance(value, dict):
        # Custom field values: show each key so a single changed field is easy to spot.
        return ", ".join(f"{key}: {item}" for key, item in value.items())
    return str(value)
