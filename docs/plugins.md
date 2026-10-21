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
     `METRA_PLUGIN_PACKAGES="metra-something==1.2 git+https://example.org/x.git"`.
     Then rebuild with `docker compose up -d --build`. You can also build
     your own image `FROM metra:latest` and `pip install`
     into `/app/.venv`.
   - Without Docker, install it with `uv pip install` or `pip install`.
2. Enable it by name in `METRA_PLUGINS`, a comma-separated list, for example
   `METRA_PLUGINS=example`. Installed plugins that are not listed are never
   loaded. An unknown name stops the app at startup with a clear error.
   The official plugins that come with Metra (see below) are the exception:
   they are on by default, and `METRA_PLUGINS_DISABLED` turns one off.
3. Restart. The web container runs the plugin's migrations on start.

Installed plugins can then be turned on and off by an admin under
**Settings > Add-ons**, without a restart. While a plugin is off, its menu
items, panels, settings links, help articles, notification kinds, webhook
events, messaging providers, event receivers and pages under
`/plugins/<name>/` are left out, and its data is kept. Each process reads
the on/off states again within two seconds of a change.

## Writing a plugin

Start from [plugins/example](../plugins/example), which the tests load. A
plugin needs four things.

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

**An AppConfig that names the plugin API versions it works with**, in
`metra_api`. When none of them is one this Metra release supports
(`api.SUPPORTED_API_VERSIONS`), the app refuses to start with a clear
error (`plugins.E001`) instead of breaking later. Without it, `manage.py
check` warns (`plugins.W002`). How the API version changes is in
[releasing.md](releasing.md#the-plugin-api).

```python
class ExamplePluginConfig(AppConfig):
    name = "metra_example_plugin"
    personal_data = []
    metra_api = [1]
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

Everything a plugin registers belongs to it, worked out from the module
that calls `api`, so it disappears while an admin has the plugin turned off.
Event receivers count as the plugin's when their function is in the
plugin's package.

A plugin's `urls.py`, if it has one, is mounted at `/plugins/<name>/`.
Views must check a permission, as the app's own do (see AGENTS.md). To react
to changes, listen to the events below rather than to Metra's models.

**Settings.** A plugin lists its settings in `metra_settings` on its
AppConfig, and Metra makes a settings page for it under **Settings >
Add-ons** (admins only). Each `api.Setting(key, label, kind, help, default,
choices, env, required)` has a kind: `Setting.TEXT`, `NUMBER`, `CHOICE`,
`BOOL` or `SECRET`. Secrets (API keys, passwords) are stored encrypted with
`METRA_SETTINGS_KEY` (or a key derived from `METRA_SECRET_KEY`), are never
shown again once saved, only replaced or removed, and the audit log records
which setting changed but not its value. A setting with `env` takes the
value of that environment variable when it is set, and the page shows it as
locked. Read values with `api.plugin_settings("name").get("key")`, or
`api.plugin_settings()` from the plugin's own code:

```python
class ExamplePluginConfig(AppConfig):
    metra_settings = [
        api.Setting("api_user", "API user", env="METRA_THING_USER"),
        api.Setting("api_key", "API key", kind=api.Setting.SECRET),
        api.Setting(
            "region",
            "Region",
            kind=api.Setting.CHOICE,
            choices=[("eu", "EU"), ("us", "US")],
            default="eu",
        ),
    ]
```

**Permissions for roles.** A plugin with its own models gives their
permissions to Metra's roles (Admin, Board, Treasurer, Read-only) in a
migration, with `api.grant_to_roles`:

```python
from apps.plugins import api


class Migration(migrations.Migration):
    dependencies = [("my_plugin", "0001_initial"), ("accounts", "0001_roles")]
    operations = [
        api.grant_to_roles(
            {
                "Admin": ["my_plugin.view_thing", "my_plugin.change_thing"],
                "Board": ["my_plugin.view_thing"],
            }
        ),
    ]
```

## Official plugins in this repository

Plugins developed with Metra live in [plugins/](../plugins), one package per
folder, as members of a uv workspace: `uv sync` installs them all for
development, and CI runs their tests with the app's. The official ones are
listed in `BUNDLED` in `config/plugins.py`, installed in the Docker image and
on by default; `METRA_PLUGINS_DISABLED` turns one off. The example plugin is
installed only for development and tests. The [webhooks plugin](webhooks.md)
and the meetings plugin are official but off by default: they are installed
in the Docker image, and `METRA_PLUGINS=webhooks,meetings` turns them on.

| Plugin | Name | What it does |
| --- | --- | --- |
| [metra-sms-46elks](../plugins/sms-46elks) | `46elks` | SMS through 46elks, with delivery reports. Bundled, on by default |
| [metra-email-mailgun](../plugins/email-mailgun) | `mailgun` | Email through Mailgun, with delivery, bounce and spam reports. Bundled, on by default; sends once chosen under Settings > Email |
| [metra-api](../plugins/api) | `api` | The REST API ([docs](api.md)). Off until `METRA_PLUGINS=api` |
| [metra-webhooks](../plugins/webhooks) | `webhooks` | Signed webhooks to outside systems ([docs](webhooks.md)). Off until `METRA_PLUGINS=webhooks` |
| [metra-meetings](../plugins/meetings) | `meetings` | Meetings: notice with the agenda, attendance and votes, minutes approved by the minute checkers and shown to members. Off until `METRA_PLUGINS=meetings` |

So that each can later move to its own repository, a plugin in plugins/:

- imports only `apps.plugins.api` from Metra, never other app modules;
- keeps its tests inside its package (`src/<package>/tests/`), using the
  shared fixtures in the root `conftest.py`;
- keeps its translations in its own `locale/` folder, made from the package
  folder (for example `plugins/api/src/metra_api`) with
  `METRA_DEBUG=true DJANGO_SETTINGS_MODULE=config.settings PYTHONPATH=<repository root> uv run django-admin makemessages -l sv -l fi -l en`
  (the app's own `makemessages` from the repository root also finds a
  plugin's `locale/` folder and fills it);
- declares its own dependencies in its `pyproject.toml`.

## Extension points

| Extension point | API | What it takes |
| --- | --- | --- |
| Navigation | `api.add_navigation(NavItem(label, url_name, permission))` | A main-menu link, shown to users with the permission |
| Unit panels | `api.add_unit_panel(Panel(template, title, permission, context))` | A section on unit pages. The template gets `object`, `title`, `perms`, `request` and whatever `context(request, unit)` returns |
| Person panels | `api.add_person_panel(Panel(...))` | The same, on person pages |
| SMS and email providers | `api.add_messaging_provider(ProviderClass)` | An `api.Provider` subclass with `channel` (`api.SMS` or `api.EMAIL`), `name` and `send()`. An SMS provider is chosen with `METRA_SMS_PROVIDER=<name>`, or automatically when `is_configured()` returns true; an email provider is chosen by an admin under Settings > Email, and then also gets the app's own mail (login codes, invitations) through `send_email_message(message)`, which by default sends the plain text with `send()` and can be overridden to send the whole Django `EmailMessage`. `api.sms_sender()`, `api.sms_country_code()`, `api.normalise_phone()` and `api.record_delivery()` help SMS providers. Email providers are chosen under Settings > Email; `api.email_from()` gives the from and Reply-To addresses, the email of a send-out carries its id in the `api.SEND_OUT_HEADER` header, and `api.record_email_event(provider, provider_id, event, reason)` records `api.DELIVERED`, `api.BOUNCED` (the message fails and the person's address is flagged) or `api.COMPLAINED` |
| Settings links | `api.add_settings_link(SettingsLink(label, url_name, permission, description))` | A link on the Settings page to the plugin's own settings or tools, listed under **Integrations** with its `description` below it. It is shown only to users with `permission` (no permission: everyone who can open Settings). Give it a name people understand, such as "API clients"; the page never calls them plugins |
| Member page panels | `api.add_member_panel(MemberPanel(template, title, context))` | A section on the member page behind a personal link, below the page's own sections. The template gets `unit`, `person`, `token`, `title`, `request` and whatever `context(request, member_link)` returns. Members are not users, so no permission applies: show only what the member may see. See "Serving members" below |
| Help articles | `api.add_help_articles(HelpArticles(folder, order, pages))` | Markdown articles in `folder/<language>/<slug>.md`, each starting with `# Title`; `order` lists the slugs for the help index and `pages` maps the plugin's URL namespaces to the article its pages' Help link opens. An article missing in the reader's language is shown in English |
| Webhook events | `api.add_webhook_event(WebhookEvent(name, label, signal, payload))` | An event that webhook endpoints can subscribe to. `signal` is a Django signal sent after commit; `payload(**signal_kwargs)` returns a dict of ids and non-personal facts (never names, emails, phones or addresses). Works whether or not the webhooks plugin is enabled, and whichever plugin loads first. A plugin that sends webhooks reads them with `api.webhook_events()` and `api.on_webhook_event(listener)` |
| Notifications | `api.add_notification_kind(NotificationKind(name, label, message, roles, permission, default_on))` and `api.notify(kind, params, link, users, roles, group)` | A kind of notification for the bell, listed on each user's notification settings. `message` is a translated text with `%(name)s` placeholders filled from `params` when it is shown, in the reader's language; use `ngettext_lazy(singular, plural, "count")` for a count. `roles` (such as `["Admin"]`) get it when `notify` names no users or roles, and only users with `permission` (one name or a list) do. A kind with `default_on=False` goes only to users who turn it on. `notify` sends after the transaction commits and never raises; `link` is a path on this site, and a `group` joins it to an unread notification of the same kind and group from the last 24 hours, adding up `params["count"]`. Keep `params` to counts and technical facts, never members' personal data |

## PDFs and messages

`api.render_pdf(html)` turns a complete HTML document (CSS inline, images as
`data:` URIs) into PDF bytes with WeasyPrint, as invoices are made. It raises
`api.PDFUnavailable` when WeasyPrint or its Pango library is missing, so
catch it and tell the user.

`api.message_draft(request, subject, body, files=[(filename, bytes,
mimetype)], email_body="")` prepares a message for the current user and
returns the address of the New message form, filled in and with the files
attached and ticked. Redirect to it: staff choose the recipients, check and
send as usual, so a plugin never sends to everyone on its own. `body` is the
SMS text (and the email's, unless `email_body` is given); the usual
placeholders such as `{first_name}` work. The form needs the
`messaging.send_broadcast` permission, so show the button only to users with
it. Files must be types the form accepts (PDF, images, office documents) and
within its size limits, or `ValidationError` is raised. The draft is kept in
the user's session for a few hours.

## Serving members

The member page is opened through a personal link with no login. A plugin
that shows members something more, such as a file to download, adds a
`MemberPanel` (above) with links to its own views under the same token, and
answers in those views like this:

```python
@never_cache
def member_file(request, token, pk):
    link = api.member_link(request, token)
    if link is None:
        return api.member_unavailable(request)
    thing = ...  # only what this member (link.unit, link.person) may see
    link.log_access(request, thing)  # in the audit log, as the member pages do
    return api.member_response(HttpResponse(...))
```

`api.member_link` counts against the member pages' rate limit and records a
failure for a token that does not work, so guessing is slow; it returns
None for unknown, expired and revoked links and when there were too many
tries. `api.member_unavailable` gives the same page the member pages give
then. `api.member_response` adds their privacy headers: not cached, not
indexed, and no referrer to other sites. `api.member_page_url(token)` is the
full address of the member page.

## Records

A plugin that reads or changes Metra's data uses the models, forms and
helpers in `api.RECORDS`, never `apps.*` modules:

| Name | What it is |
| --- | --- |
| `api.Unit`, `api.Person`, `api.UnitContact`, `api.UnitType`, `api.CustomField`, `api.Tag` | The register's models |
| `api.Organisation` | The organisation's own details; `Organisation.current()` is the one in use, or None |
| `api.ReadingType`, `api.ReadingRound`, `api.Reading` | Readings |
| `api.Invoice`, `api.InvoiceLine`, `api.Payment` | Invoicing. Issued invoices and payments never change: only read them |
| `api.UnitForm`, `api.PersonForm`, `api.UnitContactForm`, `api.ReadingForm` | The forms staff use. Check data from outside with them, so a plugin never stores what the web pages would refuse (custom fields included) |
| `api.log_view(obj)` | Record in the audit log that the current user opened a unit or person, as its page does |

They load on first use, so `from apps.plugins import api` stays safe at
import time; use them in `ready()`, views and serializers, not at the top of a
plugin's `models.py`. Changes made through the models are in the audit log;
outside a web request, set the actor with `auditlog.context.set_actor`.

## Events

`api.events` has signals that Metra sends once a change is committed to the
database, so a receiver never sees a change that was rolled back:

| Event | Arguments |
| --- | --- |
| `api.events.unit_saved` | `unit`, `created` (archiving a unit is a change) |
| `api.events.person_saved` | `person`, `created` |
| `api.events.reading_saved` | `reading`, `created` (entered by staff or a member) |
| `api.events.invoice_issued` | `invoice` (an invoice or a credit note got its number) |
| `api.events.payment_recorded` | `payment` |

```python
from django.dispatch import receiver
from apps.plugins import api


@receiver(api.events.invoice_issued)
def on_invoice_issued(sender, invoice, **kwargs): ...
```

Receivers run in the request or worker that made the change, so anything
slow belongs in a background task. An error in a receiver is logged and does
not undo the change.

A panel that raises an error is left out of the page and logged. With
`METRA_DEBUG=true` the error is shown instead.

More extension points come with the features they hook into: custom field
types, backup targets, CSV import and export formats, reading validators,
invoice line generators. The REST API is a plugin itself; see [api.md](api.md).
