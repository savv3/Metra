from django import forms
from django.utils.translation import gettext_lazy as _

from .custom_fields import CustomFieldsFormMixin
from .models import CustomField, Person, Unit, UnitContact

DATE_WIDGET = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class UnitForm(CustomFieldsFormMixin, forms.ModelForm):
    class Meta:
        model = Unit
        fields = [
            "name",
            "status",
            "street_address",
            "postal_code",
            "city",
            "country",
            "start_date",
            "end_date",
            "tags",
            "notes",
        ]
        widgets = {
            "start_date": DATE_WIDGET,
            "end_date": DATE_WIDGET,
            "tags": forms.CheckboxSelectMultiple,
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, unit_type, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.unit_type = unit_type
        self.setup_custom_fields(unit_type.custom_fields.all())

    def save(self, commit=True):
        self.apply_custom_fields()
        return super().save(commit)


class PersonForm(CustomFieldsFormMixin, forms.ModelForm):
    class Meta:
        model = Person
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "preferred_channel",
            "street_address",
            "postal_code",
            "city",
            "country",
            "tags",
            "notes",
        ]
        widgets = {
            "tags": forms.CheckboxSelectMultiple,
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_custom_fields(CustomField.objects.filter(target=CustomField.Target.PERSON))

    def clean(self):
        cleaned = super().clean()
        channel = cleaned.get("preferred_channel")
        if channel == Person.Channel.EMAIL and not cleaned.get("email"):
            self.add_error("email", _("Add an email address, or choose another channel."))
        if channel == Person.Channel.SMS and not cleaned.get("phone"):
            self.add_error("phone", _("Add a phone number, or choose another channel."))
        return cleaned

    def save(self, commit=True):
        self.apply_custom_fields()
        return super().save(commit)


class UnitContactForm(forms.ModelForm):
    """Links an existing person to a unit."""

    class Meta:
        model = UnitContact
        fields = ["person", "role"]

    def __init__(self, *args, unit, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.unit = unit
        self.fields["person"].queryset = Person.objects.active()

    def validate_unique(self):
        # The unit is set on the instance, not in the form, so check it here.
        try:
            self.instance.validate_constraints()
        except forms.ValidationError:
            self.add_error(None, _("This person already has that role on this unit."))
