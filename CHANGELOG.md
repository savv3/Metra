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

## [0.9.0] - 2026-11-25

### Changed

- The admin pages show the side list of every table again (taken away in
  0.8.0).
- Every user must now use two-factor login, not only staff: board,
  treasurer and read-only users see members' personal details too.
  `METRA_REQUIRE_MFA_FOR=staff` keeps the old behaviour.
- Plain http is redirected to https and pages send an HSTS header in
  production (`METRA_SSL_REDIRECT`, `METRA_HSTS_SECONDS`).

### Security

- Invitation and password links and newsletter unsubscribe links are no
  longer written in full to the access log.

### Upgrade notes

- Users without two-factor login are asked to set it up at their next login,
  before they can use the app. Tell them before upgrading, or set
  `METRA_REQUIRE_MFA_FOR=staff` until they are ready.
- If nothing in front of Metra serves https, set `METRA_SSL_REDIRECT=false`.

## [0.8.1] - 2026-11-24

### Fixed

- The cards on the Settings page have even padding again; the text no
  longer sits against the card's edge.

## [0.8.0] - 2026-11-24

### Added

- Bookkeeping: exports and retention. **Export the books** on a year's page
  downloads the year as a ZIP for an accountant or for keeping outside
  Metra: the chart of accounts with balances and every posted voucher line
  as CSV, the receipts, a README, and the year in SIE 4, which is also
  offered on its own. Exports are recorded in the audit log. A new page,
  **How long the books are kept**, shows for every year how long its books
  (10 years) and vouchers and receipts (6 years from the end of the calendar
  year) must be kept, and whether anything may be removed yet; nothing is
  removed automatically. The books, receipts and invoices are kept for
  these periods even when a person is erased.

- Bookkeeping: locking and year-end. Months are locked once reported, and
  nothing can be posted into a locked period (records from invoicing dated
  there are booked on the first open day, with a note). **Close the year**
  goes through the year-end: depreciation by plan from a new **Fixed
  assets** register, accrual of income invoiced after the year, the bank
  statement balances, and the notes and signers. Closing locks the year for
  good, keeps its chart of accounts as it was, and opens the next year with
  the closing balances, the result carried to equity; accruals are reversed
  on its first day. Errors found later are corrected in the open year and
  listed in its notes. The **Year-end package** is one PDF for the auditor:
  the statements, notes, signature page, balance sheet specifications, list
  of books and material, chart of accounts, journal and ledger.
- Bookkeeping: invoiced income across the year end is shared by supply
  days. Supplies that straddle the year end are accrued in part, and
  invoices issued in the year for supplies after it are deferred. If
  invoices change after the accrual voucher was made, the year-end page and
  the closing warn, and **Make the accrual voucher** books only the
  difference.

### Changed

- Adding a user under Settings > Users invites them by email instead of
  asking for a password: the new user chooses their own password from a
  one-time link (and admins then set up two-factor login). When email is not
  set up, the link is shown once to send by hand. **Send a new invitation
  link** in the list of users sends a fresh one to someone who has not chosen
  a password yet. For hosting tools, `create_organisation --send` emails the
  first admin's link from the install, and the new `invite_user` command makes
  a new link (`--send` to email it).

- Installs made with `docker/new-instance.sh` never start their own
  `caddy` service, which only got in the way next to a tunnel or a proxy on
  the host. `scripts/deploy.sh` labels the image it builds with its version,
  as the published images are, so metra-admin accepts it as a release.

- Buttons sit in the same places on every page: one blue button for the
  main action, page actions at the top right, section actions next to the
  section heading, and **Cancel** as a link. Pages below the first level show
  the way back above the heading (for example **Fakturor › Faktureringsomgångar**)
  instead of a back button.
- An invoice run's page shows three steps, **Check**, **Issue** and **Send**,
  each with its own button, in the order they are done.
- **Invoices**, **Overdue invoices** and **Invoice runs** are tabs, and
  **New invoice run** is on the Invoices page.
- A unit's page: **Archive** is under **More**, the add-contact form opens
  from **Add contact**, empty fields are left out, and the history is folded
  away.
- **Settings** is a two-column grid, and some links say what still needs
  doing: a missing bank account or from address, no backup yet, or when the
  last backup was taken.
