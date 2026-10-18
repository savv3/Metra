"""Find the plugins an installation enabled with METRA_PLUGINS.

A plugin is a pip-installable package that is a Django app and declares an
entry point in the ``metra.plugins`` group, for example in its pyproject.toml:

    [project.entry-points."metra.plugins"]
    example = "metra_example_plugin"

Installed plugins are not loaded on their own: only names listed in
METRA_PLUGINS are added to INSTALLED_APPS. The official plugins in BUNDLED
are the exception: they come with Metra (in plugins/ and in the Docker image)
and are on whenever installed, unless METRA_PLUGINS_DISABLED lists them.
See docs/plugins.md.
"""

from importlib.metadata import entry_points

from django.core.exceptions import ImproperlyConfigured

GROUP = "metra.plugins"
# The group's name before the rename to Metra; plugins using it still load.
LEGACY_GROUP = "scr.plugins"
# Official plugins that ship with Metra and are on by default, in load order.
BUNDLED = ("46elks",)


def available():
    """{name: entry point} for every installed plugin."""
    found = {entry_point.name: entry_point for entry_point in entry_points(group=LEGACY_GROUP)}
    found.update((entry_point.name, entry_point) for entry_point in entry_points(group=GROUP))
    return found


def app_for(entry_point):
    """The INSTALLED_APPS entry: "pkg" or "pkg.apps:Config" becomes "pkg.apps.Config"."""
    return entry_point.value.replace(":", ".").strip()


def enabled_names(listed, disabled=(), found=None, bundled=BUNDLED):
    """The plugins to load: the installed bundled ones not disabled, then the
    ones METRA_PLUGINS lists, each once."""
    found = available() if found is None else found
    names = [name for name in bundled if name in found and name not in disabled]
    names += [name for name in listed if name not in names]
    return names


def enabled_apps(names, found=None):
    """{plugin name: INSTALLED_APPS entry} for the enabled names, in the order given."""
    found = available() if found is None else found
    apps = {}
    for name in names:
        if name not in found:
            installed = ", ".join(sorted(found)) or "none"
            raise ImproperlyConfigured(
                f"METRA_PLUGINS lists {name!r}, but no installed package provides a plugin by "
                f"that name (installed: {installed})."
            )
        apps[name] = app_for(found[name])
    return apps


def url_patterns(plugin_apps):
    """A plugin with a ``urls`` module gets it mounted at /plugins/<name>/."""
    from importlib import import_module
    from importlib.util import find_spec

    from django.apps import apps
    from django.urls import include, path

    patterns = []
    for name, entry in plugin_apps.items():
        config = next(c for c in apps.get_app_configs() if entry in (c.name, _config_path(c)))
        module = f"{config.name}.urls"
        if find_spec(module) is not None:
            patterns.append(path(f"plugins/{name}/", include(import_module(module))))
    return patterns


def _config_path(config):
    return f"{type(config).__module__}.{type(config).__name__}"
