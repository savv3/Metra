from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class MessagingConfig(AppConfig):
    name = "apps.messaging"
    verbose_name = _("Messaging")

    def ready(self):
        # Register the built-in SMS and email providers.
        from . import providers  # noqa: F401
