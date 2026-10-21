# AGENTS.md

Guidance for AI coding agents (and humans) working in this repository.
`CLAUDE.md` imports this file, so this is the single source of truth.

## What this is

Metra is an open source (MIT), self-hostable web app for small
companies and associations to manage members and clients: a register of
households or other units and their contacts, annual readings (for example
water usage), SMS and email messaging, newsletters, invoicing, an API, and
offsite backups.

The first user is a water association serving about 50 households, but the
product must stay **configurable**: record types and fields are set up by an
admin, never hard-coded for water. If a feature only makes sense for one
kind of organisation, make it a setting or a configurable type.

The full plan, data model and roadmap are in
[docs/architecture.md](docs/architecture.md). Read it before starting a new
module.

## Decisions already made

Do not revisit these without the maintainer asking.

| Topic | Decision |
| --- | --- |
| Stack | Python 3.13, Django 5.2 LTS, server-rendered templates with HTMX |
| Database | SQLite only (WAL mode), no PostgreSQL or Redis |
| Background jobs | Huey with SQLite storage, run as `manage.py run_huey` |
| Deployment | Docker Compose: `web`, `worker`, `caddy` sharing one data volume |
| Licence | MIT |
| Languages | Swedish (default), English and Finnish (machine translated, flagged in the UI) |
| First country rules | Finland including Åland (Åland is outside the EU VAT area) |
| Member self-service | Yes, through expiring personal links, no member passwords |
| SMS provider | 46elks, behind a provider interface so others can be added |

## How to work here

- **Plan first.** For anything bigger than a small fix, write a short plan
  and get the maintainer's approval before writing code.
- **Small pull requests.** Follow the phase plan in `docs/architecture.md`;
  one PR per row of the phase table. Each PR keeps CI green.
- **Use subagents and match the model to the task.** When your tool can
  start subagents, split independent work and run it in parallel. Send
  simpler tasks to cheaper, faster models and keep the strongest model for
  hard judgement:
  - Cheapest model (for example Haiku): mechanical edits, renames,
    translation entries, boilerplate, formatting, simple searches.
  - Mid-tier model (for example Sonnet): well-specified features, tests,
    Docker and CI changes, documentation.
  - Strongest model (for example Opus): architecture and data model
    decisions, security and privacy work, tricky bugs, reviewing other
    agents' output before it is committed.
  The agent that starts subagents stays responsible for checking their work.

## Commands

```sh
uv sync                                         # install dependencies
export METRA_DEBUG=true                           # local development defaults
uv run python manage.py migrate
uv run python manage.py compilemessages --ignore=.venv
uv run python manage.py runserver               # http://localhost:8000
uv run python manage.py run_huey                # background worker
uv run pytest                                   # tests (uses config.test_settings)
uv run ruff check . && uv run ruff format --check .
uv run python manage.py makemessages -l sv -l en --ignore=.venv
docker compose up --build                       # full stack, needs a .env (see .env.example)
```

`compilemessages` and `makemessages` need GNU gettext installed. Always pass
`--ignore=.venv` so they skip installed packages.

## Conventions

- **Layout:** project settings in `config/`, Django apps in `apps/<name>/`,
  shared templates in `templates/`, translations in `locale/`. Integrations
  and providers for outside services (SMS gateways, the REST API, webhooks)
  are plugins in `plugins/<name>/` that use only `apps.plugins.api`, so they
  can move to their own repository later; see `docs/plugins.md`.
- **Configuration:** every per-installation value is an environment variable
  prefixed `METRA_` and documented in `.env.example`. No secrets in the repo.
  Settings an admin changes in the app (plugins' settings, `api.Setting`)
  keep an environment variable that wins when set, and secrets saved in the
  database are encrypted with `apps.plugins.secrets`, never shown again and
  kept out of the audit log.
- **Plugins on and off:** admins turn installed plugins on and off in the
  app (`apps.plugins.state`). Anything a plugin adds through
  `apps.plugins.api` is left out while it is off, so new extension points go
  through `hooks.register`/`hooks.get` (or check `state.is_enabled`). In the
  interface plugins are called add-ons (Tillägg, Lisäosat), never plugins.
- **Data:** everything persistent lives under `METRA_DATA_DIR` (databases,
  uploads), so one directory is all a backup needs.
- **Translations:** every user-facing string goes through `gettext` /
  `{% translate %}`. Add the Swedish translation in
  `locale/sv/LC_MESSAGES/django.po` and the Finnish one in
  `locale/fi/LC_MESSAGES/django.po` in the same PR. The maintainer proofreads
  Swedish and English but not Finnish, which is machine translated: keep it
  in `MACHINE_TRANSLATED_LANGUAGES` so pages show a notice saying so. Compiled `.mo` files are
  not committed.
- **Help:** the in-app help articles are Markdown in
  `apps/help/articles/<language>/`, in Swedish, English and Finnish. A change
  users notice updates the article that describes it, in all three languages.
- **Privacy (GDPR):** store only fields with a clear purpose, log changes to
  personal data, and make sure new personal data is covered by the
  per-person export and erasure tools. Never send personal data to a third
  party except through a configured, documented provider.
- **Bookkeeping data:** sent invoices and payments are immutable; correct
  them with credit notes, not edits.
- **Access:** every view checks a model permission (`permission_required`
  with `raise_exception=True`, so refusals are a 403 page) and templates hide
  buttons with `perms`. Roles are the groups created in
  `apps/accounts/migrations/0001_roles.py`; a new model or permission needs a
  migration that adds it to the right roles. Staff must use two-factor login
  (`apps/accounts/middleware.py`) unless `METRA_REQUIRE_MFA` is off, which is
  the default only when `METRA_DEBUG=true` (staff then see a warning banner);
  tests run with it on. Keep every login path going through django-allauth,
  and keep requests that are not pages (icons, robots.txt) out of the
  middleware's redirect.
- **Audit log:** register models are registered with django-auditlog in
  `apps/register/models.py`; register new models holding personal or
  business data the same way, and log views of detail pages with
  `history.log_view`.
- **Tests:** pytest with pytest-django. Shared fixtures (`make_user`,
  `role_client`, `board_client`, `unit`, `person`) are in `conftest.py`.
  New behaviour comes with tests; CI runs ruff, the migration check and
  pytest.
- **Versions and changelog:** the app version lives only in
  `pyproject.toml`; see [docs/releasing.md](docs/releasing.md). Add a line
  under **Unreleased** in `CHANGELOG.md` in every PR that changes something
  users, admins or plugin authors notice. A breaking change to
  `apps/plugins/api.py` bumps `API_VERSION`; additions do not.
- **Dependencies:** prefer Django's built-ins and well-maintained, free
  packages. Add new runtime dependencies only when they save real work.
