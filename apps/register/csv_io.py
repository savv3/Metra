"""CSV import of units with one contact each, and CSV export of filtered lists.

Files are read and written in memory only; nothing is stored on disk.
"""

import csv
import datetime
import io
import re
from dataclasses import dataclass, field

from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from .custom_fields import FIELD_PREFIX, display_value
from .forms import PersonForm, UnitForm
from .models import COUNTRY_CHOICES, CustomField, Organisation, Person, Tag, Unit, UnitContact
from .unitwords import words as unit_words

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000
DELIMITERS = [";", ",", "\t"]
LANGUAGES = ["sv", "en", "fi"]


class CSVError(Exception):
    """The file cannot be read at all (as opposed to a row with errors)."""


# Reading


def read_csv(uploaded_file):
    """Return (headers, rows) from an uploaded file: UTF-8 with or without BOM,
    separated by semicolons, commas or tabs. Rows with no values are dropped."""
    raw = uploaded_file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise CSVError(_("The file is larger than 2 MB. Split it into smaller files."))
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CSVError(_("The file is not UTF-8. In Excel, save it as “CSV UTF-8”.")) from None
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=detect_delimiter(text))
    rows = [[cell.strip() for cell in row] for row in reader]
    rows = [row for row in rows if any(row)]
    if len(rows) < 2:
        raise CSVError(_("The file needs a header row and at least one row of data."))
    if len(rows) - 1 > MAX_ROWS:
        raise CSVError(_("The file has more than %(max)s rows.") % {"max": MAX_ROWS})
    return rows[0], rows[1:]


def detect_delimiter(text):
    """The separator used most in the header row; a comma when there is none."""
    header = next(iter(text.splitlines()), "")
    counts = {delimiter: header.count(delimiter) for delimiter in DELIMITERS}
    best = max(counts, key=counts.get)
    return best if counts[best] else ","


# Mapping columns to fields


@dataclass
class Target:
    """A field a CSV column can be mapped to."""

    key: str
    label: str
    required: bool = False
    aliases: set = field(default_factory=set)


def _normalise(text):
    return re.sub(r"[\s*_-]+", " ", str(text)).strip().casefold()


def _labels(model, name):
    """The field's name and its label in every language, for guessing columns."""
    names = {name}
    for language in LANGUAGES:
        with translation.override(language):
            names.add(str(model._meta.get_field(name).verbose_name))
    return {_normalise(n) for n in names}


UNIT_FIELDS = ["name", "status", "street_address", "postal_code", "city", "country"]
UNIT_FIELDS += ["start_date", "end_date", "tags", "notes"]
CONTACT_FIELDS = ["first_name", "last_name", "email", "phone"]
CONTACT_SECTION = gettext_lazy("Contact")


def build_targets(unit_type):
    targets = []
    for name in UNIT_FIELDS:
        model_field = Unit._meta.get_field(name)
        targets.append(
            Target(
                f"unit:{name}",
                str(model_field.verbose_name).capitalize(),
                required=name == "name",
                aliases=_labels(Unit, name),
            )
        )
    for definition in unit_type.custom_fields.all():
        targets.append(
            Target(
                f"custom:{definition.key}",
                definition.label,
                aliases={_normalise(definition.key), _normalise(definition.label)},
            )
        )
    for name in CONTACT_FIELDS:
        label = str(Person._meta.get_field(name).verbose_name).capitalize()
        targets.append(
            Target(f"contact:{name}", f"{CONTACT_SECTION}: {label}", aliases=_labels(Person, name))
        )
    targets.append(
        Target(
            "contact:role",
            f"{CONTACT_SECTION}: {UnitContact._meta.get_field('role').verbose_name}",
            aliases=_labels(UnitContact, "role"),
        )
    )
    return targets


def guess_mapping(targets, headers):
    """Map each target to the first column whose header matches its name or label."""
    columns = {}
    for index, header in enumerate(headers):
        columns.setdefault(_normalise(header), index)
    mapping = {}
    for target in targets:
        for alias in target.aliases:
            if alias in columns:
                mapping[target.key] = columns[alias]
                break
    return mapping


# Turning cell values into form values


