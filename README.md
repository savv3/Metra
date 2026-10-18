# SmallCompanyRegister

A simple, self-hostable web app for small companies and associations to keep
track of their members and clients. Free and open source under the MIT
licence.

Built first for a water association with about 50 households, but
configurable for clubs, associations and small businesses. Planned features:
a configurable register, annual readings with member self-service, SMS and
email messaging, newsletters, invoicing, an API and offsite backups. See
[docs/architecture.md](docs/architecture.md) for the plan.

**Status:** early development (phase 1: register, roles, two-factor login, audit log, CSV import and export).

## Run it with Docker

```sh
cp .env.example .env    # then set SCR_DOMAIN and SCR_SECRET_KEY
docker compose up -d --build
```

Caddy serves the app on your domain with automatic HTTPS. All data lives in
the `data` Docker volume.

## Develop locally

Needs Python 3.13, [uv](https://docs.astral.sh/uv/) and GNU gettext.

```sh
uv sync
export SCR_DEBUG=true
uv run python manage.py migrate
uv run python manage.py compilemessages --ignore=.venv
uv run python manage.py createsuperuser
uv run python manage.py load_sample_setup water   # optional: the water association setup
uv run python manage.py runserver
```

Log in at http://localhost:8000. Record types and their custom fields are set
up under **Settings** (the Django admin); units and people are managed on the
main pages.

### Import and export

**Units > Import CSV** (Admin and Board) imports units of one type, each with
up to one contact person:

1. Choose the unit type and the file. It must be UTF-8 (in Excel: *CSV UTF-8*),
   with semicolons, commas or tabs between columns and one header row.
2. Check which column goes to which field. Columns whose header matches a
   field name or a custom field's label or key are chosen for you.
3. Check the preview: every row is marked OK, skipped (the unit name is
   already in the register, if you chose to skip those) or shown with its
   errors. Nothing is imported while any row has errors, and the import is
   all or nothing.

Contacts are matched to people already in the register by email, or by phone
when there is no email, so nobody is added twice; existing people are linked,
not changed. Dates can be written 2026-04-01 or 1.4.2026, yes/no fields as
ja/nej or yes/no, and tags must already exist. An example file for the water
association setup is linked on the import page
([static/examples/hushall-exempel.csv](static/examples/hushall-exempel.csv)).

The unit and people lists have an **Export as CSV** link that downloads the
current filtered list, semicolon-separated with a UTF-8 BOM so Excel shows å,
ä and ö correctly. Custom fields become columns named by their labels. Every
export is recorded in the audit log with who exported which records; the
file is made in memory and never stored on the server.

### Users, roles and two-factor login

The first account comes from `createsuperuser` (in Docker:
`docker compose exec web python manage.py createsuperuser`). When it first
logs in, the app asks for the password once more and then for an
authenticator app (for example Aegis, Google Authenticator or 1Password):
scan the QR code, enter the six-digit code, and save the recovery codes it
shows. Staff and superusers cannot use the app until this is done, and from
then on every login asks for a code.

Further users are added under **Settings > Users**. Give each one a role by
adding them to one group:

| Role | Can |
| --- | --- |
| Admin | Everything; also tick "Staff status" so they can open Settings |
| Board (Styrelse) | View, add and edit units, people, contacts and tags; archive; see history |
| Treasurer (Kassör) | View the register (invoicing comes later) |
| Read-only (Läsbehörighet) | View the register |

The roles are shown in the user's language; groups you create yourself keep
the name you give them. Two-factor login is optional for users without staff status; they can turn it
on under **Two-factor login**. Every change to the register, every role
change and every opened unit or person page is recorded in the audit log,
shown on the unit and person pages for Admin and Board and under
**Settings > Log entries**.

Run the checks with `uv run pytest` and `uv run ruff check .`. More
conventions are in [AGENTS.md](AGENTS.md).

## Licence

MIT, see [LICENSE](LICENSE).
