from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ReadingsConfig(AppConfig):
    name = "apps.readings"
    verbose_name = _("Readings")
