from django.conf import settings
from django.core.checks import Error, register

from .registry import AUTO, SMS, registry


@register()
def sms_provider_exists(app_configs, **kwargs):
    """METRA_SMS_PROVIDER names a provider that is installed and enabled."""
    name = settings.MESSAGING["sms_provider"]
    if name in ("", "none", AUTO) or name in registry.names(SMS):
        return []
    return [
        Error(
            f"METRA_SMS_PROVIDER is {name!r}, but no enabled plugin provides an SMS provider "
            f"by that name (available: {', '.join(registry.names(SMS))}).",
            hint="Enable the plugin that provides it (see METRA_PLUGINS and "
            "METRA_PLUGINS_DISABLED), or set METRA_SMS_PROVIDER=auto.",
            id="messaging.E001",
        )
    ]
