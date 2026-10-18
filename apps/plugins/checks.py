from django.apps import apps
from django.conf import settings
from django.core.checks import Warning, register


@register()
def plugins_declare_personal_data(app_configs, **kwargs):
    """Every enabled plugin says what personal data it stores, so the export and
    erasure tools can cover it (an empty list when it stores none)."""
    plugin_modules = {entry.split(".")[0] for entry in settings.PLUGIN_APPS.values()}
    warnings = []
    for config in apps.get_app_configs():
        if config.name.split(".")[0] in plugin_modules and not hasattr(config, "personal_data"):
            warnings.append(
                Warning(
                    f"The plugin {config.name} does not declare personal_data.",
                    hint="Set personal_data on its AppConfig: a list of the personal data it "
                    "stores, or [] for none. See docs/plugins.md.",
                    obj=config,
                    id="plugins.W001",
                )
            )
    return warnings
