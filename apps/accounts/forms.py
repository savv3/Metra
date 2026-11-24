from allauth.core import context
from allauth.mfa.totp.forms import ActivateTOTPForm as BaseActivateTOTPForm
from allauth.mfa.totp.internal.auth import SECRET_SESSION_KEY
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _

from .roles import role_label


class ActivateTOTPForm(BaseActivateTOTPForm):
    """allauth's form, but the secret stays the same while the setup page is
    reloaded. allauth makes a new secret on every page load, so any second
    load (a reload, another tab, the browser fetching an icon that is
    redirected to this page) silently replaced the secret the user had just
    scanned, and every code was then "incorrect"."""

    def __init__(self, *args, **kwargs):
        kept = context.request.session.get(SECRET_SESSION_KEY)
        super().__init__(*args, **kwargs)
        if kept and not self.is_bound:
            context.request.session[SECRET_SESSION_KEY] = self.secret = kept


class InviteUserForm(forms.ModelForm):
    """Adding a user in the admin: name, email and role, no password. The
    user is emailed a link to choose their own (see ``invites``)."""

    email = forms.EmailField(label=_("Email"), help_text=_("Also their username."))
    role = forms.ModelChoiceField(label=_("Role"), queryset=Group.objects.order_by("name"))

    class Meta:
        model = get_user_model()
        fields = ["first_name", "last_name", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["role"].label_from_instance = role_label

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if get_user_model().objects.filter(username__iexact=email).exists():
            raise forms.ValidationError(_("Someone already has this email as their username."))
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email
        user.is_staff = self.cleaned_data["role"].name == "Admin"
        user.set_unusable_password()
        if commit:
            user.save()
            self.save_m2m()
        return user

    def _save_m2m(self):
        # Also what the admin's save_related calls, after saving the user.
        super()._save_m2m()
        self.instance.groups.add(self.cleaned_data["role"])