def _choice_lookup(choices):
    """Match a cell against choice values and their labels in every language."""
    lookup = {}
    for value, label in choices:
        lookup[_normalise(value)] = value
        for language in LANGUAGES:
            with translation.override(language):
                lookup[_normalise(label)] = value
    return lookup


DATE_FORMATS = ["%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y"]
YES = {"ja", "yes", "x", "1", "true", "sant", "kyllä"}
NO = {"nej", "no", "0", "false", "falskt", "ei"}


def _date(value):
    for date_format in DATE_FORMATS:
        try:
            return datetime.datetime.strptime(value, date_format).date().isoformat()
        except ValueError:
            continue
    return value  # the form reports it as invalid


def _number(value):
    return value.replace(" ", "").replace(" ", "").replace(",", ".")


class RowValues:
    """Builds form data for one CSV row, collecting errors the forms cannot see."""

    def __init__(self, unit_type):
        self.statuses = _choice_lookup(Unit.Status.choices)
        self.countries = _choice_lookup(COUNTRY_CHOICES)
        self.roles = _choice_lookup(UnitContact.Role.choices)
        self.tags = {_normalise(tag.name): tag.pk for tag in Tag.objects.all()}
        self.definitions = {d.key: d for d in unit_type.custom_fields.all()}
        organisation = Organisation.current()
        self.default_country = organisation.country if organisation else "FI"

    def unit_data(self, cells, errors):
        data = {"status": Unit.Status.ACTIVE, "country": self.default_country}
        for name in UNIT_FIELDS:
            value = cells.get(f"unit:{name}", "")
            if not value:
                continue
            if name == "status":
                data[name] = self.statuses.get(_normalise(value), value)
            elif name == "country":
                data[name] = self.countries.get(_normalise(value), value)
            elif name in ("start_date", "end_date"):
                data[name] = _date(value)
            elif name == "tags":
                data[name] = self._tags(value, errors)
            else:
                data[name] = value
        for key, definition in self.definitions.items():
            value = cells.get(f"custom:{key}", "")
            if value:
                data[FIELD_PREFIX + key] = self._custom(definition, value)
        return data

    def _tags(self, value, errors):
        pks = []
        for name in filter(None, (part.strip() for part in re.split(r"[,|]", value))):
            if _normalise(name) in self.tags:
                pks.append(self.tags[_normalise(name)])
            else:
                errors.append(
                    _("Tags: “%(name)s” does not exist. Add it under Settings first.")
                    % {"name": name}
                )
        return pks

    def _custom(self, definition, value):
        match definition.field_type:
            case CustomField.FieldType.DATE:
                return _date(value)
            case CustomField.FieldType.NUMBER:
                return _number(value)
            case CustomField.FieldType.BOOLEAN:
                return "on" if _normalise(value) in YES else ""
            case CustomField.FieldType.CHOICE:
                options = {_normalise(option): option for option in definition.choice_list}
                return options.get(_normalise(value), value)
        return value

    def boolean_errors(self, cells):
        errors = []
        for key, definition in self.definitions.items():
            value = cells.get(f"custom:{key}", "")
            known = YES | NO
            if definition.field_type == CustomField.FieldType.BOOLEAN and value:
                if _normalise(value) not in known:
                    errors.append(
                        _("%(label)s: write yes or no, not “%(value)s”.")
                        % {"label": definition.label, "value": value}
                    )
        return errors

    def role(self, value, default_role):
        if not value:
            return default_role
        return self.roles.get(_normalise(value))


# Validating and importing


@dataclass
class RowResult:
    line: int
    name: str
    status: str = "ok"  # "ok", "skip" or "error"
    errors: list = field(default_factory=list)
    contact: str = ""
    unit_form: UnitForm | None = None
    person_form: PersonForm | None = None
    person: Person | None = None
    person_key: str = ""
    role: str = ""


def _form_errors(form):
    messages = []
    for name, errors in form.errors.items():
        label = form.fields[name].label if name in form.fields else ""
        for error in errors:
            messages.append(f"{label}: {error}" if label else str(error))
    return messages


def _phone_key(phone):
    return re.sub(r"\D", "", phone)


