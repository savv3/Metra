import datetime

from django import forms
from django.contrib.auth.models import Group
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import ROLE_CHOICES, ApiClient


def grantable_roles(user):
    """The roles ``user`` may give a client: those whose every permission the
    user has, so nobody can make a client stronger than themselves."""
    mine = user.get_all_permissions()
    roles = []
    for value, label in ROLE_CHOICES:
        group = Group.objects.filter(name=value).first()
        if group is None:
            continue
        needed = {
            f"{app_label}.{codename}"
            for app_label, codename in group.permissions.values_list(
                "content_type__app_label", "codename"
            )
        }
        if user.is_superuser or needed <= mine:
            roles.append((value, label))
    return roles


class ApiClientForm(forms.ModelForm):
    expires_on = forms.DateField(
        label=_("Expires after"),
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        help_text=_("Optional. The token stops working when this day is over."),
    )

    class Meta:
        model = ApiClient
        fields = ["name", "description", "role", "read_only"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
        help_texts = {
            "role": _(
                "The client may do what a user with this role may. Choose the narrowest "
                "role that does the job."
            )
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [("", "---"), *grantable_roles(user)]

    def clean_expires_on(self):
        day = self.cleaned_data.get("expires_on")
        if day and day < timezone.localdate():
            raise forms.ValidationError(_("Choose today or a later day."))
        return day

    def expires_at(self):
        day = self.cleaned_data.get("expires_on")
        if not day:
            return None
        midnight = datetime.datetime.combine(day + datetime.timedelta(days=1), datetime.time())
        return timezone.make_aware(midnight)
