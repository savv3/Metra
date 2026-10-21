from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from apps.plugins.api import Setting


class FortySixElksConfig(AppConfig):
    name = "metra_sms_46elks"
    label = "metra_sms_46elks"
    verbose_name = "46elks SMS"
    default_auto_field = "django.db.models.BigAutoField"

    # Messages and their delivery status are stored by Metra, not here.
    personal_data = []
    # The plugin API versions (apps.plugins.api.API_VERSION) this plugin works with.
    metra_api = [1]
    # Edited under Settings > Add-ons > 46elks SMS. A METRA_ELKS_* or
    # METRA_SMS_SENDER variable in the environment wins over the page.
    metra_settings = [
        Setting(
            "api_user",
            _("API username"),
            help=_("At 46elks, under Account."),
            env="METRA_ELKS_API_USER",
        ),
        Setting(
            "api_password",
            _("API password"),
            kind=Setting.SECRET,
            help=_("At 46elks, under Account."),
            env="METRA_ELKS_API_PASSWORD",
        ),
        Setting(
            "sender",
            _("Sender"),
            help=_(
                "The name shown on the phone, up to 11 letters and digits (for example "
                "Vatten), or a number you have at 46elks."
            ),
            env="METRA_SMS_SENDER",
        ),
        Setting(
            "dry_run",
            _("Test mode"),
            kind=Setting.BOOL,
            help=_("46elks checks messages without sending them or charging."),
            env="METRA_ELKS_DRY_RUN",
        ),
    ]

    def ready(self):
        from apps.plugins import api

        from .providers import FortySixElks

        api.add_messaging_provider(FortySixElks)