class PersonMatcher:
    """Finds people already in the register by email, or by phone when there is no email."""

    def __init__(self):
        self.by_email = {}
        self.by_phone = {}
        for person in Person.objects.order_by("pk"):
            if person.email:
                self.by_email.setdefault(person.email.casefold(), person)
            if person.phone and _phone_key(person.phone):
                self.by_phone.setdefault(_phone_key(person.phone), person)

    def key(self, contact):
        if contact.get("email"):
            return "email:" + contact["email"].casefold()
        if _phone_key(contact.get("phone", "")):
            return "phone:" + _phone_key(contact["phone"])
        return ""

    def find(self, contact):
        if contact.get("email"):
            return self.by_email.get(contact["email"].casefold())
        if contact.get("phone"):
            return self.by_phone.get(_phone_key(contact["phone"]))
        return None


def validate_rows(unit_type, headers, rows, mapping, default_role, skip_existing):
    values = RowValues(unit_type)
    matcher = PersonMatcher()
    existing = {
        name.casefold()
        for name in Unit.objects.filter(unit_type=unit_type).values_list("name", flat=True)
    }
    names_in_file = {}
    people_in_file = {}
    results = []
    for number, row in enumerate(rows, start=2):  # line 1 is the header
        cells = {key: row[index] if index < len(row) else "" for key, index in mapping.items()}
        result = RowResult(line=number, name=cells.get("unit:name", ""))
        results.append(result)
        if len(row) > len(headers) and any(row[len(headers) :]):
            result.errors.append(_("The row has more values than the header has columns."))

        folded = result.name.casefold()
        if skip_existing and folded in existing:
            result.status = "skip"
            continue
        if skip_existing and folded and folded in names_in_file:
            result.errors.append(
                _("The name is also used on line %(line)s.") % {"line": names_in_file[folded]}
            )
        names_in_file.setdefault(folded, number)

        result.errors.extend(values.boolean_errors(cells))
        result.unit_form = UnitForm(values.unit_data(cells, result.errors), unit_type=unit_type)
        if not result.unit_form.is_valid():
            result.errors.extend(_form_errors(result.unit_form))

        contact = {name: cells.get(f"contact:{name}", "") for name in CONTACT_FIELDS}
        role_cell = cells.get("contact:role", "")
        if any(contact.values()):
            _validate_contact(result, contact, role_cell, default_role, values, matcher)
            if result.person_key and not result.person:
                if result.person_key in people_in_file:
                    first = people_in_file[result.person_key]
                    result.contact = _("Same person as line %(line)s") % {"line": first}
                else:
                    people_in_file[result.person_key] = number
        elif role_cell:
            result.errors.append(_("A role is given but no contact details."))

        if result.errors:
            result.status = "error"
    return results


def _validate_contact(result, contact, role_cell, default_role, values, matcher):
    result.role = values.role(role_cell, default_role)
    if not result.role:
        result.errors.append(
            _("Role: “%(value)s” is not one of owner, billing contact or contact.")
            % {"value": role_cell}
        )
    result.person = matcher.find(contact)
    result.person_key = matcher.key(contact)
    if result.person:
        result.contact = _("Existing person: %(name)s") % {"name": result.person}
        return
    if contact["email"]:
        channel = Person.Channel.EMAIL
    elif contact["phone"]:
        channel = Person.Channel.SMS
    else:
        channel = Person.Channel.POST
    data = dict(contact, preferred_channel=channel, country=values.default_country)
    result.person_form = PersonForm(data)
    if result.person_form.is_valid():
        result.contact = _("New person: %(name)s") % {
            "name": " ".join(filter(None, [contact["first_name"], contact["last_name"]]))
        }
    else:
        result.errors.extend(
            f"{CONTACT_SECTION}: {message}" for message in _form_errors(result.person_form)
        )


def import_rows(results):
    """Save every valid row. Call inside a transaction, after checking there are no errors."""
    created_people = {}
    units = 0
    for result in results:
        if result.status != "ok":
            continue
        unit = result.unit_form.save()
        units += 1
        person = result.person
        if result.person_form is not None:
            person = created_people.get(result.person_key)
            if person is None:
                person = result.person_form.save()
                if result.person_key:
                    created_people[result.person_key] = person
        if person is not None:
            UnitContact.objects.get_or_create(unit=unit, person=person, role=result.role)
    return units, len(created_people)


