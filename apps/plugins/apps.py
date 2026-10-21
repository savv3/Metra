from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PluginsConfig(AppConfig):
    name = "apps.plugins"
    verbose_name = _("Add-ons")

    def ready(self):
        from . import checks, events  # noqa: F401

        events.connect()
