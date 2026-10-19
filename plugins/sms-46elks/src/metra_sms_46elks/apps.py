from django.apps import AppConfig


class FortySixElksConfig(AppConfig):
    name = "metra_sms_46elks"
    label = "metra_sms_46elks"
    verbose_name = "46elks SMS"
    default_auto_field = "django.db.models.BigAutoField"

    # Messages and their delivery status are stored by Metra, not here.
    personal_data = []
    # The plugin API versions (apps.plugins.api.API_VERSION) this plugin works with.
    metra_api = [1]

    def ready(self):
        from apps.plugins import api

        from .providers import FortySixElks

        api.add_messaging_provider(FortySixElks)