# Exporting


FORMULA_START = ("=", "@", "\t", "\r")
PHONE_OR_NUMBER = re.compile(r"^[+-][\d\s().-]*$")


def _safe(value):
    """Keep spreadsheet programs from running a cell as a formula."""
    text = "" if value is None else str(value)
    if text.startswith(FORMULA_START) or (
        text.startswith(("+", "-")) and not PHONE_OR_NUMBER.match(text)
    ):
        return "'" + text
    return text


def csv_response(filename, header, rows):
    """A semicolon-separated UTF-8 file with BOM, so Excel shows å, ä and ö correctly."""
    buffer = io.StringIO()
    buffer.write("﻿")
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow([_safe(value) for value in header])
    for row in rows:
        writer.writerow([_safe(value) for value in row])
    response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "no-store"
    return response


def _date_text(value):
    return value.isoformat() if value else ""


def _custom_columns(definitions):
    """(heading, definition) pairs; labels used by several types get the type's name."""
    labels = {}
    for definition in definitions:
        labels.setdefault(definition.label, set()).add(definition.unit_type_id)
    columns = []
    for definition in definitions:
        heading = definition.label
        if len(labels[heading]) > 1:
            heading = f"{definition.unit_type}: {definition.label}"
        columns.append((heading, definition))
    return columns


def export_units(units, definitions):
    columns = _custom_columns(definitions)
    header = [
        _("Name"),
        _("Type"),
        _("Status"),
        _("Street address"),
        _("Postal code"),
        _("City"),
        _("Country"),
        _("Start date"),
        _("End date"),
        _("Tags"),
        _("Notes"),
        _("Archived"),
        *[heading for heading, _definition in columns],
        _("Contacts"),
    ]
    rows = []
    for unit in units:
        contacts = "; ".join(
            ", ".join(
                filter(
                    None, [c.person.full_name, c.get_role_display(), c.person.email, c.person.phone]
                )
            )
            for c in unit.unit_contacts.all()
        )
        rows.append(
            [
                unit.name,
                unit.unit_type.name,
                unit.get_status_display(),
                unit.street_address,
                unit.postal_code,
                unit.city,
                unit.get_country_display(),
                _date_text(unit.start_date),
                _date_text(unit.end_date),
                ", ".join(tag.name for tag in unit.tags.all()),
                unit.notes,
                _date_text(unit.archived_at and timezone.localdate(unit.archived_at)),
                *[
                    display_value(d, unit.custom_data.get(d.key))
                    if d.unit_type_id == unit.unit_type_id
                    else ""
                    for _heading, d in columns
                ],
                contacts,
            ]
        )
    return header, rows


def export_people(people, definitions):
    header = [
        _("First name"),
        _("Last name"),
        _("Email"),
        _("Phone"),
        _("Preferred channel"),
        _("Street address"),
        _("Postal code"),
        _("City"),
        _("Country"),
        _("Tags"),
        _("Notes"),
        _("Archived"),
        *[d.label for d in definitions],
        unit_words()["plural"],
    ]
    rows = []
    for person in people:
        rows.append(
            [
                person.first_name,
                person.last_name,
                person.email,
                person.phone,
                person.get_preferred_channel_display(),
                person.street_address,
                person.postal_code,
                person.city,
                person.get_country_display(),
                ", ".join(tag.name for tag in person.tags.all()),
                person.notes,
                _date_text(person.archived_at and timezone.localdate(person.archived_at)),
                *[display_value(d, person.custom_data.get(d.key)) for d in definitions],
                "; ".join(
                    f"{c.unit.name} ({c.get_role_display()})" for c in person.unit_contacts.all()
                ),
            ]
        )
    return header, rows


def log_export(request, model, objects, filters):
    """Record in the audit log who exported which records."""
    pks = [obj.pk for obj in objects]
    LogEntry.objects.create(
        content_type=ContentType.objects.get_for_model(model),
        object_pk="",
        object_repr=_("CSV export of %(count)s %(things)s")
        % {"count": len(pks), "things": model._meta.verbose_name_plural},
        action=LogEntry.Action.ACCESS,
        actor=request.user,
        additional_data={"export": "csv", "filters": filters, "ids": pks},
    )
