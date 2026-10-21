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
For a server without internet access (behind a Cloudflare Tunnel, for
example), build the image elsewhere and deploy it over SSH with
`scripts/deploy.sh`, as [docs/deploying.md](docs/deploying.md) describes.

### First login

Create the first account with
`docker compose exec web python manage.py createsuperuser` and log in. Staff
must set up two-factor login with an authenticator app on their first login;
see [Users, roles and two-factor login](docs/user-guide.md#users-roles-and-two-factor-login).
After that, the [setup wizard](docs/user-guide.md#setup-wizard) takes you
through the rest.

## Backup and restore

Metra keeps **snapshots**: a consistent copy of the database, taken with
SQLite's online backup while the app runs, together with all uploaded files,
in one `metra-snapshot-<date>-<time>-<why>-<version>.tar.gz` file in
`/data/snapshots`. A snapshot is taken

- every night at 02:30 (`METRA_BACKUP_TIME`, local time),
- when a new version starts, before it changes the database,
- before a CSV import, before deleting a unit type or a field, and before a
  restore (if no snapshot can be taken, the action is stopped),
- whenever an admin clicks **Take a snapshot now** on the Backups page, or
  runs `manage.py snapshot`.

Every snapshot is kept for 7 days, then the newest of each week for 4 weeks
and the newest of each month for 12 months (`METRA_BACKUP_KEEP_DAYS`,
`METRA_BACKUP_KEEP_WEEKS`, `METRA_BACKUP_KEEP_MONTHS`). Snapshots taken by hand
on the Backups page are kept until an admin deletes them. Admins see the
snapshots, here and offsite, under **Settings > Backups** (also linked from the
backup status on the Units page).

The snapshots on the server are on the same disk as the data, so also set a
remote in `.env` (see `.env.example`): `METRA_BACKUP_REMOTE_TYPE` is `s3`,
`sftp` or `ftps`, with its address, credentials and
`METRA_BACKUP_REMOTE_PATH`. Every snapshot is then also sent offsite,
encrypted with `METRA_BACKUP_ENCRYPTION_PASSWORD` (rclone crypt) before it
leaves the server, and the remote keeps snapshots on the same schedule.
**Keep a copy of the encryption password somewhere other than the server**:
without it the offsite snapshots cannot be read.

Take a snapshot now, or list the ones offsite:

```sh
docker compose exec web python manage.py snapshot
docker compose exec web python manage.py snapshot --list-remote
```

### Restore from the app

An admin can restore a snapshot from **Settings > Backups**: **Restore…**
next to a snapshot asks for the password (or the two-factor code) again and
shows what the snapshot holds and how many units, people, readings, messages,
invoices and payments differ from now. Invoices issued and payments recorded
since the snapshot are listed and need an extra confirmation, as they may
already be in the bookkeeping. On confirmation Metra takes a snapshot of the
data as it is, shows a short "back in a moment" page to everyone, and the
worker restores the database and uploads, brings an older snapshot up to
date and records the restore (listed on the Backups page and in the audit
log). If anything goes wrong, the data from just before is put back. An
offsite snapshot is downloaded first; a snapshot taken by a newer version of
Metra is refused. Only Admin may restore ("Can restore a snapshot").

### Restore onto a fresh install

1. Install as in [Run it with Docker](#run-it-with-docker), with a `.env`
   that has the same `METRA_BACKUP_*` settings (including the encryption
   password) and the same `METRA_SECRET_KEY` and `METRA_SETTINGS_KEY`
   (without them, secrets saved in the app, such as plugins' API keys,
   cannot be read and must be entered again), and start it once: `docker compose up -d --build`.
2. Stop the app so nothing writes during the restore:
   `docker compose stop web worker`
3. Restore the snapshot you want, from offsite:

   ```sh
   docker compose run --rm web python manage.py restore --remote metra-snapshot-20261018-023000-nightly-0.2.0.tar.gz
   ```

   or from a snapshot file on the host:

   ```sh
   docker compose run --rm -v "$PWD/metra-snapshot-20261018-023000-nightly-0.2.0.tar.gz:/tmp/restore.tar.gz:ro" web python manage.py restore /tmp/restore.tar.gz
   ```

4. Start again: `docker compose up -d`, and log in as before.

`restore` replaces the database and all uploaded files with the snapshot's,
then brings the database up to date with `migrate`. It refuses to run when
the database already has users or register data; add `--force` to restore
over an install that is in use (for example to go back to last night). It
then first takes a snapshot of the current data; `--skip-snapshot` restores
without one, for a database too damaged to copy.

To copy a snapshot off the server:
`docker compose cp web:/data/snapshots/metra-snapshot-20261018-023000-nightly-0.2.0.tar.gz .`

## Email and SMS

**Email** is set up by an admin under **Settings > Email** (also a step of
the setup wizard): SMTP with the mail server, port, encryption, user name and
password of the organisation's own mail account, or a sending service added
by an add-on, plus the from address and an optional Reply-To. The password is
stored encrypted (see `METRA_SETTINGS_KEY`). All email goes that way,
including login codes and invitations. **Send test email** on the same page
checks it. Until it is set up, email is off in production and printed to the
console in development.

The `METRA_EMAIL_*` variables still work and win over the page field by
field (`METRA_EMAIL_HOST`, `METRA_EMAIL_PORT`, `METRA_EMAIL_USER`,
`METRA_EMAIL_PASSWORD`, `METRA_EMAIL_USE_TLS` or `METRA_EMAIL_USE_SSL`,
`METRA_EMAIL_FROM` and `METRA_EMAIL_REPLY_TO`); the page shows those fields
as locked. When `METRA_EMAIL_HOST` or `METRA_EMAIL_BACKEND` is set, the
environment also decides how email is sent, so an existing install keeps
working unchanged.

**Mailgun** is an add-on for sending through [Mailgun](https://www.mailgun.com)
instead of SMTP, with delivery and bounce reports. It comes with Metra and is
on by default, but sends only once chosen:

1. At Mailgun, add and verify a sending domain (for example `mg.example.fi`),
   in the EU region unless the account is in the US, and create a sending API
   key for it.
2. In Metra, open **Settings > Add-ons > Mailgun** and enter the **Sending
   domain**, **API key** and **Region**.
3. At Mailgun, under *Webhooks*, add `<METRA_BASE_URL>/plugins/mailgun/events/`
   for *Delivered messages*, *Permanent failure* and *Spam complaints*, and
   copy the **HTTP webhook signing key** into **Webhook signing key** in
   Metra.
4. Under **Settings > Email** choose **Mailgun**, set the from address (on
   the sending domain) and send a test email.

Mailgun then reports each email: delivered, bounced (the message is marked
failed and the person's address is flagged as bouncing until it is changed)
or marked as spam. Each send-out's email is tagged `send-out-<id>` at Mailgun.
The settings can instead be set with `METRA_MAILGUN_DOMAIN`,
`METRA_MAILGUN_API_KEY`, `METRA_MAILGUN_REGION` (`eu` or `us`) and
`METRA_MAILGUN_WEBHOOK_KEY`, which win over the page. Mailgun receives each
recipient's address and the email's text; list it as a processor in your GDPR
records.

**SMS** goes through [46elks](https://46elks.com):

1. Create an account at 46elks and add credit. Messages are paid per SMS.
2. In Metra, open **Settings > Add-ons > 46elks SMS** and enter the
   **API username** and **API password** from *Account* at 46elks.
3. Enter the **Sender**, the name shown on the phone (up to 11 letters and
   digits, for example `Vatten`), or a number you have at 46elks. Without
   one, `METRA_SMS_SENDER` or "Register" is used.
4. Optional: tick **Test mode** to have 46elks check messages without
   sending them or charging, while you try the setup.
5. Send a test SMS from the setup wizard's messaging step.

Numbers written without a country code (`040 123 4567`) get
`METRA_SMS_COUNTRY_CODE`, 358 (Finland and Åland) by default. The settings
can instead be set on the server with `METRA_ELKS_API_USER`,
`METRA_ELKS_API_PASSWORD`, `METRA_SMS_SENDER` and `METRA_ELKS_DRY_RUN`; a
variable that is set wins over the page and shows there as locked, so
existing installs keep working unchanged.

Delivery reports come back automatically when the app is reachable over
HTTPS at `METRA_BASE_URL`. 46elks posts them to a secret address the app
derives from `METRA_SECRET_KEY`, so they need no setup. Without SMS settings,
links go by email or letter. 46elks receives the phone number and text of
each SMS; list it as a processor in your GDPR records. 46elks support is the
bundled [metra-sms-46elks](plugins/sms-46elks) plugin, on by default; other
providers can be added as plugins (see [docs/plugins.md](docs/plugins.md)).

## Plugins

Plugins are pip-installable packages that add pages, menu items, panels on
unit and person pages, or SMS and email providers. Install them through
`METRA_PLUGIN_PACKAGES` (Docker build) or pip, and enable them by name in
`METRA_PLUGINS`; nothing loads unless it is listed. An admin then turns
installed plugins on and off, and edits their settings, under **Settings >
Add-ons**, with no restart. Plugins run with full
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
