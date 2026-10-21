from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from apps.plugins import api

from .models import AgendaItem, AgendaTemplate, Attendance, Meeting


def active_users():
    return get_user_model().objects.filter(is_active=True).order_by("username")


class UserChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, user):
        return user.get_full_name() or user.get_username()


class UserMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, user):
        return user.get_full_name() or user.get_username()


class MeetingForm(forms.ModelForm):
    starts_at = forms.DateTimeField(
        label=_("Date and time"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"],
    )
    chair = UserChoiceField(label=_("Chair"), queryset=active_users(), required=False)
    secretary = UserChoiceField(label=_("Secretary"), queryset=active_users(), required=False)
    checkers = UserMultipleChoiceField(
        label=_("Minute checkers"),
        queryset=active_users(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text=_("They approve the minutes in Metra. Everyone ticked must approve."),
    )

    class Meta:
        model = Meeting
        fields = [
            "kind",
            "title",
            "starts_at",
            "place",
            "notes",
            "votes_by_unit",
            "members_can_read",
            "chair",
            "secretary",
            "checkers",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Querysets are made per form, so new users show up.
        for name in ("chair", "secretary", "checkers"):
            self.fields[name].queryset = active_users()
        templates = list(AgendaTemplate.objects.all())
        if self.instance.pk is None and templates:
            self.fields["agenda"] = forms.ChoiceField(
                label=_("Agenda"),
                choices=[
                    (AUTO, _("The agenda template for this kind of meeting, if there is one")),
                    (EMPTY, _("An empty agenda")),
                    *[(str(t.pk), t.name) for t in templates],
                ],
                initial=AUTO,
                required=False,
                help_text=_("You can change the items afterwards."),
            )
            self.order_fields(["kind", "agenda"])

    def agenda_template(self):
        """The template chosen for a new meeting's agenda, or None."""
        choice = self.cleaned_data.get("agenda") or EMPTY
        if choice == AUTO:
            return AgendaTemplate.for_kind(self.instance.kind)
        if choice == EMPTY:
            return None
        return AgendaTemplate.objects.filter(pk=choice).first()


AUTO, EMPTY = "auto", "empty"


class AgendaTemplateForm(forms.ModelForm):
    class Meta:
        model = AgendaTemplate
        fields = ["name", "kind", "items"]
        widgets = {"items": forms.Textarea(attrs={"rows": 14})}

    def clean_kind(self):
        kind = self.cleaned_data["kind"]
        others = AgendaTemplate.objects.exclude(pk=self.instance.pk)
        if kind and others.filter(kind=kind).exists():
            raise forms.ValidationError(
                _("Another template is already used for this kind of meeting.")
            )
        return kind


class AgendaItemForm(forms.ModelForm):
    class Meta:
        model = AgendaItem
        fields = ["order", "title", "description", "minutes", "decision"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "minutes": forms.Textarea(attrs={"rows": 5}),
            "decision": forms.Textarea(attrs={"rows": 3}),
        }


class MinutesForm(forms.ModelForm):
    """The minutes and decision of one item, on the page with all items."""

    class Meta:
        model = AgendaItem
        fields = ["minutes", "decision"]
        widgets = {
            "minutes": forms.Textarea(attrs={"rows": 4}),
            "decision": forms.Textarea(attrs={"rows": 2}),
        }


MinutesFormSet = forms.modelformset_factory(AgendaItem, form=MinutesForm, extra=0)


class PersonChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, person):
        units = ", ".join(u.name for u in person.units.all() if not u.is_archived)
        return f"{person.full_name} ({units})" if units else person.full_name


class AttendanceForm(forms.ModelForm):
    person = PersonChoiceField(label=_("Person"), queryset=None)
    unit = forms.ModelChoiceField(
        label=_("Unit"),
        queryset=None,
        required=False,
        help_text=_("Empty: the person's unit, if they have only one."),
    )

    class Meta:
        model = Attendance
        fields = ["person", "unit", "votes", "proxy"]

    def __init__(self, *args, meeting, **kwargs):
        super().__init__(*args, **kwargs)
        self.meeting = meeting
        self.fields["person"].queryset = (
            api.Person.objects.active()
            .prefetch_related("units")
            .order_by("last_name", "first_name")
        )
        self.fields["unit"].queryset = api.Unit.objects.active().order_by("name")
        self.fields["votes"].required = False
        self.fields["votes"].help_text = (
            _("Empty: one vote for the first person present for a unit, none for the others.")
            if meeting.votes_by_unit
            else _("Empty: one vote.")
        )
        if not self.instance.pk:
            self.initial.pop("votes", None)
            self.fields["votes"].initial = None

    def clean(self):
        cleaned = super().clean()
        person, unit = cleaned.get("person"), cleaned.get("unit")
        if person is None:
            return cleaned
        others = self.meeting.attendances.exclude(pk=self.instance.pk)
        if others.filter(person=person).exists():
            self.add_error("person", _("This person is already on the list."))
        if unit is None:
            units = [u for u in person.units.all() if not u.is_archived]
            if len(units) == 1:
                unit = cleaned["unit"] = units[0]
        votes = cleaned.get("votes")
        if self.meeting.votes_by_unit:
            carried = others.filter(unit=unit, votes__gt=0).first() if unit else None
            if votes is None:
                votes = 1 if unit and carried is None else 0
            elif votes and unit is None:
                self.add_error("votes", _("Only units have votes at this meeting."))
            elif votes and carried is not None:
                self.add_error(
                    "votes",
                    _("%(name)s already carries the vote of %(unit)s.")
                    % {"name": carried.name, "unit": unit.name},
                )
            elif votes and votes > 1 and not cleaned.get("proxy"):
                self.add_error(
                    "votes", _("A unit has one vote. Note the proxy for any votes beyond it.")
                )
        elif votes is None:
            votes = 1
        cleaned["votes"] = votes
        return cleaned
