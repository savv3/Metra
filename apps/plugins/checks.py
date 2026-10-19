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


@register()
def names_from_before_the_rename(app_configs, **kwargs):
    """Old SCR_ settings and plugins in the old "scr.plugins" group still work,
    but should be renamed before support for them is removed."""
    from config.plugins import LEGACY_GROUP, legacy_plugins

    warnings = []
    if names := getattr(settings, "LEGACY_SETTING_NAMES", []):
        warnings.append(
            Warning(
                f"Settings with the old SCR_ prefix are in use: {', '.join(names)}.",
                hint="Rename them to METRA_ in .env (for example SCR_DOMAIN to METRA_DOMAIN). "
                "They still work for now.",
                id="core.W001",
            )
        )
    if names := legacy_plugins():
        warnings.append(
            Warning(
                f"Plugins declare the old entry point group {LEGACY_GROUP!r}: {', '.join(names)}.",
                hint='Change [project.entry-points."scr.plugins"] to '
                '[project.entry-points."metra.plugins"] in the plugin\'s pyproject.toml.',
                id="plugins.W003",
            )
        )
    return warnings