- Settings that open in the Django admin now have Metra's colours, no side
  list of every table, and **Back to Metra settings** at the top; saving the
  organisation or invoice settings returns to the Settings page.
- **Settings > Add-ons** shows each add-on as a card with an on/off switch,
  grouped into features, sending services and integrations, with links to
  its pages and settings and a note when it is in use or not set up yet.
  Turning one off first says what changes. The official add-ons'
  descriptions are translated.
- A closed reading round no longer offers to send links, and its rows show
  each value with **Correct** instead of an input and a Save button per row.
  **Export as CSV** moved to the top of the round page, and the SMS service
  is named in words instead of by its code name.
- **Send-outs**: **New message** is the main button, and **Urgent alert** is
  no longer red (red is kept for deleting and restoring). Dates in tables no
  longer break over two lines, and the two-factor banner is smaller.
- On a reading round's page, the units table and its filters have their own
  **Readings** heading, so they no longer run into the **Send links** buttons.

### Fixed

- Bookkeeping: account names from the chart template now show in the
  display language (Swedish, English or Finnish), also in books already
  started in another language. Names the treasurer has changed stay as
  written.
- The reading box on the member page and the staff reading form shows a saved
  reading with the reading type's decimals (17, not 17,000).

## [0.7.1] - 2026-11-23

### Removed

- The **Manage add-ons** link in the menu from 0.7.0. Add-ons are under
  **Settings > Add-ons**, as before.

## [0.7.0] - 2026-11-23

### Added

- Meetings: **Send invitations** opens the invitation as an email with the
  agenda PDF and a calendar file (.ics) attached, and sending it marks the
  meeting as called. Everyone invited gets an automatic reminder a set
  number of days before the meeting (**Reminder, days before**, 3 unless
  changed), or one sent by hand. When the date, time or place changes after
  the invitations, the meeting page offers an updated invitation whose
  calendar file moves the meeting in people's calendars.
- Plugin API: `api.send_message()` sends a message to (person, unit) pairs
  in the background, `api.message_draft()` takes `channels` and `source`,
  send-outs have a `source` a plugin finds them by (`api.MessageBatch`),
  `api.events.message_sent` is sent when a message to many people starts
  going out, and `api.plugin_enabled()` tells a periodic task whether its
  plugin is on. Calendar files (.ics) can be attached to messages.

### Changed

- The menu always has **Manage add-ons** under **Add-ons** for admins, so
  add-ons are one click away instead of under Settings.
- **Settings > Email** shows only the fields for the chosen way of sending:
  the SMTP fields only for SMTP, and for an add-on such as Mailgun a link to
  the add-on's page where its sending domain and API key are entered, with
  whether they are filled in. Saving an add-on that lacks them warns.
- The **From address** and **Reply-To address** take a name as well as an
  address, such as `Kasvikens vatten <noreply@example.fi>`.

### Fixed

- A test email, from **Settings > Email** or an add-on's page, is no longer
  sent before a from address is set (it went out as `register@localhost`).
  An email add-on's page says when email is not sent through it yet.

## [0.6.0] - 2026-11-20

### Added

- Demo sites: with `METRA_DEMO=true` an install becomes a public demo with a
  demo/demo login shown on the login page, a banner on every page, no email
  or SMS, and locked accounts. The worker deletes everything and loads the
  made-up demo data again every night (`METRA_DEMO_RESET_TIME`, default
  03:00); `manage.py reset_demo` does it by hand and refuses to run on any
  other install.
- `NavItem` takes a `group` (one of `api.NAV_GROUPS`) and an `icon` (one of
  `api.NAV_ICONS`), so an add-on's menu link goes in the right section of the
  sidebar.

- Invoices state their delivery date or period, printed on the invoice
  (AVL 209 e §). An invoice run asks for the period its fees are for, and
  a single draft can have its own; without one, the invoice date counts.
  VAT follows the delivery, not the invoice date.

