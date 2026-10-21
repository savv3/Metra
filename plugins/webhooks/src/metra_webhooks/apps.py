from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy


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
        api.add_notification_kind(
            api.NotificationKind(
                "webhook_failed",
                _("A webhook could not be delivered"),
                ngettext_lazy(
                    "A webhook to %(endpoint)s could not be delivered and was given up.",
                    "%(count)s webhooks to %(endpoint)s could not be delivered and were given up.",
                    "count",
                ),
                roles=["Admin"],
                permission="metra_webhooks.view_webhookdelivery",
            )
        )
