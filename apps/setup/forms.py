from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils.text import capfirst, slugify
from django.utils.translation import gettext_lazy as _

from apps.accounts.roles import role_label
from apps.invoicing.models import BillingSettings
from apps.register.models import CustomField, Organisation, UnitType

User = get_user_model()


class OrganisationForm(forms.ModelForm):
    website = forms.URLField(
        label=capfirst(Organisation._meta.get_field("website").verbose_name),
        required=False,
        assume_scheme="https",
    )

    class Meta:
        model = Organisation
        fields = [
            "name",
            "display_name",
            "business_id",
            "vat_number",
            "street_address",
            "postal_code",
            "city",
            "country",
            "email",
            "phone",
            "emergency_phone",
            "website",
            "opening_hours",
            "description",
            "public_page",
        ]
        widgets = {
            "opening_hours": forms.Textarea(attrs={"rows": 2}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class LanguageForm(forms.Form):
    language = forms.ChoiceField(
        label=_("Your language"),
        choices=settings.LANGUAGES,
        widget=forms.RadioSelect,
        help_text=_(
            "Everyone picks their own language in the menu, and members on their own pages."
        ),
    )


class LogoForm(forms.ModelForm):
    class Meta:
        model = Organisation
        fields = ["logo"]
        widgets = {"logo": forms.FileInput(attrs={"accept": ".png,.jpg,.jpeg,.webp"})}


class UnitTypeForm(forms.ModelForm):
    class Meta:
        model = UnitType
        fields = ["name", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}


class CustomFieldForm(forms.ModelForm):
    """A field on units of one type, or on every person. The key is made from
    the label."""

    PERSON = "person"

    applies_to = forms.ChoiceField(label=_("Applies to"))

    class Meta:
        model = CustomField
        fields = ["label", "field_type", "choices", "required", "help_text"]
        widgets = {"choices": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["applies_to"].choices = [
            *[(str(t.pk), t.name) for t in UnitType.objects.all()],
            (self.PERSON, _("Every person")),
        ]
        self.order_fields(["applies_to", "label", "field_type", "choices", "required"])

    def clean(self):
        cleaned = super().clean()
        applies_to = cleaned.get("applies_to")
        if applies_to == self.PERSON:
            self.instance.target = CustomField.Target.PERSON
            self.instance.unit_type = None
        elif applies_to:
            self.instance.target = CustomField.Target.UNIT
            self.instance.unit_type = UnitType.objects.filter(pk=applies_to).first()
        self.instance.key = slugify(cleaned.get("label", "")).replace("-", "_")[:50] or "field"
        return cleaned

    def validate_unique(self):
        super().validate_unique()
        same = CustomField.objects.filter(target=self.instance.target, key=self.instance.key)
        if self.instance.target == CustomField.Target.UNIT:
            same = same.filter(unit_type=self.instance.unit_type)
        if same.exists():
            self.add_error("label", _("There is already a field with this name."))


class BillingSettingsForm(forms.ModelForm):
    class Meta:
        model = BillingSettings
        fields = [
            "vat_registered",
            "vat_exemption_text",
            "default_vat_rate",
            "iban",
            "bic",
            "payment_terms_days",
            "reference_type",
            "number_prefix",
            "next_number",
            "late_interest_text",
            "footer",
            "reminder_fee",
            "reminder_days",
        ]
        widgets = {"footer": forms.Textarea(attrs={"rows": 2})}


def role_choices():
    return [(group.pk, role_label(group)) for group in Group.objects.order_by("name")]


class InviteForm(forms.Form):
    first_name = forms.CharField(label=_("First name"), max_length=150)
    last_name = forms.CharField(label=_("Last name"), max_length=150, required=False)
    email = forms.EmailField(label=_("Email"))
    role = forms.TypedChoiceField(label=_("Role"), coerce=int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = role_choices()

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError(_("Someone already has this email as their username."))
        return email


class TestMessageForm(forms.Form):
    channel = forms.ChoiceField(choices=[("email", "email"), ("sms", "sms")])
    to = forms.CharField(label=_("Send a test to"), max_length=200)
