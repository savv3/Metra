from django import forms
from django.utils.translation import gettext_lazy as _

from . import events, service
from .models import WebhookEndpoint


class EndpointForm(forms.ModelForm):
    events = forms.MultipleChoiceField(
        label=_("Events"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text=_("The endpoint gets nothing until at least one event is ticked."),
    )

    url = forms.URLField(
        label=_("Address"),
        max_length=500,
        assume_scheme="https",
        help_text=_("Where Metra sends the events. Must start with https://."),
    )

    class Meta:
        model = WebhookEndpoint
        fields = ["url", "description", "events", "active"]
        help_texts = {
            "description": _("What the receiver is, for your own reference."),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["events"].choices = events.event_choices()

    def clean_url(self):
        url = self.cleaned_data["url"]
        try:
            service.check_scheme(url)
        except service.UnsafeURL as error:
            raise forms.ValidationError(str(error)) from error
        return url

    def clean_events(self):
        return sorted(self.cleaned_data["events"])
