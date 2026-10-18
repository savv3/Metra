from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PluginsConfig(AppConfig):
    name = "apps.plugins"
    verbose_name = _("Plugins")

    def ready(self):
        from . import checks  # noqa: F401
