from django import forms
from django.http import QueryDict
from django.utils.translation import gettext_lazy as _

from apps.register.models import Tag, UnitType

from . import broadcast
from .models import PLACEHOLDER, MessageBatch, MessageTemplate, organisation_placeholders

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
    "You can use {first_name}, {name}, {unit}, {organisation}, {organisation_phone}, "
    "{organisation_email}, {organisation_website} and {emergency_phone}."
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

    notice = forms.BooleanField(
        label=_("Also show as a notice on the public page"),
        required=False,
        help_text=_("Anyone can see it there and on members' pages, so no personal details."),
    )
    notice_text = forms.CharField(
        label=_("Notice text"),
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text=_("Empty: the message text."),
    )
    notice_until = forms.DateTimeField(
        label=_("Show the notice until"),
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"],
        help_text=_("Empty: until you remove it."),
    )

    def __init__(self, *args, urgent=False, can_publish_notice=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not can_publish_notice:
            for name in ("notice", "notice_text", "notice_until"):
                del self.fields[name]
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
        if cleaned.get("notice") and not cleaned.get("notice_text"):
            body = cleaned.get("body", "")
            text = MessageTemplate.fill(body, organisation_placeholders())
            if PLACEHOLDER.search(text):
                # {first_name} and the like have no value on a public page.
                self.add_error("notice_text", _("Write the notice without personal placeholders."))
            else:
                cleaned["notice_text"] = text
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


class NewsletterForm(forms.Form):
    subject = forms.CharField(label=_("Subject"), max_length=200)
    body = forms.CharField(
        label=_("Text"),
        widget=forms.Textarea(attrs={"rows": 14}),
        help_text=_(
            "Plain text. You can use {first_name}, {name} and {organisation}. "
            "An unsubscribe link is added at the end of every email."
        ),
    )


class ConsentForm(forms.Form):
    """Staff record a yes or no given on paper, by phone or in person."""

    subscribed = forms.TypedChoiceField(
        label=_("Newsletter"),
        choices=[("1", _("Wants the newsletter")), ("0", _("Does not want it"))],
        coerce=lambda value: value == "1",
        widget=forms.RadioSelect,
    )
    note = forms.CharField(
        label=_("How it was given"),
        max_length=200,
        required=False,
        help_text=_("For example: signed form at the annual meeting."),
    )