- The Bookkeeping add-on (`METRA_PLUGINS=bookkeeping`, off by default):
  double-entry books under the Finnish Accounting Act, with a chart of
  accounts from a template for an association or a cooperative, financial
  years, numbered vouchers with receipts, corrections by reversing
  vouchers, and the journal, general ledger and trial balance. Issued
  invoices, credit notes, payments and reminder fees are booked
  automatically once the treasurer chooses the accounts and the start day
  under Settings > Bookkeeping of invoices, each voucher pointing to its
  invoice and the invoice page showing its vouchers. VAT is booked at the
  rate in force on the day, with dated VAT registration and separate
  accounts for sales VAT, purchase VAT and the VAT settlement. The
  income statement and balance sheet follow the PMA decree's formats
  (the non-profit format for associations), in Finnish or Swedish with
  the previous year beside them, and show the size class; a budget per
  account is followed up against the books; a VAT summary per VAT period
  counts VAT by the supply date and advance payments, and says when it is
  not ready for the return. Every report is also a PDF and a CSV file.
  The year-end follows.
- Plugin authors: an add-on's AppConfig can define `turn_off_refused()` to
  keep it from being turned off, with the reason shown under Settings >
  Add-ons.
- Plugin authors: the `api.events.reminder_sent` event, sent when a payment
  reminder is made; `api.add_invoice_panel` for a section on invoice pages;
  and `api.PaymentReminder` among the records.

### Changed

- The main menu is a sidebar on the left, in sections (Register, Finance,
  Communication and Add-ons) with Settings and Help at the bottom, so it no
  longer overflows when add-ons add links. On phones the menu button in the
  top bar opens it.

## [0.5.0] - 2026-10-25

### Added

- `METRA_EMAIL_BACKEND` can name an add-on's email provider, such as
  `mailgun`, so a hosting provider can set up Mailgun for a new install with
  environment variables only.

### Fixed

- Choosing a password through a setup or reset link marks the person's email
  address as verified. Before, an admin made by `create_organisation` or
  invited by email could not turn on two-factor login ("verify your email
  address first") on an install without email.

## [0.4.0] - 2026-10-23

### Upgrade notes

- Installs made with `docker/new-instance.sh` (several organisations on one
  server): copy the new `compose.yaml` and `docker/upgrade.sh` into place, as
  `docs/multiple-organisations.md` describes, so the health check uses the
  install's own host name.

### Added

- `manage.py create_organisation --name ... --admin-email ...`: names the
  organisation of a fresh install and creates its first admin, printing a
  link where they choose a password, so an install can be set up without
  `createsuperuser`.
- `/status`: version, backup state and add-ons for a tool that runs many
  installs, only with the token in `METRA_STATUS_TOKEN` (no personal data).
  `/healthz` now also reports the version.
- `manage.py load_demo_data`: fills a fresh installation with a made-up water
  association (households, contacts, readings, invoices) for demos and trials.
  It refuses to run when units already exist and sends nothing.
- Plugin API: `BillingSettings`, `FeePlan` and `FeeLine` records, so an
  add-on can set up what units are invoiced for.
- `SECURITY.md`: how to report a security problem privately, and which
  versions get fixes.

### Fixed

- The container health check and `upgrade.sh` now ask `/healthz` with the
  install's own host name (`METRA_DOMAIN`). With `METRA_ALLOWED_HOSTS` set to
  only that name, as `new-instance.sh` does, they were refused, so the worker
  never started and every upgrade went back to the old image.

## [0.3.0] - 2026-10-21

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
- `docker/upgrade.sh` takes its snapshot with `manage.py backup` when the
  running version is older than 0.3.0, so upgrading from 0.2.0 works.

### Upgrade notes

- `METRA_BACKUP_KEEP` and `METRA_BACKUP_DIR` are replaced by
  `METRA_BACKUP_KEEP_DAYS`, `METRA_BACKUP_KEEP_WEEKS` and
  `METRA_BACKUP_KEEP_MONTHS`; snapshots are kept in `/data/snapshots`.
  Remove the old variables from `.env`.
- `manage.py backup` is now `manage.py snapshot`; update any cron job or
  script that calls it.
- Email and 46elks SMS can now be set up in the app. Any `METRA_EMAIL_*`,
  `METRA_ELKS_*` or `METRA_SMS_SENDER` variable in `.env` still wins and
  shows as locked on the settings page; empty them to manage the settings
  in the app instead.
- Check people's preferred channel before the next send-out (see Fixed).

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
