# Changelog

All notable changes to Metra are listed here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[semantic versioning](https://semver.org/) as described in
[docs/releasing.md](docs/releasing.md).

Every pull request that changes what users, admins or plugin authors see adds
a line under **Unreleased**. A release renames that section to the version
and date. **Upgrade notes** says what an admin must do when upgrading
(beyond pulling the new image), and is left out when there is nothing.

## [Unreleased]

### Added

- A Settings page of Metra's own at /settings/, grouped by task:
  Organisation, Register, Readings, Invoicing, Messages, Users and roles,
  Integrations, Backups and the Setup wizard, each entry with a short
  description. Everyone sees only the entries their role may change, and the
  menu shows Settings to anyone with at least one. The full admin is under
  Advanced, for superusers only. Links that plugins add with
  `api.add_settings_link` are listed under Integrations.
- Invoice settings now include the payment reference type and the reminder
  fee and days, which could not be changed before.

- The meetings plugin (`METRA_PLUGINS=meetings`, off by default): annual,
  extraordinary and board meetings with an agenda, the notice sent as a
  message with the agenda attached, attendance from the register with votes
  per unit or per person, minutes and decisions per item, and a minutes PDF
  that the minute checkers approve in the app. Approved minutes no longer
  change and are listed on the members' personal pages.
- For plugin authors: `api.render_pdf`, `api.message_draft` (open the New
  message form filled in, with files attached), member page panels
  (`api.add_member_panel`), `api.member_link` and friends for serving
  members through their personal link, and `api.Organisation`.

- Admins can restore a snapshot from the Backups page, after confirming
  their login again. They see what the restore would remove, confirm
  separately when invoices or payments would be removed, and the site shows
  a "back in a moment" page while the worker restores. A snapshot of the
  data just before is taken first and put back if the restore fails.
- A Help section with short guides in Swedish, English and Finnish: getting
  started, the register, readings, messages and newsletters, invoicing,
  backups, and roles and two-factor login. Every page has a Help link to the
  guide for it, the guides can be searched, and plugins can add their own.
- Notifications: a bell next to your name shows how many unread
  notifications you have, and a Notifications page lists them. Each can be
  opened, marked as read or unread, or dismissed, and there is "mark all as
  read". Staff are notified about failed (and, if they ask, nightly)
  snapshots, restores, SMS and email that could not be delivered, readings
  and changes members send in, invoices that became overdue, and webhooks
  that were given up. Each person chooses what they get under Notification
  settings. Read and dismissed notifications are removed after 90 days.
- Plugins can send notifications: `api.NotificationKind`,
  `api.add_notification_kind` and `api.notify`.

### Changed

- Backups are now snapshots: a copy of the database and uploads taken every
  night, when a new version starts, before a CSV import, before deleting a
  unit type or field, before a restore, and on demand. They are kept for 7
  days, then weekly for 4 weeks and monthly for 12 months; ones taken by hand
  stay until deleted. A new Backups page lists them, here and offsite.
- `manage.py backup` is now `manage.py snapshot`.
- The menu's Settings opens the new Settings page instead of the admin. Fee
  lines are no longer listed on their own in the admin (they are edited in
  their fee plan), and the admin's index shows non-superusers only the
  tables that are settings.

### Upgrade notes

- `METRA_BACKUP_KEEP` and `METRA_BACKUP_DIR` are replaced by
  `METRA_BACKUP_KEEP_DAYS`, `METRA_BACKUP_KEEP_WEEKS` and
  `METRA_BACKUP_KEEP_MONTHS`; snapshots are kept in `/data/snapshots`.

### Fixed

- New message and Message to one unit no longer ask for an SMS text when the
  message goes by email only: the form shows only the texts the chosen
  channels need, and checks only those.
- `scripts/deploy.sh` logs in to the server once and reuses that SSH
  connection, so a firewall's intrusion prevention no longer mistakes a
  deploy for an SSH scan and blocks the laptop.
- The web container no longer logs "Permission denied: '/app/.gunicorn'" at
  start; gunicorn's control socket, which Metra does not use, is turned off.

## [0.2.0] - 2026-10-19

### Added

- The release version is shown in the account menu.
- Plugins declare the plugin API versions they work with (`metra_api`), and a
  plugin made for another API version stops the app with a clear error.
- Tagged releases publish Docker images to the GitHub container registry.
- `scripts/deploy.sh` builds a release on a laptop and deploys it over SSH to
  a server without internet access; `docker/upgrade.sh` on the server takes a
  backup first and goes back to the previous image if the new one is not
  healthy. See `docs/deploying.md`.

## [0.1.0]

Development version before the first release: everything built
from the start of the project until versioning was set up.
