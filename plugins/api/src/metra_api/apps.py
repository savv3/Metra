from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ApiConfig(AppConfig):
    name = "metra_api"
    verbose_name = _("API")
    default_auto_field = "django.db.models.BigAutoField"

    # Clients are systems, not people: the plugin stores their name and who
    # created them. The personal data the API serves is Metra's own.
    personal_data = []

    def ready(self):
        from apps.plugins import api

        api.add_settings_link(
            api.SettingsLink(
                _("API clients"),
                "metra_api:client_list",
                "metra_api.view_apiclient",
                _("Tokens for other systems that read or change the register."),
            )
        )
