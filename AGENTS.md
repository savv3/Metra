# AGENTS.md

Guidance for AI coding agents (and humans) working in this repository.
`CLAUDE.md` imports this file, so this is the single source of truth.

## What this is

Metra is an open source (MIT), self-hostable web app for small companies and
associations: a register of units and their contacts, annual readings, SMS
and email, invoicing, bookkeeping, an API and offsite backups. The first user
is a water association with about 50 households, but the product stays
**configurable**: record types and fields are set up by an admin, never
hard-coded for water. Something only one kind of organisation needs becomes
a setting or a configurable type.

The plan, data model and roadmap are in
[docs/architecture.md](docs/architecture.md).

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

- **One PR per feature** (one row of the phase plan in `docs/architecture.md`),
  with CI green. Review fixes go on the same branch before merging, not in a
  new PR; small unrelated fixes wait and go together in one PR.
- **Build straight away.** Plan and wait for approval only for data model,
  security, privacy and bookkeeping-law changes.
- **Short-lived branches** from the latest `main`; bring in `main` once,
  just before merging, only if there are conflicts.
- **Release in batches,** when there is something to deploy or the
  maintainer asks, never after every PR ([docs/releasing.md](docs/releasing.md)).
- **Subagents only for big independent pieces** (for example all
  translations of a large PR); small edits are cheaper done yourself. Cheap
  models for mechanical work, the strongest for design, security,
  bookkeeping and reviews. Whoever starts a subagent checks its work.
- **Read only what the task needs:** `docs/architecture.md` for a new
  module, `docs/ui-conventions.md` for templates, `docs/plugins.md` for
  plugins. Finished build plans are in `docs/history/`.

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

The gettext commands need GNU gettext and always `--ignore=.venv`.

## Conventions

- **Layout:** settings in `config/`, Django apps in `apps/<name>/`, shared
  templates in `templates/`, translations in `locale/`. Integrations with
  outside services (SMS, REST API, webhooks) are plugins in `plugins/<name>/`
  that use only `apps.plugins.api`; see `docs/plugins.md`.
- **Configuration:** every per-install value is a `METRA_` environment
  variable documented in `.env.example`; no secrets in the repo. Settings
  changed in the app (plugin settings, `api.Setting`) keep an environment
  variable that wins when set. Secrets saved in the database are encrypted
  with `apps.plugins.secrets`, never shown again and kept out of the audit log.
- **Plugins on and off** (`apps.plugins.state`): anything a plugin adds is
  left out while it is off, so new extension points go through
  `hooks.register`/`hooks.get` or check `state.is_enabled`. The interface
  calls them add-ons (Tillägg, Lisäosat), never plugins.
- **Data:** everything persistent lives under `METRA_DATA_DIR`.
- **Translations:** every user-facing string goes through `gettext` /
  `{% translate %}`, with Swedish and Finnish entries in
  `locale/{sv,fi}/LC_MESSAGES/django.po` in the same PR. Finnish is machine
  translated and stays in `MACHINE_TRANSLATED_LANGUAGES`. `.mo` files are not
  committed.
- **Interface and help:** follow [docs/ui-conventions.md](docs/ui-conventions.md).
  A change users notice updates its help article in `apps/help/articles/`
  in all three languages.
- **Privacy (GDPR):** store only fields with a clear purpose, log changes to
  personal data, and cover new personal data in the per-person export and
  erasure tools. Personal data goes to third parties only through a
  configured, documented provider.
- **Bookkeeping data:** sent invoices and payments are immutable; correct
  them with credit notes.
- **Access:** every view uses `permission_required(..., raise_exception=True)`
  and templates hide buttons with `perms`. Roles are the groups from
  `apps/accounts/migrations/0001_roles.py`; a new permission needs a
  migration adding it to the right roles. Staff need two-factor login
  (`apps/accounts/middleware.py`) unless `METRA_REQUIRE_MFA` is off (default
  only with `METRA_DEBUG=true`); tests run with it on. All logins go through
  django-allauth; non-page requests (icons, robots.txt) stay out of the
  middleware's redirect.
- **Audit log:** register models holding personal or business data with
  django-auditlog (as in `apps/register/models.py`) and log detail-page views
  with `history.log_view`.
- **Tests:** pytest-django; shared fixtures (`make_user`, `role_client`,
  `board_client`, `unit`, `person`) in `conftest.py`. New behaviour comes
  with tests. CI runs ruff, the migration check and pytest.
- **Versions and changelog:** the version lives only in `pyproject.toml`
  ([docs/releasing.md](docs/releasing.md)). Every PR users, admins or plugin
  authors notice adds a line under **Unreleased** in `CHANGELOG.md`. A
  breaking change to `apps/plugins/api.py` bumps `API_VERSION`.
- **Dependencies:** prefer Django built-ins; add runtime dependencies only
  when they save real work.
