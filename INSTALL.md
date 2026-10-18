# Installing and running Metra

[Back to the README](README.md)

This page covers installing, configuring, backing up and developing Metra.
How to use the app is in the [user guide](docs/user-guide.md). Every setting
is an environment variable starting with `METRA_`, listed with a short
explanation in [.env.example](.env.example).

## Run it with Docker

```sh
cp .env.example .env    # then set METRA_DOMAIN and METRA_SECRET_KEY
docker compose up -d --build
```

Caddy serves the app on your domain with automatic HTTPS. All data lives in
the `data` Docker volume.

To host several organisations on one server, each as its own separate
install, see [docs/multiple-organisations.md](docs/multiple-organisations.md).

### First login

Create the first account with
`docker compose exec web python manage.py createsuperuser` and log in. Staff
must set up two-factor login with an authenticator app on their first login;
see [Users, roles and two-factor login](docs/user-guide.md#users-roles-and-two-factor-login).

### Upgrading from SmallCompanyRegister

Metra was called SmallCompanyRegister, and its settings were prefixed `SCR_`.
An existing `.env` keeps working unchanged: every `SCR_` setting is still
read, and a `METRA_` setting wins when both are set. Rename them at your own
pace. The data volume, database and older `scr-backup-*` archives are used
as before. The image is now tagged `metra:latest`; an install that loads a
prebuilt image should tag it `metra:latest`, or set `METRA_IMAGE` to the old
tag.

## Backup and restore

Every night at 02:30 (`METRA_BACKUP_TIME`, local time) the worker makes a
backup: a consistent copy of the database, taken with SQLite's online backup
while the app runs, and all uploaded files, in one
`metra-backup-YYYYMMDD-HHMMSS.tar.gz` archive. The newest 14
(`METRA_BACKUP_KEEP`) are kept in `/data/backups`. Admins see the last backup,
its size and any error at the top of the Units page; every run is also listed
under **Settings > Backups**.

Those local copies are on the same disk as the data, so also set a remote in
`.env` (see `.env.example`): `METRA_BACKUP_REMOTE_TYPE` is `s3`, `sftp` or
`ftps`, with its address, credentials and `METRA_BACKUP_REMOTE_PATH`. Archives
are encrypted with `METRA_BACKUP_ENCRYPTION_PASSWORD` (rclone crypt) before
they leave the server, and the remote also keeps the newest
`METRA_BACKUP_KEEP`. **Keep a copy of the encryption password somewhere other
than the server**: without it the remote backups cannot be read.

Make a backup now, or list the ones on the remote:

```sh
docker compose exec web python manage.py backup
docker compose exec web python manage.py backup --list-remote
```

### Restore onto a fresh install

1. Install as in [Run it with Docker](#run-it-with-docker), with a `.env`
   that has the same `METRA_BACKUP_*` settings (including the encryption
   password), and start it once: `docker compose up -d --build`.
2. Stop the app so nothing writes during the restore:
   `docker compose stop web worker`
3. Restore the backup you want, from the remote:

   ```sh
   docker compose run --rm web python manage.py restore --remote metra-backup-20261018-023000.tar.gz
   ```

   or from an archive file on the host:

   ```sh
   docker compose run --rm -v "$PWD/metra-backup-20261018-023000.tar.gz:/tmp/restore.tar.gz:ro" web python manage.py restore /tmp/restore.tar.gz
   ```

4. Start again: `docker compose up -d`, and log in as before.

`restore` replaces the database and all uploaded files with the backup's,
then brings the database up to date with `migrate`. It refuses to run when
the database already has users or register data; add `--force` to restore
over an install that is in use (for example to go back to last night).

To copy a local backup off the server:
`docker compose cp web:/data/backups/metra-backup-20261018-023000.tar.gz .`

## Email and SMS

**Email** goes out over SMTP when `METRA_EMAIL_HOST` is set, with
`METRA_EMAIL_PORT`, `METRA_EMAIL_USER`, `METRA_EMAIL_PASSWORD`, `METRA_EMAIL_USE_TLS`
or `METRA_EMAIL_USE_SSL`, and `METRA_EMAIL_FROM` as the sender. Without a host,
email is off in production and printed to the console in development.

**SMS** goes through [46elks](https://46elks.com):

1. Create an account at 46elks and add credit. Messages are paid per SMS.
2. Under *Account* copy the **API username** and **API password** into
   `METRA_ELKS_API_USER` and `METRA_ELKS_API_PASSWORD`.
3. Set `METRA_SMS_SENDER` to the name shown on the phone (up to 11 letters
   and digits, for example `Vatten`) or to a number you have at 46elks.
4. Numbers written without a country code (`040 123 4567`) get
   `METRA_SMS_COUNTRY_CODE`, 358 (Finland and Åland) by default.
5. Optional: set `METRA_ELKS_DRY_RUN=true` to have 46elks check messages
   without sending them or charging, while you try the setup.
6. Restart: `docker compose up -d`.

Delivery reports come back automatically when the app is reachable over
HTTPS at `METRA_BASE_URL`. 46elks posts them to a secret address the app
derives from `METRA_SECRET_KEY`, so they need no setup. Without SMS settings,
links go by email or letter. 46elks receives the phone number and text of
each SMS; list it as a processor in your GDPR records. Other providers can
be added in code: see `apps/messaging/registry.py`.

## Plugins

Plugins are pip-installable packages that add pages, menu items, panels on
unit and person pages, or SMS and email providers. Install them through
`METRA_PLUGIN_PACKAGES` (Docker build) or pip, and enable them by name in
`METRA_PLUGINS`; nothing loads unless it is listed. Plugins run with full
trust, so install only ones you trust. See [docs/plugins.md](docs/plugins.md)
and the [example plugin](plugins/example).

## Develop locally

Needs Python 3.13, [uv](https://docs.astral.sh/uv/) and GNU gettext, and
Pango for invoice PDFs (see [PDF library](#pdf-library)).

```sh
uv sync
export METRA_DEBUG=true
uv run python manage.py migrate
uv run python manage.py compilemessages --ignore=.venv
uv run python manage.py createsuperuser
uv run python manage.py load_sample_setup water   # optional: the water association setup
uv run python manage.py runserver
```

Log in at http://localhost:8000. Record types and their custom fields are set
up under **Settings** (the Django admin); units and people are managed on the
main pages.

### PDF library

PDFs are made with [WeasyPrint](https://weasyprint.org), which the Docker
image includes. For local development install its Pango library
(`brew install pango` on a Mac, `apt install libpango-1.0-0
libpangoft2-1.0-0` on Debian or Ubuntu); on a Mac also run the app with
`DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` so Python finds it. Without
Pango everything works except making PDFs, and the PDF tests are skipped.

### Checks

Run the checks with `uv run pytest` and `uv run ruff check .`. More
conventions are in [AGENTS.md](AGENTS.md).
