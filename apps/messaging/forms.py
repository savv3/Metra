from django import forms
from django.http import QueryDict
from django.utils.translation import gettext_lazy as _

from apps.register.models import Tag, UnitType

from . import broadcast
from .models import MessageBatch

SCOPES = [
    (broadcast.EVERYONE, _("Everyone")),
    (broadcast.TAG, _("Units with a tag")),
    (broadcast.UNIT_TYPE, _("Units of a type")),
    (broadcast.FILTERED, _("The units in the filtered list")),
]
CONTACTS = [
    (broadcast.ALL_CONTACTS, _("All contacts of each unit")),
    (broadcast.MAIN_CONTACT, _("Only each unit's main contact")),
]
PLACEHOLDER_HELP = _(
    "You can use {first_name}, {name}, {unit}, {organisation} and {organisation_phone}."
)


class MessageForm(forms.Form):
    """A message staff write to many people. ``urgent`` is an alert about the service."""

    urgent = forms.BooleanField(
        label=_("Urgent alert"),
        required=False,
        help_text=_("For disruptions such as a water leak. Sent to everyone at once."),
    )
    scope = forms.ChoiceField(label=_("Send to"), choices=SCOPES, initial=broadcast.EVERYONE)
    tag = forms.ModelChoiceField(label=_("Tag"), queryset=Tag.objects.all(), required=False)
    unit_type = forms.ModelChoiceField(
        label=_("Unit type"), queryset=UnitType.objects.all(), required=False
    )
    filters = forms.CharField(required=False, widget=forms.HiddenInput)
    contacts = forms.ChoiceField(
        label=_("Who in each unit"),
        choices=CONTACTS,
        initial=broadcast.ALL_CONTACTS,
        widget=forms.RadioSelect,
    )
    channels = forms.ChoiceField(
        label=_("Send by"),
        choices=MessageBatch.Channels.choices,
        initial=MessageBatch.Channels.SMS_OR_EMAIL,
        widget=forms.RadioSelect,
    )
    body = forms.CharField(
        label=_("Message"),
        max_length=1600,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text=PLACEHOLDER_HELP,
    )
    subject = forms.CharField(
        label=_("Email subject"),
        max_length=200,
        required=False,
        help_text=_("Needed when the message goes by email."),
    )
    email_body = forms.CharField(
        label=_("Longer text for email"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text=_("Optional. Without it, the email has the same text as the SMS."),
    )

    def __init__(self, *args, urgent=False, **kwargs):
        super().__init__(*args, **kwargs)
        if urgent and not self.is_bound:
            self.initial |= {
                "urgent": True,
                "channels": MessageBatch.Channels.SMS_AND_EMAIL,
                "contacts": broadcast.ALL_CONTACTS,
            }

    def clean(self):
        cleaned = super().clean()
        scope = cleaned.get("scope")
        if scope == broadcast.TAG and not cleaned.get("tag"):
            self.add_error("tag", _("Choose a tag."))
        if scope == broadcast.UNIT_TYPE and not cleaned.get("unit_type"):
            self.add_error("unit_type", _("Choose a unit type."))
        if cleaned.get("channels") != MessageBatch.Channels.SMS and not cleaned.get("subject"):
            self.add_error("subject", _("Add a subject for the email."))
        return cleaned

    def units(self):
        data = self.cleaned_data
        value = {broadcast.TAG: data.get("tag"), broadcast.UNIT_TYPE: data.get("unit_type")}.get(
            data["scope"]
        )
        return broadcast.audience_units(
            data["scope"], getattr(value, "pk", ""), QueryDict(data.get("filters", ""))
        )

    def audience_label(self):
        data = self.cleaned_data
        label = dict(SCOPES)[data["scope"]]
        detail = data.get("tag") or data.get("unit_type")
        if data["scope"] in (broadcast.TAG, broadcast.UNIT_TYPE) and detail:
            label = f"{label}: {detail}"
        return f"{label} ({dict(CONTACTS)[data['contacts']].lower()})"
