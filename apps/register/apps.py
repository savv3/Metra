from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class RegisterConfig(AppConfig):
    name = "apps.register"
    verbose_name = _("Register")
