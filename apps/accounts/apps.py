from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    verbose_name = _("Access")

    def ready(self):
        from auditlog.registry import auditlog
        from django.contrib.auth import get_user_model

        # Log who gives or takes away access, never password hashes.
        auditlog.register(
            get_user_model(),
            exclude_fields=["password", "last_login"],
            m2m_fields={"groups", "user_permissions"},
        )
