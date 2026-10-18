from django import forms
from django.utils.translation import gettext_lazy as _

from apps.readings.forms import value_field
from apps.register.models import Person


class MemberReadingForm(forms.Form):
    def __init__(self, *args, reading_type, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["value"] = value_field(reading_type)
        self.fields["value"].widget.attrs["aria-describedby"] = "value-help"


class MemberContactForm(forms.ModelForm):
    """The contact details members may correct themselves."""

    class Meta:
        model = Person
        fields = ["email", "phone", "street_address", "postal_code", "city"]
        widgets = {
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"type": "tel", "autocomplete": "tel"}),
            "street_address": forms.TextInput(attrs={"autocomplete": "street-address"}),
            "postal_code": forms.TextInput(attrs={"autocomplete": "postal-code"}),
            "city": forms.TextInput(attrs={"autocomplete": "address-level2"}),
        }

    def clean(self):
        cleaned = super().clean()
        channel = self.instance.preferred_channel
        if channel == Person.Channel.EMAIL and not cleaned.get("email"):
            self.add_error("email", _("We send you messages by email, so it cannot be empty."))
        if channel == Person.Channel.SMS and not cleaned.get("phone"):
            self.add_error("phone", _("We send you messages by SMS, so it cannot be empty."))
        return cleaned
