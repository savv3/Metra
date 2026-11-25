# Build plans for finished phases

The pull-request plans for phases 1 to 9, moved out of
[architecture.md](../architecture.md) once the phases were done. Kept for
reference; the code and `CHANGELOG.md` are the record of what was built.

## Phase 1 build plan

Phase 1 is done when an admin can install with `docker compose up`, set up
the water association, import 50 households from CSV, search and edit them,
and see a nightly encrypted backup land on S3 or SFTP. It ships as five pull
requests.

| PR | Contents | Done when |
| --- | --- | --- |
| 1. Skeleton | Django 5.2 LTS, uv, ruff, pytest, GitHub Actions CI, MIT licence, README, Swedish and English translations, SQLite in WAL mode, Dockerfile and Compose with web, worker and Caddy | `docker compose up` shows a translated start page and CI is green |
| 2. Register | Organisation settings, unit types with custom fields, units, people, roles, tags; searchable list, add, edit and archive pages with HTMX | An admin can create the "Household" type and register households with contacts |
| 3. Access and audit | Two-factor login for admins, roles for admin, board, treasurer and read-only, audit log of changes and views | Each role sees only what it should; every change is logged |
| 4. CSV import and export | Upload, map columns, preview with validation errors, import; export any filtered list | 50 households import cleanly, and bad rows are reported, not skipped silently |
| 5. Backups | SQLite online backup, encrypted with rclone, sent to S3, SFTP or FTPS nightly; dashboard status; documented restore | A restore from last night's backup brings the register back on a fresh install |

A sample "water association" configuration ships as a ready-made setup that
can be loaded on first start.

## Phase 2 build plan

