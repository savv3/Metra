from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class WebhooksConfig(AppConfig):
    name = "metra_webhooks"
    verbose_name = _("Webhooks")
    default_auto_field = "django.db.models.BigAutoField"

    # Payloads carry ids and non-personal facts only, and endpoints are
    # addresses of systems, not of people.
    personal_data = []
    # The plugin API versions (apps.plugins.api.API_VERSION) this plugin works with.
    metra_api = [1]

    def ready(self):
        from apps.plugins import api

        from . import events

        events.register_builtin()
        events.connect_all()
        api.add_settings_link(
            api.SettingsLink(
                _("Webhooks"),
                "metra_webhooks:endpoint_list",
                "metra_webhooks.view_webhookendpoint",
                _("Tell outside systems when something changes in Metra."),
            )
        )
