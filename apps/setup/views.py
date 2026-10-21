"""The setup wizard: one page per step, each saved on its own or skipped.
Nothing changes until a step's form is saved."""

from allauth.account.forms import default_token_generator
from allauth.account.utils import user_pk_to_url_str
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import Group
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

from apps.invoicing.models import BillingSettings
from apps.messaging.email_forms import EmailSettingsForm
from apps.messaging.registry import EMAIL, SMS, ProviderError, provider_for
from apps.messaging.views import send_test_email
from apps.register.models import CustomField, Organisation, UnitType

from . import examples
from .forms import (
    BillingSettingsForm,
    CustomFieldForm,
    InviteForm,
    LanguageForm,
    LogoForm,
    OrganisationForm,
    TestMessageForm,
    UnitTypeForm,
)
from .models import SetupState

User = get_user_model()

STEPS = [
    ("organisation", gettext_lazy("Organisation")),
    ("language", gettext_lazy("Language")),
    ("logo", gettext_lazy("Logo")),
    ("types", gettext_lazy("Units and fields")),
    ("messaging", gettext_lazy("Email and SMS")),
    ("invoicing", gettext_lazy("Invoices")),
    ("board", gettext_lazy("Invite the board")),
]
NAMES = [name for name, _label in STEPS]


def _next(name):
    index = NAMES.index(name)
    return reverse("setup:step", args=[NAMES[index + 1]]) if index + 1 < len(NAMES) else None


def _render(request, name, context):
    state = SetupState.current()
    index = NAMES.index(name)
    context |= {
        "steps": [
            {"name": n, "label": label, "saved": n in state.saved_steps, "current": n == name}
            for n, label in STEPS
        ],
        "step": name,
        "number": index + 1,
        "total": len(STEPS),
        "title": dict(STEPS)[name],
        "next_url": _next(name) or reverse("setup:done"),
        "back_url": reverse("setup:step", args=[NAMES[index - 1]]) if index else None,
    }
    return render(request, f"setup/{name}.html", context)


def _saved(request, name, stay=False, message=None):
    SetupState.current().mark_saved(name)
    messages.success(request, message or _("Saved."))
    if stay:
        return redirect("setup:step", name)
    return redirect(_next(name) or reverse("setup:done"))


@login_required
@permission_required("setup.run_setup", raise_exception=True)
def start(request):
    return redirect("setup:step", NAMES[0])


@login_required
@permission_required("setup.run_setup", raise_exception=True)
def step(request, name):
    handler = {
        "organisation": organisation_step,
        "language": language_step,
        "logo": logo_step,
        "types": types_step,
        "messaging": messaging_step,
        "invoicing": invoicing_step,
        "board": board_step,
    }.get(name)
    if handler is None:
        raise Http404
    return handler(request, name)


def organisation_step(request, name):
    form = OrganisationForm(request.POST or None, instance=Organisation.current())
    if request.method == "POST" and form.is_valid():
        form.save()
        return _saved(request, name)
    return _render(request, name, {"form": form})


def language_step(request, name):
    form = LanguageForm(request.POST or None, initial={"language": translation.get_language()})
    if request.method == "POST" and form.is_valid():
        language = form.cleaned_data["language"]
        translation.activate(language)
        response = _saved(request, name)
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            language,
            max_age=settings.LANGUAGE_COOKIE_AGE,
            samesite="Lax",
            secure=request.is_secure(),
        )
        return response
    return _render(request, name, {"form": form})


def logo_step(request, name):
    organisation = Organisation.current()
    if organisation is None:
        messages.info(request, _("Fill in the organisation first; the logo belongs to it."))
        return _render(request, name, {"form": None, "organisation": None})
    if request.method == "POST" and request.POST.get("remove") and organisation.logo:
        organisation.logo.delete(save=True)
        messages.success(request, _("The logo was removed."))
        return redirect("setup:step", name)
    form = LogoForm(request.POST or None, request.FILES or None, instance=organisation)
    if request.method == "POST" and form.is_valid():
        form.save()
        return _saved(request, name)
    return _render(request, name, {"form": form, "organisation": organisation})


def types_step(request, name):
    """Unit types and their fields, with the water association as an example."""
    type_form = UnitTypeForm(prefix="type")
    field_form = CustomFieldForm(prefix="field")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "example":
            household = examples.water_association()
            message = _("Added %(name)s with its fields and a water meter.") % {"name": household}
            return _saved(request, name, stay=True, message=message)
        if action == "type":
            type_form = UnitTypeForm(request.POST, prefix="type")
            if type_form.is_valid():
                type_form.save()
                return _saved(request, name, stay=True)
        if action == "field":
            field_form = CustomFieldForm(request.POST, prefix="field")
            if field_form.is_valid():
                field_form.save()
                return _saved(request, name, stay=True)
    context = {
        "unit_types": UnitType.objects.prefetch_related("custom_fields"),
        "person_fields": CustomField.objects.filter(target=CustomField.Target.PERSON),
        "type_form": type_form,
        "field_form": field_form,
        "has_types": UnitType.objects.exists(),
    }
    return _render(request, name, context)


