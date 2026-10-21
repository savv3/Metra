"""Plugins' own settings, edited on a page Metra makes for each plugin.

A plugin lists its settings on its AppConfig:

    metra_settings = [
        api.Setting("api_user", _("API user"), env="METRA_ELKS_API_USER"),
        api.Setting("api_password", _("API password"), kind=api.Setting.SECRET),
        api.Setting("region", _("Region"), kind=api.Setting.CHOICE,
                    choices=[("eu", "EU"), ("us", "US")], default="eu"),
    ]

and reads them with ``api.plugin_settings("46elks").get("api_user")``. A
value set in the server environment (``env``) wins over the page and shows
there as locked. Secrets are stored encrypted and never shown again.
"""

import os
from dataclasses import dataclass, field

from django.apps import apps
from django.conf import settings as django_settings
from django.utils import timezone

from . import secrets


@dataclass
class Setting:
    TEXT = "text"
    NUMBER = "number"
    CHOICE = "choice"
    BOOL = "bool"
    SECRET = "secret"
    KINDS = (TEXT, NUMBER, CHOICE, BOOL, SECRET)

    key: str
    label: str
    kind: str = TEXT
    help: str = ""
    default: object = None
    choices: list = field(default_factory=list)
    # An environment variable that wins over the saved value when it is set.
    env: str = ""
    required: bool = False

    def __post_init__(self):
        if self.kind not in self.KINDS:
            raise ValueError(f"Unknown setting kind {self.kind!r}; use one of {self.KINDS}")

    @property
    def from_env(self):
        """The value from the environment, or None when it is not set there."""
        if self.env and os.environ.get(self.env, "") != "":
            return self.convert(os.environ[self.env])
        return None

    def convert(self, text):
        """A stored or environment text as the setting's type."""
        if self.kind == self.BOOL:
            return str(text).strip().lower() in {"1", "true", "yes", "on"}
        if self.kind == self.NUMBER:
            try:
                return int(text)
            except (TypeError, ValueError):
                return self.default
        return text

    def as_text(self, value):
        if self.kind == self.BOOL:
            return "1" if value else ""
        return "" if value is None else str(value)


def definitions(name):
    """The settings a plugin declares, or []."""
    entry = django_settings.PLUGIN_APPS.get(name)
    if entry is None:
        return []
    package = entry.split(".")[0]
    for config in apps.get_app_configs():
        if config.name.split(".")[0] == package:
            return list(getattr(config, "metra_settings", []))
    return []


class PluginSettings:
    """A plugin's settings: the environment's value, else the saved one, else the default."""

    def __init__(self, name):
        self.name = name
        self.fields = {setting.key: setting for setting in definitions(name)}

    def _stored(self):
        from .models import PluginSetting

        return dict(PluginSetting.objects.filter(plugin=self.name).values_list("key", "value"))

    def get(self, key, default=None):
        setting = self.fields[key]
        if (value := setting.from_env) is not None:
            return value
        stored = self._stored().get(key)
        if stored is None or stored == "":
            return setting.default if default is None else default
        if setting.kind == Setting.SECRET:
            try:
                return secrets.decrypt(stored)
            except secrets.SecretUnreadable:
                return setting.default if default is None else default
        return setting.convert(stored)

    def is_saved(self, key):
        return bool(self._stored().get(key))

    def unreadable(self, key):
        """A saved secret that this server's key cannot read."""
        stored = self._stored().get(key)
        if not stored or self.fields[key].kind != Setting.SECRET:
            return False
        try:
            secrets.decrypt(stored)
        except secrets.SecretUnreadable:
            return True
        return False

    def save(self, key, value, user=None):
        """Save a value from the settings page; a secret is encrypted first."""
        from .models import PluginSetting

        setting = self.fields[key]
        text = setting.as_text(value)
        if setting.kind == Setting.SECRET and text:
            text = secrets.encrypt(text)
        stored = PluginSetting.objects.filter(plugin=self.name, key=key).first()
        if stored is None:
            if text == "":
                return
            stored = PluginSetting(plugin=self.name, key=key)
        elif stored.value == text:
            return
        stored.value = text
        stored.changed_at = timezone.now()
        stored.changed_by = user
        stored.save()
