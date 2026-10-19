from django.apps import apps
from django.conf import settings
from django.core.checks import Error, Warning, register

from .api import API_VERSION, SUPPORTED_API_VERSIONS


def plugin_configs():
    plugin_modules = {entry.split(".")[0] for entry in settings.PLUGIN_APPS.values()}
    return [c for c in apps.get_app_configs() if c.name.split(".")[0] in plugin_modules]


@register()
def plugins_declare_personal_data(app_configs, **kwargs):
    """Every enabled plugin says what personal data it stores, so the export and
    erasure tools can cover it (an empty list when it stores none)."""
    warnings = []
    for config in plugin_configs():
        if not hasattr(config, "personal_data"):
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


@register()
def plugins_match_the_api_version(app_configs, **kwargs):
    """Every enabled plugin names the plugin API versions it works with
    (``metra_api``). One that supports none of this release's stops the app
    with a clear error, rather than failing somewhere at run time."""
    problems = []
    for config in plugin_configs():
        wanted = getattr(config, "metra_api", None)
        if wanted is None:
            problems.append(
                Warning(
                    f"The plugin {config.name} does not declare metra_api.",
                    hint=f"Set metra_api on its AppConfig to the plugin API versions it works "
                    f"with, for example [{API_VERSION}]. See docs/plugins.md.",
                    obj=config,
                    id="plugins.W002",
                )
            )
        elif not set(wanted) & set(SUPPORTED_API_VERSIONS):
            supported = ", ".join(str(v) for v in SUPPORTED_API_VERSIONS)
            problems.append(
                Error(
                    f"The plugin {config.name} needs plugin API version "
                    f"{', '.join(str(v) for v in wanted)}, but this Metra supports {supported}.",
                    hint="Install a version of the plugin made for this Metra release, or "
                    "turn the plugin off. See docs/releasing.md.",
                    obj=config,
                    id="plugins.E001",
                )
            )
    return problems