Phase 2 is done when the board can open a reading round, send every
household a personal link by SMS or email (or print a letter for those with
neither), and see who has reported and who needs a reminder. It ships as
four pull requests; the last one adds the plugin core (see
[Plugins](../architecture.md#plugins)).

| PR | Contents | Done when |
| --- | --- | --- |
| 7. Readings | Reading types set up by an admin (unit of measure, decimals, cumulative meter), reading rounds, one reading per unit and round; usage from the previous reading with warnings for values that look wrong; round progress with a filter for missing units; entry and correction from the round and the unit page; history from the audit log; CSV export | The board enters 50 households' meter readings for 2026 and exports the round |
| 8. Self-service links | Personal links with a random token stored only as a hash, expiring and revocable; a public, mobile-first page where a member enters the reading and corrects their own contact details; changes logged with the link; printable letters with a QR code | A member opens the link on a phone, reports the meter, fixes their email, and the board sees it |
| 9. Sending links and reminders | A messaging app with a provider interface (SMTP email, 46elks SMS, console for development), message records with delivery status, editable templates, sending a round's links and reminders to missing units through the worker | Links go out by SMS, falling back to email, falling back to the print list, and a reminder reaches only those who have not reported |
| 10. Plugin core | Entry-point loader, `METRA_PLUGINS`, hook registry with the first extension points (navigation, unit and person panels, messaging providers), example plugin and docs | The example plugin, enabled with `METRA_PLUGINS`, adds a menu item, a unit panel and an SMS provider, and the tests load it |

### Readings

A **reading type** says what is read from which unit type, for example
"Vattenmätare" in m³ from households. For a cumulative meter the usage of a
round is the value minus the unit's most recent earlier reading of the same
type (rounds without a reading are skipped). A value lower than the previous
one, or a usage more than three times the unit's average over its last three
rounds, is saved but marked for a check. A round expects every active,
non-archived unit of the type, plus any unit that has a reading in it.

### Self-service links

A link holds a random 256-bit token. Only its SHA-256 hash is stored, so the
token exists only in the letter or message that carries it, and a copy of
the database cannot open anyone's page. A link belongs to one unit, one
person and optionally a round. It expires at the end of the round's closing
day, or after `METRA_SELF_SERVICE_LINK_DAYS`, and can be stopped. Changes made
through a link are applied directly and audit-logged with the link's id in
`additional_data`. Links, and the audit entries they produce, are personal
data of the person they belong to, so the export and erasure tools (module
8) must include them. Member pages are rate-limited with Django's cache (files
under `METRA_DATA_DIR`, no extra service), with stricter limits for unknown
tokens.

### Messaging

`apps.messaging` keeps a record of every message (channel, recipient,
text, status, the provider's id), grouped in send-outs. Providers are
classes registered by channel and name in `apps.messaging.registry`; an
installation picks one per channel by setting. The registry is the
messaging extension point that the plugin core (PR 10) opens to plugins.
Built-in: email through Django (SMTP or console), SMS through 46elks, and
console and dummy SMS providers for development and tests. Sending runs in
Huey tasks. A link's token is only in the message that goes out; the
stored copy has a placeholder. Messages are personal data of their
recipient and are covered by the export and erasure tools. Phase 3 builds
group messaging on the same records and providers.

## Phase 3 build plan

Phase 3 is done when an admin can send an urgent alert to every household
in a minute, visitors find the organisation's contact details on its public
page, and members can subscribe to newsletters and unsubscribe from them.

| PR | Contents | Done when |
| --- | --- | --- |
| 11. Messages and urgent alerts | Staff write one message to everyone, a tag, a unit type or the filtered unit list (all contacts or main contact only) by SMS, email or both; recipient and SMS counts and a confirmation step; urgent alert mode on both channels with a list of who cannot be reached; live delivery status | A water-leak alert reaches every household with a phone or email, and the board knows whom to call |
| 12. Public organisation page | Public contact fields and logo in organisation settings; a translated, mobile-first landing page at `/` (can be switched off, the only page search engines may index); a notice banner an alert can publish; the contact block on member pages, in letters and as message placeholders | A visitor on a phone finds the emergency number and the current notice |
| 13. Newsletters with consent | Per-person consent with time and source, changeable on the self-service page; newsletters by email to consenting people only, with an unsubscribe link in every one | A newsletter reaches only those who said yes, and one click unsubscribes |

Newsletters reuse the send-out records and the email provider. Consent is
an append-only list of answers per person (`ConsentRecord`: yes or no, time,
source, who recorded it); the newest answer counts and none means no. The
unsubscribe link is a signed token naming the person, so it needs no table.
Messages and alerts in PR 11 are service messages about the organisation's
own service, sent on the basis of membership, so they need no marketing
consent. Newsletters (PR 13) do.

## Phase 4 build plan

Phase 4 is done when the treasurer can turn the year's fee plan and meter
readings into numbered invoices, send them as PDFs by email or print, and
follow up payments, all within the Finnish rules for invoices and
bookkeeping. Payments are marked by hand; importing bank files can come
later. It ships as three pull requests.

| PR | Contents | Done when |
| --- | --- | --- |
| A. Fee plans and invoices | Invoice settings (VAT status, IBAN and BIC, payment terms, numbering, late interest and footer text); fee plans with fixed fees and usage fees per reading type (optional price tiers and per-field conditions, VAT rate per line); invoice runs that build draft invoices from the plans and a period's readings; draft review and editing; issuing with gapless numbering and a locked copy of seller and buyer; credit notes; invoice, run and detail pages | The 2026 run gives every household a correct draft, and the treasurer issues them with numbers 1 to 50 |
| B. Delivery | PDF invoices (WeasyPrint) with every required detail, the organisation's logo and contact block, the Finnish reference number (viitenumero, RF as an option), the bank barcode (virtuaaliviivakoodi) and payment details; sending by email with the PDF attached, as messages; a print batch for post; members download their invoices from the self-service page | Households with email get their invoice in their inbox and the rest come out of the printer in one PDF |
| C. Payments and follow-up | Manual payments (full or partial), paid and overdue status, overdue list, payment reminders by SMS or email with an optional reminder fee (none by default, at most €5 for consumers), CSV export of invoices and payments for bookkeeping | The treasurer marks the payments, reminds the late payers and hands the year to the accountant |

### Invoicing rules

- **VAT.** An organisation is either VAT registered, with a rate per fee
  line (general rate 25.5 %, reduced rates possible), or not (the
  small-business exemption), in which case invoices show no VAT and carry
  the exemption text. Åland belongs to Finnish VAT but is outside the EU VAT
  area; the app does not need cross-border VAT for households. Prices in fee
  plans are without VAT; VAT is counted per rate on the invoice, rounded to
  cents once per rate.
- **Contents.** An issued invoice holds everything the Finnish VAT Act asks
  for: issue date, unique sequential number, the seller's name, address and
  business ID (and VAT number if registered), the buyer's name and address,
  each line's description, quantity, unit price and amount, the VAT base,
  rate and amount per rate or the exemption text, the total and due date.
  Seller and buyer details are copied onto the invoice when it is issued.
- **Numbering.** One sequence without gaps, taken inside the transaction
  that issues the invoice; drafts have no number. Credit notes use the same
  sequence.
- **Immutability.** Issued invoices and their lines cannot change or be
  deleted; corrections are credit notes that refer to the original, and an
  invoice is marked credited when it is fully credited. Payments are
  immutable too: a payment recorded by mistake is reversed with a negative
  one. An invoice's only later change is its status (paid, credited).
- **Reminders.** A payment reminder carries a fee if one is set (none by
  default; at most 5 € for consumers under the Debt Collection Act) and a
  new due date at least 14 days ahead; the amount still to pay is the invoice, less credit notes and
  payments, plus reminder fees. Reminder fees are outside VAT.
- **Retention.** Invoices, credit notes and payments are bookkeeping
  material, kept for the legal period (in Finland 6 years from the end of
  the financial year for vouchers, 10 for the books). They are excluded
  from erasure: erasing a person anonymises them in the register, while
  their invoices stay as issued.

## Phase 5 build plan

Phase 5 is done when the board can email one unit from its page, attach a
file such as the annual meeting's agenda to a send-out, set up a new
install through a wizard, and trust that their email reaches inboxes. It
ships as four pull requests, with deliverability last.

| PR | Contents | Done when |
| --- | --- | --- |
| A. Email a unit | A "Send message" button on the unit page that opens the message form with that unit as the only recipient, sent to the unit's contacts with email (SMS as an option); the message shows on the unit's history. Also fixes the New message form, which shows the tag and type dropdowns even when Everyone is selected | A board member writes to one household from its page and the message appears in its history |
| B. Attachments | Files attached to messages and newsletters (PDF, images and office documents, with a size limit per file and per message), stored under `METRA_DATA_DIR`, sent as email attachments; SMS recipients get a short self-service link to the file instead; files are kept with the message | The agenda for the annual meeting goes out as a PDF to every household |
| C. Setup wizard | A step-by-step wizard after the first admin's first login: organisation name and contact details, language, logo, unit and person types with their fields (with the water association as a ready-made example), email and SMS settings with a test message, invoice settings, and inviting the board. Steps can be skipped; admins can start it again from Settings, and it changes nothing until each step is saved | A new install is ready to use without the Django admin, and an admin can rerun the wizard later |
| D. Email deliverability (replaced by phase 8) | Research first, then build what it recommends. Options to compare: sending through the organisation's own mail account (SMTP with their domain), a transactional provider on a sending subdomain (for example `mail.example.fi`), and a shared Metra sending domain for hosted installs. Whichever wins, the app checks SPF, DKIM and DMARC for the sending domain and shows what to fix, sets a proper From and Reply-To, keeps List-Unsubscribe on newsletters, throttles batches, and records bounces | A test send to Gmail, Outlook and a Finnish ISP lands in the inbox, and the settings page shows the domain's DNS as correct |

## Phase 6 build plan

Phase 6 is done when outside systems can read and update the register
through a documented API and receive signed webhooks when things change,
all delivered as plugins under
`plugins/` that could move to their own repository without changes. The
core keeps the interfaces: provider registry, hooks, permissions and the
audit log. It ships as four pull requests.

| PR | Contents | Done when |
| --- | --- | --- |
| A. Plugin groundwork | `plugins/*` as a uv workspace, with CI testing every plugin; bundled plugins installed in the Docker image and on by default, each one possible to turn off; plugin API events (unit or person changed, reading submitted, invoice issued, payment recorded), a helper to grant plugin permissions to roles, plugin API routes and Settings links; `docs/plugins.md` updated | The example plugin uses the new events and routes, and CI runs its tests |
| B. 46elks SMS plugin | `metra-sms-46elks` with its delivery-report route and the same `METRA_ELKS_*` settings; console and dummy providers stay in the core | An existing install upgrades and keeps sending SMS with no setting changes |
| C. REST API plugin | `metra-api` (Django REST framework): tokens per user or per API client, limited to model permissions; read and write units, people, contacts and readings; read invoices and payments; an OpenAPI docs page, rate limits and audit logging | A script with a token lists households and submits a reading, and the audit log shows it |
| D. Webhooks plugin | `metra-webhooks`: endpoints set by an admin, HMAC-signed payloads for the events from A, retries in the worker and a delivery log | A test endpoint receives a signed event when a payment is recorded, and a failed delivery is retried |

SMTP email stays in the core. A bookkeeping export for outside accounting
software is left out until one is needed; the bookkeeping plugin in
phase 9 covers associations that keep their own books.

## Phase 7 build plan

Phase 7 is done when an admin can undo a big mistake by restoring a
backup from inside the app, every page links to help in Swedish, English
and Finnish, and an association can keep its meeting protocols in Metra.
Staff also get a notification centre. It ships as five pull requests, starting with backups.

| PR | Contents | Done when |
| --- | --- | --- |
| A. Snapshots | Rework backups around snapshots: a consistent copy of the database (SQLite online backup) and uploads, stored under `METRA_DATA_DIR/snapshots`, taken nightly, before every upgrade, before risky actions (CSV import, deleting a unit type or field, restoring) and on demand. Snapshots are kept on a schedule (for example 7 daily, 4 weekly and 12 monthly, manual ones until deleted), and each one is also sent offsite, encrypted, as today. The Backups page lists local and offsite snapshots with their date, size, app version and what triggered them | Deleting a unit type takes a snapshot first, and the Backups page shows it next to last night's |
| B. Restore in the app | An admin with the new restore permission (admins only, after a fresh two-factor check) picks a snapshot and sees what it holds and what the restore would remove; invoices and payments recorded since the snapshot need an extra confirmation. The app takes a safety snapshot and switches to maintenance mode, then the worker restores the database and uploads, runs migrations for older snapshots and brings the site back. People erased after the snapshot are erased again, so a restore never brings back erased personal data. Offsite snapshots are downloaded first, and snapshots from a newer version are refused. The restore is in the audit log, and the `restore` command stays for an install that will not start | An admin deletes a unit type by mistake, restores the morning's snapshot from the Backups page, and the units are back |
| C. Help pages | A Help section with short articles on how to do things: getting started, the register, readings, messages and newsletters, invoicing, backups and restore, roles and two-factor login. Articles are Markdown files per language in the repository, shown in the app with search. Each page links to the article that fits it, Finnish articles carry the machine-translation notice, and plugins can add their own articles through a hook | Every main page has a help link that opens the right article in the user's language |
| D. Meeting protocols plugin | `metra-meetings` under `plugins/`, off by default. Meetings (annual, extraordinary, board) with date, place and agenda; the notice of meeting sent as a message with the agenda attached; attendance from the register, with votes per unit where the rules say so; minutes per agenda item with decisions, the chair, the secretary and the minute checkers; a PDF of the minutes that the checkers approve in the app; approved minutes published to members on the self-service page. Attendance is covered by the per-person export, and approved minutes are kept as the association's records | The annual meeting is called, held and minuted in Metra, and members can read the approved minutes |
| E. Notifications | A notification service in the core: a bell icon next to the account menu with the number of unread notifications, and a Notifications page listing them newest first. Each notification can be opened (it links to what it is about), marked as read or unread, or dismissed, and there is "mark all as read". Notifications go to a user or to everyone in a role, for example a failed or finished backup, a restore, SMS or email that could not be delivered, a reading or contact change sent in through self-service, an invoice becoming overdue, and a failed webhook. Each user chooses which kinds they get; plugins send their own through `apps.plugins.api`. Read and dismissed notifications are removed after 90 days | A failed backup shows up under the bell for every admin, and an admin marks it as read and dismisses it |

## Phase 8 build plan

Phase 8 is done when an admin can turn plugins on and off, and set up
email (SMTP or Mailgun) and SMS (46elks) in the app, without editing the
server's environment. It ships as four pull requests.

| PR | Contents | Done when |
| --- | --- | --- |
| A. Plugin chooser and plugin settings | A Plugins page under Settings lists the installed plugins with their description and version, and an admin turns each on or off. Installed plugins stay loaded, so turning one on or off needs no restart; while it is off, its pages, menu items, panels, events, API routes and providers are hidden, and its data is kept. `METRA_PLUGINS` still decides what is installed. Plugins declare their settings (text, number, choice, on/off and secret fields) through `apps.plugins.api` and get a settings page without writing their own. Secrets are stored encrypted with a key from the environment (`METRA_SETTINGS_KEY`, falling back to one derived from the secret key), are never shown again once saved, only replaced, and changes are in the audit log without the values. A value set in the environment wins and shows as locked. Admins only | An admin turns the meetings plugin off and on from Settings, and its menu item goes and comes back |
| B. Email settings in the app | An Email page under Settings: choose the email provider among the enabled ones, with SMTP built in (host, port, user, password, TLS or SSL, From address and Reply-To). Login codes, invites and other system mail go through the same provider. The setup wizard's messaging step becomes a form, and the test message button stays. Existing `METRA_EMAIL_*` settings keep working | An admin switches from the console to SMTP in the app and the test message arrives |
| C. Mailgun plugin | `metra-email-mailgun` under `plugins/`: sends through the Mailgun API, EU region by default (domain, API key and region as plugin settings), with attachments, List-Unsubscribe and a tag per send-out. Mailgun's signed event webhooks (delivered, bounced, complained) are recorded on the message, and a bounced address is flagged on the person | A newsletter goes out through Mailgun, and a bounce shows on the message and on the person |
| D. 46elks settings in the app | The 46elks plugin's API user, password, sender name and dry-run flag move to its plugin settings page; the `METRA_ELKS_*` variables still win | An admin sets up SMS in the app and a test SMS arrives |

Restoring a snapshot on another server needs the same `METRA_SETTINGS_KEY`;
without it the saved secrets cannot be read and have to be entered again.
The restore guide says so.

## Phase 9 build plan

Phase 9 is done when a small Finnish association or cooperative can keep its
own books in Metra for a whole financial year and hand the auditor
(toiminnantarkastaja or tilintarkastaja) everything they need. The add-on is
`metra-bookkeeping` in `plugins/bookkeeping`, called `bookkeeping` in
`METRA_PLUGINS`, off by default. What differs between countries (chart
templates, the length of a year, and later statement formats, size classes,
retention and export) lives in a country module, `fi` first, so Sweden adds
a module instead of changing the ledger. It ships as five pull requests.

| PR | Contents | Done when |
| --- | --- | --- |
| A. Ledger | Financial years (12 months, 1 to 18 for a first or changed one, each starting the day after the previous one); a chart of accounts from a template (association, or cooperative and company), editable, with account kinds; an account with entries keeps its number and kind and cannot be deleted; voucher series; vouchers (tositteet) with a date, a description, debit and credit lines and attached receipts; posting checks the balance, gives the next number in the series and year (drafts have none, so numbers have no gaps) and locks the voucher; a mistake is corrected with a reversing voucher that points to the original; journal (päiväkirja), general ledger (pääkirja) and trial balance pages, printable; drafts past the four-month booking time are listed; each year shows how long its books and vouchers are kept; the add-on cannot be turned off once it has posted vouchers, so the books stay readable; roles (Treasurer and Admin keep the books, Board and Read-only read them); audit log | The treasurer enters a year's opening balances and a dozen receipts, and the journal and ledger agree |
| B. Postings from Metra | Separate accounts for sales VAT, purchase VAT and the VAT settlement; account settings for receivables, sales per fee line, reminder fees and the bank account; VAT codes with validity dates and the rate stored on each posted line (rates change on dates, registration starts and ends on dates; reverse-charge and import codes for the Åland tax border, or a plain statement that they are not supported); issued invoices, credit notes, payments and reminder fees become vouchers in their own series automatically (accrual basis for invoices), each pointing to the invoice it comes from, which is its evidence; existing issued invoices of the open year can be posted once; Metra gets a `reminder_sent` event in the plugin API | Issuing the 2026 run and marking payments fills the ledger without typing, and the receivables account equals what is outstanding |
| C. Financial statements | Income statement and balance sheet in the PMA decree's formats (Annex IV for associations, the small and micro formats for cooperatives and companies; no extraordinary items), with the decree's own Finnish and Swedish line names, never machine translated; size class worked out from dated thresholds; any date range with the previous year beside it; budget per account and budget against actual; VAT summary per period when registered; PDF and CSV of every report | The board sees the result so far and the budget follow-up at any meeting |
| D. Locking and year-end | Months are locked once reported; a closed year never reopens, and errors found later are corrected in the open year, material ones against retained earnings; a fixed asset register with acquisition cost, date and depreciation plan, and a year-end step that proposes the depreciation voucher; closing the year keeps that year's chart of accounts as it was (names included, so a later rename does not change it), posts the result to equity, locks the year and opens the next one with an opening voucher generated from the closing balances; the year-end package as one PDF: income statement, balance sheet, balance sheet specifications (tase-erittelyt, including fixed assets), notes (liitetiedot), the chart of accounts, the list of books and material (luettelo kirjanpidoista ja aineistoista, naming Metra and its version), journal and ledger, and a signature page; the four-month deadline for the statements and, for cooperatives, the Trade Register filing | The 2026 year is closed, 2027 opens with the right balances, and the auditor gets one file |
| E. Exports and retention | Export of a year as a ZIP (chart of accounts with balances and every voucher line as CSV, the receipts, a README) and as SIE 4 (the format Finnish accountants import is to be confirmed with one); retention periods in the country module and a retention view of what may be removed once the legal periods have passed, never removed automatically; vouchers, receipts and invoices excluded from erasure (the books hold names as booked, so erasing a person leaves the books as booked) | An accountant takes the year into their own software |

### Bookkeeping rules (Finland)

From the Accounting Act (kirjanpitolaki 1336/1997), the Accounting Decree
and the PMA decree for small and micro entities (1753/2015), as reviewed
in the project's compliance review; not legal advice. A Finnish authorised
accountant checks them before the first real year is kept in Metra.

- **Double entry.** Every voucher balances (debits equal credits), in euros
  with cents. Entries are kept in date order (the journal) and in account
  order (the ledger).
- **Vouchers.** Every entry rests on a dated voucher, numbered without gaps
  within its series and year when it is posted. A receipt can be attached;
  a voucher of the add-on's own making points to the record it comes from.
  The voucher shows the accounts it was booked to.
- **Audit trail.** From a report line to the ledger, to the voucher, to the
  receipt or invoice, and back (kirjausketju).
- **Corrections.** A posted voucher never changes and is never deleted. A
  mistake gets a new voucher that reverses it, and both stay in the books.
- **Timing.** Cash entries promptly, day by day, others at the latest four
  months after the end of their month. Not enforced; late drafts are shown.
- **Financial year** is 12 months, a first or changed one 1 to 18.
- **Retention.** Financial statements, balance sheet specifications,
  journal, ledger, chart of accounts and list of books 10 years from the
  end of the financial year; vouchers and receipts 6 years from the end of
  the calendar year in which the financial year ended. These are minimums:
  nothing is deleted automatically, and the add-on cannot be turned off
  while it holds posted vouchers. Receipts are stored under
  `METRA_DATA_DIR`, so backups include them.
- **VAT** only on days the organisation is VAT registered (dated
  registration periods), at the rate in force on the voucher's date, which
  is stored on each line. Sales VAT, purchase VAT and the VAT settlement
  have accounts of their own. Reverse charge and imports (also across the
  Åland tax border) are not supported yet and are booked by hand.
- **Postings from Metra.** Issued invoices and credit notes are booked on
  the accrual basis on their invoice date, payments on the day paid and
  reminder fees on the day of the reminder (without VAT, as compensation
  for collection costs), each in a voucher of its own that points to the
  invoice, its evidence. Records dated before the chosen start day belong
  to the opening balances, which are checked against what those invoices
  had outstanding. The VAT period and rate follow the supply (AVL 15 §):
  invoices carry a delivery date or period, and each posting keeps it, so
  the VAT summary (C) reports by it; PR D accrues invoices issued after
  year end for supplies of the closed year.
- **Financial statements.** In Finnish or Swedish, with the line names of
  the PMA decree (annex IV for associations, annex I for cooperatives and
  companies, annex V for the balance sheet); English only as a labelled
  translation. Accounts land on lines by number range, and accounts on no
  line are listed, never dropped. The size class is worked out on the safe
  side (micro only when no more than one micro limit is exceeded in each of
  the two years), and a full small-entity statement is always allowed.
- **VAT summary.** Per VAT period (month, quarter or year, from the
  registration), by rate. An invoice counts at the end of its supply
  period, except the part paid before it, an advance payment, which counts
  in the month paid; a reversal counts where the voucher it reverses did.
  Entries without a VAT code (reverse charge, imports) are outside it, and
  it is marked not ready while such entries on the VAT accounts, drafts
  with VAT or records waiting from invoicing exist.
