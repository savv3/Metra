from dataclasses import dataclass

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.messaging.registry import EMAIL
from config.plugins import BUNDLED, available

from . import state
from .models import PluginState
from .plugin_settings import PluginSettings, Setting, definitions


@dataclass
class Installed:
    name: str
    label: str
    description: str
    version: str
    enabled: bool
    bundled: bool
    has_settings: bool


def _config(name):
    from django.apps import apps

    package = settings.PLUGIN_APPS[name].split(".")[0]
    return next(c for c in apps.get_app_configs() if c.name.split(".")[0] == package)


def installed():
    """The installed plugins, in load order, as the Plugins page lists them."""
    found = available()
    result = []
    for name in settings.PLUGIN_APPS:
        config = _config(name)
        dist = getattr(found.get(name), "dist", None)
        metadata = dist.metadata if dist is not None else {}
        result.append(
            Installed(
                name=name,
                label=str(config.verbose_name),
                description=str(getattr(config, "description", "") or metadata.get("Summary", "")),
                version=dist.version if dist is not None else "",
                enabled=state.is_enabled(name),
                bundled=name in BUNDLED,
                has_settings=bool(definitions(name)),
            )
        )
    return result


@login_required
@permission_required("plugins.change_pluginstate", raise_exception=True)
def plugin_list(request):
    return render(request, "plugins/plugin_list.html", {"plugins": installed()})


@login_required
@permission_required("plugins.change_pluginstate", raise_exception=True)
@require_POST
def plugin_toggle(request, name):
    if name not in settings.PLUGIN_APPS:
        raise Http404
    enabled = request.POST.get("enabled") == "1"
    plugin, created = PluginState.objects.get_or_create(name=name)
    if plugin.enabled != enabled or created:
        plugin.enabled = enabled
        plugin.changed_at = timezone.now()
        plugin.changed_by = request.user
        plugin.save()
    state.forget()
    label = _config(name).verbose_name
    if enabled:
        messages.success(request, _("%(plugin)s is on.") % {"plugin": label})
    else:
        messages.success(request, _("%(plugin)s is off. Its data is kept.") % {"plugin": label})
    return redirect("plugins:list")


class SettingsForm(forms.Form):
    def __init__(self, *args, values, **kwargs):
        super().__init__(*args, **kwargs)
        self.values = values
        for setting in values.fields.values():
            locked = setting.from_env is not None
            self.fields[setting.key] = self._field(setting, locked)
            if setting.kind == Setting.SECRET and values.is_saved(setting.key) and not locked:
                self.fields[f"{setting.key}__clear"] = forms.BooleanField(
                    label=_("Remove the saved %(setting)s") % {"setting": setting.label},
                    required=False,
                )

    def _field(self, setting, locked):
        help_text = str(setting.help)
        if locked:
            help_text = " ".join(
                part
                for part in [
                    help_text,
                    _("Set in the server environment (%(variable)s), so it cannot be changed here.")
                    % {"variable": setting.env},
                ]
                if part
            )
        options = {
            "label": setting.label,
            "help_text": help_text,
            "disabled": locked,
            "required": setting.required and not locked,
        }
        if setting.kind == Setting.BOOL:
            options["required"] = False
            field = forms.BooleanField(**options)
        elif setting.kind == Setting.NUMBER:
            field = forms.IntegerField(**options)
        elif setting.kind == Setting.CHOICE:
            field = forms.ChoiceField(choices=setting.choices, **options)
        elif setting.kind == Setting.SECRET:
            saved = self.values.is_saved(setting.key)
            if saved and not locked:
                options["required"] = False
                note = (
                    _("The saved value cannot be read with this server's key; enter it again.")
                    if self.values.unreadable(setting.key)
                    else _("A value is saved. Leave this empty to keep it.")
                )
                options["help_text"] = " ".join(p for p in [options["help_text"], note] if p)
            field = forms.CharField(
                widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}), **options
            )
        else:
            field = forms.CharField(**options)
        if setting.kind != Setting.SECRET:
            value = setting.from_env if locked else self.values.get(setting.key)
            field.initial = value
        return field

    def save(self, user):
        for setting in self.values.fields.values():
            if setting.from_env is not None:
                continue
            value = self.cleaned_data.get(setting.key)
            if setting.kind == Setting.SECRET:
                if self.cleaned_data.get(f"{setting.key}__clear"):
                    self.values.save(setting.key, "", user)
                elif value:
                    self.values.save(setting.key, value, user)
                continue
            self.values.save(setting.key, value, user)


@login_required
@permission_required("plugins.change_pluginsetting", raise_exception=True)
def plugin_settings(request, name):
    if name not in settings.PLUGIN_APPS or not definitions(name):
        raise Http404
    providers = _providers(name)
    if request.method == "POST" and request.POST.get("action") == "test":
        _send_test(request, name, providers)
        return redirect("plugins:settings", name=name)
    values = PluginSettings(name)
    form = SettingsForm(request.POST or None, values=values)
    if request.method == "POST" and form.is_valid():
        form.save(request.user)
        messages.success(request, _("Saved the settings."))
        return redirect("plugins:settings", name=name)
    return render(
        request,
        "plugins/plugin_settings.html",
        {
            "form": form,
            "plugin": next(p for p in installed() if p.name == name),
            "tests": [
                {
                    "channel": provider_class.channel,
                    "to": request.user.email if provider_class.channel == EMAIL else "",
                }
                for provider_class in providers.values()
            ],
        },
    )


def _providers(name):
    """The SMS and email providers a plugin adds, by channel, for its test messages."""
    from apps.messaging.registry import registry

    return {provider_class.channel: provider_class for provider_class in registry.of_plugin(name)}


def _send_test(request, name, providers):
    """A test message through the plugin's own provider, whichever one the
    installation sends with, so a new set of credentials can be tried."""
    from apps.messaging.views import send_test

    channel = request.POST.get("channel")
    if channel not in providers:
        raise Http404
    if not state.is_enabled(name):
        messages.error(request, _("Turn the add-on on to send a test."))
        return
    send_test(request, providers[channel](), channel, request.POST.get("to", "").strip())
