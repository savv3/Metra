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

- Agenda templates in the meetings add-on: the usual agenda of each kind of
  meeting, which a new meeting starts with (or another template, or an empty
  agenda). New installations get templates for annual and board meetings to
  adapt. Admins and the board edit them under Meetings > Agenda templates,
  Settings > Organisation, or Settings > Add-ons > Meetings.
- An add-on's page under Settings > Add-ons now also lists its own setting
  pages, such as the webhooks or agenda templates, and opens for add-ons that
  have such pages but no other settings.
- For plugin authors: `api.SettingsLink` takes `group`, the section of the
  Settings page the link goes in (`api.SETTINGS_GROUPS`, Integrations by
  default), and the link is also listed on the plugin's page under
  Settings > Add-ons.
- A test SMS (or test email) from the add-on's own settings page, for
  example Settings > Add-ons > 46elks SMS. It goes through that add-on even
  when another one is chosen for sending.
- Mailgun add-on (`metra-email-mailgun`, bundled and on by default): send
  email through Mailgun's API, EU region by default, with attachments,
  List-Unsubscribe and a tag per send-out. Set it up under Settings >
  Add-ons > Mailgun (or `METRA_MAILGUN_*`) and choose it under Settings >
  Email. Its signed webhooks record delivered, bounced and spam-reported
  email on the message, and a bounced address is flagged on the person's
  page until the address is changed.
- For plugin authors: `api.record_email_event()` with `api.DELIVERED`,
  `api.BOUNCED` and `api.COMPLAINED`, `api.email_from()`, and
  `api.SEND_OUT_HEADER` on the email of a send-out.
- Settings > Email (admins only, and a step of the setup wizard): choose how
  email is sent (SMTP or an add-on's sending service) and set the server,
  password, from address and the new Reply-To address, then send a test.
  Login codes, password links and invitations now go the same way as
  messages. The password is stored encrypted. `METRA_EMAIL_*` variables
  still work and win over the page, and the new `METRA_EMAIL_REPLY_TO` sets
  Reply-To from the environment.
- 46elks SMS settings in the app: the API username and password, sender and
  test mode are entered under Settings > Add-ons > 46elks SMS. The
  `METRA_ELKS_*` and `METRA_SMS_SENDER` variables still work and win when
  set. The setup wizard shows the sender 46elks actually uses.
- Settings > Add-ons: admins see the installed plugins with their version
  and turn each one on or off without a restart. A plugin that is off
  disappears from menus, pages, panels, help and the provider lists, and its
  data is kept.
- Plugin settings: a plugin lists its settings with `api.Setting` in
  `metra_settings` and gets a settings page under Settings > Add-ons; read
  them with `api.plugin_settings()`. Secrets are stored encrypted with the
  new `METRA_SETTINGS_KEY` (derived from `METRA_SECRET_KEY` when not set),
  never shown again and kept out of the audit log. A value set in the
  environment wins and is shown as locked.
- A Settings page of Metra's own at /settings/, grouped by task:
  Organisation, Register, Readings, Invoicing, Messages, Users and roles,
  Integrations, Backups and the Setup wizard, each entry with a short
  description. Everyone sees only the entries their role may change, and the
  menu shows Settings to anyone with at least one. The full admin is under
  Advanced, for admins and superusers. Links that plugins add with
  `api.add_settings_link` are listed under Integrations.
- Invoice settings now include the payment reference type and the reminder
  fee and days, which could not be changed before.
- A unit type can have a plural name. With exactly one unit type, the menu,
  the list heading and the buttons use that type's own name instead of
  "Units", and the unit list drops the type filter and column. Adding a unit
  now reads "Add: <type>" (Lägg till: …), which fixes the wrong grammatical
  form in Swedish and Finnish. The water association example fills the plural.
  Existing unit types have no plural name until an admin adds one.
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

- Messages to a tag ("Units or people with a tag") now also reach people who
  carry the tag themselves, not only the contacts of tagged units. When
  nobody matches, the check page says why, for example a tagged unit without
  contacts, and links to it.
- Backups are now snapshots: a copy of the database and uploads taken every
  night, when a new version starts, before a CSV import, before deleting a
  unit type or field, before a restore, and on demand. They are kept for 7
  days, then weekly for 4 weeks and monthly for 12 months; ones taken by hand
  stay until deleted. A new Backups page lists them, here and offsite.
- `manage.py backup` is now `manage.py snapshot`.
- A reading round is a draft or published; a published round opens and closes
  on its dates, so there is no status to forget to change. The round list
  shows Draft, Opens (date), Open until (date) or Closed. Existing open and
  closed rounds become published, drafts stay drafts. For plugin authors and
  API clients: `ReadingRound.status` is now a computed read-only value
  (`draft`, `upcoming`, `open`, `closed`; `upcoming` is new), the model has
  an `is_draft` field, and the `status` filter of `/api/v1/reading-rounds/`
  works on the computed state.
- The Units page no longer shows a backup box; backup problems are reported
  through the notification bell. Staff on an installation without required
  two-factor login see one banner, not two.
- Fee plans and invoice settings are linked from the setup wizard's invoicing
  step, the invoice run pages and the overdue page.
- The menu's Settings opens the new Settings page instead of the admin. Fee
  lines are no longer listed on their own in the admin (they are edited in
  their fee plan), and the admin's index shows non-superusers only the
  tables that are settings.
- New message and Message to one unit send on each person's preferred
  channel by default ("Each person's preferred channel"); SMS only, Email
  only, SMS or email, and Both are under "Other options". Urgent alerts still
  go by SMS and email to everyone.

### Upgrade notes

- `METRA_BACKUP_KEEP` and `METRA_BACKUP_DIR` are replaced by
  `METRA_BACKUP_KEEP_DAYS`, `METRA_BACKUP_KEEP_WEEKS` and
  `METRA_BACKUP_KEEP_MONTHS`; snapshots are kept in `/data/snapshots`.

### Fixed

- The API clients page showed its Swedish introduction twice.
- The help index listed every article twice.
- The setup wizard's email and SMS step shows a description of the SMS
  provider instead of its code name.
- Every send-out now follows each person's preferred channel, using one rule:
  those who prefer email get email and those who prefer SMS get an SMS, or
  the other one when they lack an address for it, and those who prefer post
  get a letter. Reading links and reminders used to go by SMS to everyone
  with a phone, and payment reminders by email to everyone with an address.
  Since email is the default preference, check people's preferred channel
  before the next send-out.
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
