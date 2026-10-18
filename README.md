# SmallCompanyRegister

A simple, self-hostable web app for small companies and associations to keep
track of their members and clients. Free and open source under the MIT
licence.

Built first for a water association with about 50 households, but
configurable for clubs, associations and small businesses. Planned features:
a configurable register, annual readings with member self-service, SMS and
email messaging, newsletters, invoicing, an API and offsite backups. See
[docs/architecture.md](docs/architecture.md) for the plan.

**Status:** early development. Phase 1 (register, roles, two-factor login, audit log, CSV import and export, backups) is done; phase 2 (annual readings and member self-service) is being built.

## Run it with Docker

```sh
cp .env.example .env    # then set SCR_DOMAIN and SCR_SECRET_KEY
docker compose up -d --build
```

Caddy serves the app on your domain with automatic HTTPS. All data lives in
the `data` Docker volume.

## Backup and restore

Every night at 02:30 (`SCR_BACKUP_TIME`, local time) the worker makes a
backup: a consistent copy of the database, taken with SQLite's online backup
while the app runs, and all uploaded files, in one
`scr-backup-YYYYMMDD-HHMMSS.tar.gz` archive. The newest 14
(`SCR_BACKUP_KEEP`) are kept in `/data/backups`. Admins see the last backup,
its size and any error at the top of the Units page; every run is also listed
under **Settings > Backups**.

Those local copies are on the same disk as the data, so also set a remote in
`.env` (see `.env.example`): `SCR_BACKUP_REMOTE_TYPE` is `s3`, `sftp` or
`ftps`, with its address, credentials and `SCR_BACKUP_REMOTE_PATH`. Archives
are encrypted with `SCR_BACKUP_ENCRYPTION_PASSWORD` (rclone crypt) before
they leave the server, and the remote also keeps the newest
`SCR_BACKUP_KEEP`. **Keep a copy of the encryption password somewhere other
than the server**: without it the remote backups cannot be read.

Make a backup now, or list the ones on the remote:

```sh
docker compose exec web python manage.py backup
docker compose exec web python manage.py backup --list-remote
```

### Restore onto a fresh install

1. Install as in [Run it with Docker](#run-it-with-docker), with a `.env`
   that has the same `SCR_BACKUP_*` settings (including the encryption
   password), and start it once: `docker compose up -d --build`.
2. Stop the app so nothing writes during the restore:
   `docker compose stop web worker`
3. Restore the backup you want, from the remote:

   ```sh
   docker compose run --rm web python manage.py restore --remote scr-backup-20261018-023000.tar.gz
   ```

   or from an archive file on the host:

   ```sh
   docker compose run --rm -v "$PWD/scr-backup-20261018-023000.tar.gz:/tmp/restore.tar.gz:ro" web python manage.py restore /tmp/restore.tar.gz
   ```

4. Start again: `docker compose up -d`, and log in as before.

`restore` replaces the database and all uploaded files with the backup's,
then brings the database up to date with `migrate`. It refuses to run when
the database already has users or register data; add `--force` to restore
over an install that is in use (for example to go back to last night).

To copy a local backup off the server:
`docker compose cp web:/data/backups/scr-backup-20261018-023000.tar.gz .`

## Readings

An admin sets up what is read under **Settings > Reading types**: a name,
the unit type it applies to, the unit of measure (for example m³), the
number of decimals, and whether it is a cumulative meter. The water setup
(`load_sample_setup water`) adds "Vattenmätare" in whole m³. Reading types
are archived, not deleted.

Under **Readings** the board opens a round (for example "2026") with the
dates members may report in. The round page shows how many units have
reported, filters for those still missing, and lets the board type in values
row by row; a unit page lists that unit's readings with **Enter** or
**Correct**. For a cumulative meter the usage is the value minus the
previous reading. A value lower than last time, or far above the unit's
usual usage, is saved but marked **Check**. Every change is in the audit
log, shown under the reading's **Details**, and **Export as CSV** downloads
the round. Admin and Board can enter readings; Treasurer and Read-only can
see them.

## Member self-service

Members never get a password. Instead the board gives each household's
contact a personal link (`https://your-domain/m/…`). It opens a page, made
for phones and screen readers, where the member:

- enters the meter reading for the round, and can change it until the round
  closes, and
- sees their own and their household's contact details, and corrects their
  own phone, email and address.

Changes are saved straight away. They are in the audit log, marked with the
link they came through, and listed under **Readings > Recent self-service
changes**.

On a round's page, **Self-service links** makes links for all units, those
missing a reading, or those whose contact has no phone or email, and shows
them as printable letters (one per page, with a QR code) or as a list. A
unit page has **Print self-service letter** for one household. The links are
shown only on that page: the database keeps only a hash of each link, so
print straight away. Making a new link for a person stops their earlier one
for the same round, and staff can stop links one by one or all at once.

A link for a round works until the end of the round's closing day; other
links work for `SCR_SELF_SERVICE_LINK_DAYS` (30) days. Unknown, expired and
stopped links all show the same page. The member pages are rate-limited per
visitor address, are kept out of search engines (`noindex`) and send no
referrer. Letters use `SCR_BASE_URL` (by default `https://SCR_DOMAIN`) for
the address.

Links are personal data about the person they belong to: they are covered
by the per-person export and erasure tools planned for phase 8, together
with the person's other records.

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
