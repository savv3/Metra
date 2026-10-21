from django.apps import AppConfig
from django.conf import settings
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

from apps.plugins.api import Setting


class MailgunConfig(AppConfig):
    name = "metra_email_mailgun"
    label = "metra_email_mailgun"
    verbose_name = "Mailgun"
    default_auto_field = "django.db.models.BigAutoField"

    # Messages, their status and bounced addresses are stored by Metra, not here.
    personal_data = []
    # The plugin API versions (apps.plugins.api.API_VERSION) this plugin works with.
    metra_api = [1]
    # Edited under Settings > Add-ons > Mailgun. A METRA_MAILGUN_* variable in
    # the environment wins over the page.
    metra_settings = [
        Setting(
            "domain",
            _("Sending domain"),
            help=_("The domain you added at Mailgun, for example mg.example.fi."),
            env="METRA_MAILGUN_DOMAIN",
        ),
        Setting(
            "api_key",
            _("API key"),
            kind=Setting.SECRET,
            help=_("A sending API key for the domain, from Mailgun."),
            env="METRA_MAILGUN_API_KEY",
        ),
        Setting(
            "region",
            _("Region"),
            kind=Setting.CHOICE,
            choices=[("eu", _("EU (api.eu.mailgun.net)")), ("us", _("US (api.mailgun.net)"))],
            default="eu",
            help=_(
                "Where your Mailgun account keeps its data. Choose EU unless it was made in the US."
            ),
            env="METRA_MAILGUN_REGION",
        ),
        Setting(
            "webhook_key",
            _("Webhook signing key"),
            kind=Setting.SECRET,
            help=format_lazy(
                _(
                    "From Mailgun's Webhooks page. There, add {url} for delivered "
                    "messages, permanent failures and spam complaints."
                ),
                url=settings.BASE_URL + "/plugins/mailgun/events/",
            ),
            env="METRA_MAILGUN_WEBHOOK_KEY",
        ),
    ]

    def ready(self):
        from apps.plugins import api

        from .providers import Mailgun

        api.add_messaging_provider(Mailgun)