def messaging_step(request, name):
    """Email settings as a form, what is set up for SMS (46elks settings are
    in the environment), and a test message for each."""
    form = EmailSettingsForm(request.POST if request.POST.get("action") == "save" else None)
    if request.method == "POST":
        if request.POST.get("action") == "save":
            if form.is_valid():
                form.save()
                return _saved(request, name, stay=True, message=_("Saved the email settings."))
        else:
            test = TestMessageForm(request.POST)
            if test.is_valid():
                channel, to = test.cleaned_data["channel"], test.cleaned_data["to"]
                if channel == "email":
                    sent = send_test_email(request, to)
                else:
                    sent = _send_test_sms(request, to)
                if sent:
                    SetupState.current().mark_saved(name)
            return redirect("setup:step", name)
    sms = provider_for(SMS)
    context = {
        "form": form,
        "email": provider_for(EMAIL),
        "sms": sms,
        "sms_label": sms.label() if sms else "",
        "sms_sender": settings.MESSAGING["sms_sender"],
        "email_to": request.user.email,
    }
    return _render(request, name, context)


def _send_test_sms(request, to):
    provider = provider_for(SMS)
    try:
        if provider is None:
            raise ProviderError(_("This channel is not set up."))
        provider.send(to, _("This is a test message from Metra. If you got it, sending works."))
    except ProviderError as error:
        messages.error(request, _("The test failed: %(error)s") % {"error": error})
        return False
    messages.success(request, _("Test sent to %(to)s.") % {"to": to})
    return True


def invoicing_step(request, name):
    form = BillingSettingsForm(request.POST or None, instance=BillingSettings.current())
    if request.method == "POST" and form.is_valid():
        form.save()
        return _saved(request, name)
    return _render(request, name, {"form": form})


def board_step(request, name):
    form = InviteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = _invite(request, form.cleaned_data)
        if user is not None:
            return _saved(request, name, stay=True)
    context = {
        "form": form,
        "users": User.objects.filter(is_active=True)
        .prefetch_related("groups")
        .order_by("first_name", "username"),
        "email_set_up": provider_for(EMAIL) is not None,
    }
    return _render(request, name, context)


def _invite(request, data):
    """Make the account and email a link to choose a password. Nothing is
    made if the email cannot be sent."""
    provider = provider_for(EMAIL)
    if provider is None:
        messages.error(
            request,
            _("Email is not set up, so no invitation can be sent. Add the person under Settings."),
        )
        return None
    group = get_object_or_404(Group, pk=data["role"])
    user = User(
        username=data["email"],
        email=data["email"],
        first_name=data["first_name"],
        last_name=data["last_name"],
        is_staff=group.name == "Admin",
    )
    user.set_unusable_password()
    user.save()
    user.groups.add(group)
    link = request.build_absolute_uri(
        reverse(
            "account_reset_password_from_key",
            kwargs={
                "uidb36": user_pk_to_url_str(user),
                "key": default_token_generator.make_token(user),
            },
        )
    )
    organisation = Organisation.current()
    values = {
        "name": user.first_name,
        "organisation": organisation.public_name if organisation else _("Metra"),
        "username": user.username,
        "link": link,
        "inviter": request.user.get_full_name() or request.user.get_username(),
    }
    subject = _("Your account for %(organisation)s") % values
    body = (
        _(
            "Hello %(name)s,\n\n%(inviter)s has made you an account for %(organisation)s "
            "in Metra. Your username is %(username)s.\n\nChoose your password here:\n%(link)s\n\n"
            "The link works for a few days."
        )
        % values
    )
    try:
        provider.send(user.email, body, subject=subject)
    except ProviderError as error:
        user.delete()
        messages.error(request, _("The invitation could not be sent: %(error)s") % {"error": error})
        return None
    messages.success(request, _("Invitation sent to %(email)s.") % {"email": user.email})
    return user


@login_required
@permission_required("setup.run_setup", raise_exception=True)
def done(request):
    state = SetupState.current()
    context = {
        "steps": [
            {"name": n, "label": label, "saved": n in state.saved_steps} for n, label in STEPS
        ],
    }
    return render(request, "setup/done.html", context)


@login_required
@permission_required("setup.run_setup", raise_exception=True)
@require_POST
def finish(request):
    SetupState.current().finish(request.user)
    messages.success(request, _("Setup is done. You can run it again from Settings."))
    return redirect("register:unit_list")
