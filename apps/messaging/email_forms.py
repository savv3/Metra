from django import forms
from django.conf import settings
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from apps.plugins import secrets

from . import email_config
from .email_config import CONSOLE, DJANGO, ENVIRONMENT, NONE, SMTP
from .models import EmailSettings
from .registry import EMAIL, registry


def provider_choices():
    """What email can go through: none, SMTP, the console in development, and
    the email providers of add-ons that are on."""
    choices = [(NONE, _("Not set up")), (SMTP, _("SMTP (your own mail server or account)"))]
    if settings.DEBUG:
        choices.append((CONSOLE, _("The server log (development)")))
    for name in registry.names(EMAIL):
        if name != DJANGO:
            choices.append((name, registry.get(EMAIL, name).label()))
    return choices


class EmailSettingsForm(forms.Form):
    """The email settings. A field set in the server environment is shown
    with its value, locked."""

    provider = forms.ChoiceField(label=gettext_lazy("Send email through"))
    host = forms.CharField(
        label=gettext_lazy("Mail server"),
        required=False,
        help_text=gettext_lazy("For example smtp.example.fi."),
    )
    port = forms.IntegerField(label=gettext_lazy("Port"), min_value=1, max_value=65535)
    security = forms.ChoiceField(
        label=gettext_lazy("Encryption"), choices=EmailSettings.Security.choices
    )
    user = forms.CharField(label=gettext_lazy("User name"), required=False)
    password = forms.CharField(
        label=gettext_lazy("Password"),
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    clear_password = forms.BooleanField(
        label=gettext_lazy("Remove the saved password"), required=False
    )
    from_email = forms.EmailField(
        label=gettext_lazy("From address"),
        required=False,
        help_text=gettext_lazy("The address members see the email come from."),
    )
    reply_to = forms.EmailField(
        label=gettext_lazy("Reply-To address"),
        required=False,
        help_text=gettext_lazy("Where replies go, if not to the from address."),
    )

    SMTP_FIELDS = ("host", "port", "security", "user", "password")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = email_config.current()
        self.saved = EmailSettings.current()
        self.fields["provider"].choices = provider_choices()
        config = self.config
        self.initial = {
            "provider": config.choice,
            "host": config.host,
            "port": config.port,
            "security": config.security,
            "user": config.user,
            "from_email": config.from_email if config.from_email != "register@localhost" else "",
            "reply_to": config.reply_to,
        }
        if config.choice not in dict(self.fields["provider"].choices):
            # An add-on that was chosen is off now.
            self.fields["provider"].choices.append((config.choice, config.choice))
        password_saved = bool(self.saved and self.saved.password)
        if password_saved:
            note = (
                _("The saved password cannot be read with this server's key; enter it again.")
                if config.password_unreadable
                else _("A password is saved. Leave this empty to keep it.")
            )
            self.fields["password"].help_text = note
        if not password_saved or "password" in config.locked:
            del self.fields["clear_password"]
        for name in config.locked:
            if name in self.fields:
                self._lock(name)

    def _lock(self, name):
        field = self.fields[name]
        field.disabled = True
        field.required = False
        variable = ENVIRONMENT.get(name) or {
            "provider": "METRA_EMAIL_BACKEND / METRA_EMAIL_HOST",
            "security": "METRA_EMAIL_USE_TLS / METRA_EMAIL_USE_SSL",
        }.get(name, "")
        field.help_text = _(
            "Set in the server environment (%(variable)s), so it cannot be changed here."
        ) % {"variable": variable}
        if name == "password":
            field.widget.attrs["placeholder"] = "••••••••"

    def clean(self):
        cleaned = super().clean()
        provider = cleaned.get("provider") or self.config.choice
        if provider == SMTP and not (cleaned.get("host") or self.config.host):
            self.add_error("host", _("Enter the mail server to send through SMTP."))
        if provider != NONE and not (
            cleaned.get("from_email") or "from_email" in self.config.locked
        ):
            self.add_error("from_email", _("Enter the address email is sent from."))
        return cleaned

    def save(self):
        row = self.saved or EmailSettings()
        data = self.cleaned_data
        for name in ("provider", "host", "port", "security", "user", "from_email", "reply_to"):
            if name not in self.config.locked and name in data:
                value = data[name]
                setattr(row, name, NONE if name == "provider" and not value else value)
        if "password" not in self.config.locked:
            if data.get("clear_password"):
                row.password = ""
            elif data.get("password"):
                row.password = secrets.encrypt(data["password"])
        row.save()
        return row
