# AGENTS.md

Guidance for AI coding agents (and humans) working in this repository.
`CLAUDE.md` imports this file, so this is the single source of truth.

## What this is

SmallCompanyRegister is an open source (MIT), self-hostable web app for small
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
| Languages | Swedish (default) and English |
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
export SCR_DEBUG=true                           # local development defaults
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
  shared templates in `templates/`, translations in `locale/`.
- **Configuration:** every per-installation value is an environment variable
  prefixed `SCR_` and documented in `.env.example`. No secrets in the repo.
- **Data:** everything persistent lives under `SCR_DATA_DIR` (databases,
  uploads), so one directory is all a backup needs.
- **Translations:** every user-facing string goes through `gettext` /
  `{% translate %}`. Add the Swedish translation in
  `locale/sv/LC_MESSAGES/django.po` in the same PR. Compiled `.mo` files are
  not committed.
- **Privacy (GDPR):** store only fields with a clear purpose, log changes to
  personal data, and make sure new personal data is covered by the
  per-person export and erasure tools. Never send personal data to a third
  party except through a configured, documented provider.
- **Bookkeeping data:** sent invoices and payments are immutable; correct
  them with credit notes, not edits.
- **Tests:** pytest with pytest-django. New behaviour comes with tests; CI
  runs ruff, the migration check and pytest.
- **Dependencies:** prefer Django's built-ins and well-maintained, free
  packages. Add new runtime dependencies only when they save real work.
