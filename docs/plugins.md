# Plugins

A plugin adds features to Metra without changing its code.
It is an ordinary Python package that is a Django app, so it can have
models, migrations, views, templates, static files and translations.

**Plugins run with full trust**, like any installed code: a plugin can read
and change everything in the register. Install only plugins you trust.

## Installing and enabling

1. Install the package into the app's environment.
   - With Docker, list it in `METRA_PLUGIN_PACKAGES` in `.env`. Use pip names,
     URLs or paths, separated by spaces, for example
     `METRA_PLUGIN_PACKAGES="scr-something==1.2 git+https://example.org/x.git"`.
     Then rebuild with `docker compose up -d --build`. You can also build
     your own image `FROM metra:latest` and `pip install`
     into `/app/.venv`.
   - Without Docker, install it with `uv pip install` or `pip install`.
2. Enable it by name in `METRA_PLUGINS`, a comma-separated list, for example
   `METRA_PLUGINS=example`. Installed plugins that are not listed are never
   loaded. An unknown name stops the app at startup with a clear error.
3. Restart. The web container runs the plugin's migrations on start.

## Writing a plugin

Start from [plugins/example](../plugins/example), which the tests load. A
plugin needs three things.

**An entry point** in the `metra.plugins` group, whose value is the Django app
(a module, or `module:AppConfig`):

```toml
[project.entry-points."metra.plugins"]
example = "metra_example_plugin"
```

**An AppConfig that declares its personal data**, so the export and erasure
tools can cover it. Use an empty list when the plugin stores none. Without
it, `manage.py check` warns (`plugins.W001`).

```python
class ExamplePluginConfig(AppConfig):
    name = "metra_example_plugin"
    personal_data = ["Person: membership card number"]
```

**Registrations in `ready()`**, through `apps.plugins.api`. Only that module
is a stable interface (see `api.API_VERSION`); anything else in the app can
change between releases.

```python
def ready(self):
    from apps.plugins import api

    api.add_navigation(api.NavItem("Cards", "my_plugin:index", "register.view_person"))
    api.add_person_panel(api.Panel("my_plugin/card.html", title="Card"))
    api.add_messaging_provider(MySMSProvider)
```

A plugin's `urls.py`, if it has one, is mounted at `/plugins/<name>/`.
Views must check a permission, as the app's own do (see AGENTS.md). For
model events, use Django signals (`post_save` and so on).

## Extension points

| Extension point | API | What it takes |
| --- | --- | --- |
| Navigation | `api.add_navigation(NavItem(label, url_name, permission))` | A main-menu link, shown to users with the permission |
| Unit panels | `api.add_unit_panel(Panel(template, title, permission, context))` | A section on unit pages. The template gets `object`, `title`, `perms`, `request` and whatever `context(request, unit)` returns |
| Person panels | `api.add_person_panel(Panel(...))` | The same, on person pages |
| SMS and email providers | `api.add_messaging_provider(ProviderClass)` | An `api.Provider` subclass with `channel` (`api.SMS` or `api.EMAIL`), `name` and `send()`. Chosen with `METRA_SMS_PROVIDER=<name>` |

A panel that raises an error is left out of the page and logged. With
`METRA_DEBUG=true` the error is shown instead.

More extension points come with the features they hook into: custom field
types, backup targets, CSV import and export formats, reading validators,
invoice line generators (phase 4), and API routes and webhook events
(phase 5).
