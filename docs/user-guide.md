# Metra user guide

[Back to the README](../README.md) · [Installing and running](../INSTALL.md)

How to set up and use Metra once it is running. Menu names are given in
English; the app shows them in the user's language.

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
- sees their own contact details and who else is registered for the
  household (names and roles only), and corrects their own phone, email
  and address.

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
links work for `METRA_SELF_SERVICE_LINK_DAYS` (30) days. Unknown, expired and
stopped links all show the same page. The member pages are rate-limited per
visitor address, are kept out of search engines (`noindex`) and send the
referrer only to the app itself (`Referrer-Policy: same-origin`), so the
link never reaches other sites. Letters use `METRA_BASE_URL` (by default `https://METRA_DOMAIN`) for
the address.

Links are personal data about the person they belong to: they are covered
by the per-person export and erasure tools planned for phase 8, together
with the person's other records.

## Sending links and reminders

On a round's page, **Send links to all units** gives each unit's main
contact (the owner, else the billing contact) a new personal link by SMS. A
contact without a phone number, or whose SMS fails, gets it by email. Those
without either, or whose preferred channel is post, are listed as **needs a
letter**, with a button that prints their letters. **Send reminder to units
missing a reading** does the same for units that have not reported yet.
Sending runs in the worker, and the send-out page (under **Send-outs**)
shows each message's status as it goes, including delivery reports from
46elks.

The texts are under **Settings > Message templates**, one per purpose
(link or reminder) and channel (SMS or email), with the placeholders
`{name}`, `{first_name}`, `{link}`, `{closes}`, `{period}`,
`{reading_type}`, `{unit}` and `{organisation}`. The stored copy of each
message has `[personlig länk]` where the link was, because links are kept
only as hashes.

Automatic reminders are off by default. Set `METRA_READING_REMINDER_DAYS`
(for example `7`) to remind units still missing a reading that many days
before an open round closes, at 10:00, once per round.

## Public page and contact details

Visitors who are not logged in see the organisation's own page at the
site's address: its public name, logo, a short description, phone, email,
address, opening hours, website and an emergency phone, with a link to the
staff login. An admin fills these in under **Settings > Organisation >
Public page and contact details**. The logo can be a PNG, JPEG or WebP
image up to 1 MB. Untick **Show the public page** to show only a plain
welcome page instead.

The same contact details appear on members' self-service pages and at the
foot of printed letters, and messages can use `{organisation}`,
`{organisation_phone}`, `{organisation_email}`, `{organisation_website}`
and `{emergency_phone}` (the ordinary phone when no emergency phone is
set). Only organisation data is shown there, never anyone's personal data.

**Notices** are short banners at the top of the public page and of members'
pages, for example "Water off in the village until 18:00". An urgent alert
can publish one (**Also show as a notice on the public page**, with an
optional end time); the send-out page has **Remove the notice**, and all
notices are listed under **Settings > Notices**.

Search engines may index the public page and nothing else: `robots.txt`
allows only `/`, and every other page sends `X-Robots-Tag: noindex`.

## Messages and urgent alerts

Admins can write one message to many households under **Send-outs > New
message**. It can go to everyone, to units with a tag or of a type, or to
the units in the current unit list (the **Send a message to these units**
link under the list), and to all contacts of each unit or only its main
contact. Choose SMS only, email only, SMS (or email for those without a
phone), or both. The text can use `{first_name}`, `{name}`, `{unit}` and the organisation's
contact placeholders (see above); a live counter shows how many SMS it
takes.

Before anything is sent, a check page shows how many people get an SMS and
how many an email, the total number of SMS, and who cannot be reached, so
someone can call or visit them. Each person gets the message once, even if
they are a contact of several units.

**Urgent alert** (red button) is for disruptions such as a water leak: it
starts with SMS and email to every contact of every active unit, and sends
on both channels to everyone who has them, whatever their preferred
channel. The send-out page shows each recipient's delivery status as it
goes.

These are service messages about the organisation's own service, sent on
the basis of membership, so they do not need newsletter consent; use them
for operational information, not marketing. Only the Admin role may send
them; an admin can give the "Can send messages and alerts to everyone"
permission to Board under **Settings > Groups**.

To write to one household, open the unit and use **Send message** under
**Messages**. It goes to the unit's contacts, by email unless you choose
SMS, with the same check page before sending. The unit page lists every
message its contacts have been sent, including links, reminders and
invoices. Admin and Board can do this ("Can send a message to one unit").

### Attachments

Messages and newsletters can carry files, such as the annual meeting's
agenda: PDF, images and office documents, up to 10 MB per file and 15 MB per
message (`METRA_ATTACHMENT_FILE_MB` and `METRA_ATTACHMENT_TOTAL_MB`). Email
recipients get the files attached. SMS recipients get a short link at the end
of the SMS to a page with the files; it needs no login and stops working
after `METRA_SELF_SERVICE_LINK_DAYS` days (30 by default). The check page
lists the files and counts the link in the number of SMS.

The files are kept with the send-out, where staff can download them again,
and are stored in the data folder, so backups include them. Files uploaded
for a message that was never sent are removed after a day.

## Newsletters

Newsletters are email to people who have said yes, and only to them.

- **Consent.** Each person's yes or no is kept as a record with the time and
  the source: the member's own self-service page, staff (for a yes given on
  paper or by phone, with a note on how it was given), or the unsubscribe
  link. A person's newest answer counts; no answer means no. Staff see and
  record it on the person page; earlier answers are listed there too, and
  the records are never edited (**Settings > Newsletter consents**).
- **Sending.** **Send-outs > New newsletter** (Admin): write a subject and
  plain text with `{first_name}`, `{name}` and `{organisation}`, check how it
  looks, and send. It goes to active people whose newest answer is yes and
  who have an email address, `METRA_NEWSLETTER_BATCH_SIZE` (50) at a time with
  `METRA_NEWSLETTER_PAUSE_SECONDS` (60) between parts, so the mail server's
  limits hold. Anyone who unsubscribes meanwhile is skipped.
- **Unsubscribing.** Every newsletter ends with a personal unsubscribe link
  (a signed address, nothing stored) and carries `List-Unsubscribe` headers,
  so mail programs show their own one-click unsubscribe button. Opening the
  link asks for a click before anything changes, so mail scanners that open
  links do not unsubscribe anyone.

Service messages and alerts (above) are not newsletters and reach everyone.
Consent records are personal data, covered by the export and erasure tools.

## Invoicing

Under **Settings > Invoice settings** an admin sets whether the organisation
is VAT registered (off by default; invoices then carry the exemption text),
the IBAN and BIC, payment terms, the invoice numbering and the texts on
invoices. **Settings > Fee plans** says what units pay: fixed fees (with
`{period}` in the text, for example "Grundavgift {period}") and usage fees
priced per unit of a reading, optionally in tiers, each with its VAT rate.
A fee line can apply only to units with a given custom field value, and a
plan only to units with a tag. The water setup adds "Kommunal vattenavgift"
with a base fee and a price per m³; delete the m³ line if usage is not
charged.

**Invoices > Invoice runs > New invoice run** picks the period, the fee
plans and the reading round, and makes a draft invoice for each active unit
the plans apply to, addressed to its billing contact (or the owner).
Drafts whose reading is missing or looks wrong are marked **Check** and are
not issued with the others: enter the reading and rebuild the draft, or
edit its lines. **Issue** gives an invoice the next number and the invoice
and due dates, and locks it. A mistake in an issued invoice is corrected
with a **credit note**, which can credit all or part of it.

Treasurer and Admin run invoicing; Board can look at it; Read-only cannot.

### Invoice PDFs and sending

Issued invoices are PDFs with everything a Finnish invoice needs: the
seller's details and business ID, the buyer, the lines, VAT per rate or the
exemption text, the due date, the payment reference and a payment block
with the IBAN, a SEPA payment QR code and the bank barcode
(virtuaaliviivakoodi) that bank apps read. The reference is a Finnish
reference number (viitenumero) by default; **Settings > Invoice settings >
Payment reference** switches to international RF references. The barcode
needs a Finnish IBAN.

**Send invoices** on a run page emails each issued invoice with its PDF
attached (the text is under **Settings > Message templates**, "Invoice").
Recipients without email, or who prefer post, end up in **PDF to print** on
the send-out page; **PDF of invoices for post** on the run page gives the
same letters at any time. Members find their household's invoices as PDFs
on their self-service page.

### Payments, reminders and bookkeeping

Payments are recorded by hand on the invoice page (**Record a payment**:
amount, date, the reference the payer gave and a note), in full or in
parts. An invoice is **Paid** when nothing is outstanding, counting credit
notes and reminder fees. Payments are never changed or deleted; to undo
one, record the same amount as a negative payment.

**Invoices > Overdue** lists unpaid invoices past their due date, with the
days late and the amount to pay. **Send reminders to the chosen** sends a
payment reminder by email (with a reminder PDF that has the new amount,
due date and barcode), else by SMS, else as a letter in a PDF to print.
Each reminder adds the reminder fee if one is set (**Settings > Invoice
settings**; none by default) and gives at least 14 days to pay. In Finland the Debt
Collection Act (laki saatavien perinnästä) caps a reminder fee to a consumer
at 5 € and requires those 14 days before further collection steps; check
the rules before charging more or reminding businesses differently. The
texts are under **Settings > Message templates**, "Payment reminder".

For the accountant, **Export as CSV** under the invoice list gives every
issued invoice (or the filtered ones) with totals, VAT, credits, payments,
fees and what is outstanding; **Export payments** gives payments and
reminder fees for a date range.

## Import and export

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
([static/examples/hushall-exempel.csv](../static/examples/hushall-exempel.csv)).

The unit and people lists have an **Export as CSV** link that downloads the
current filtered list, semicolon-separated with a UTF-8 BOM so Excel shows å,
ä and ö correctly. Custom fields become columns named by their labels. Every
export is recorded in the audit log with who exported which records; the
file is made in memory and never stored on the server.

## Users, roles and two-factor login

The first account comes from `createsuperuser` (in Docker:
`docker compose exec web python manage.py createsuperuser`). When it first
logs in, the app asks for the password once more and then for an
authenticator app (for example Aegis, Google Authenticator or 1Password):
scan the QR code, enter the six-digit code, and save the recovery codes it
shows. Staff and superusers cannot use the app until this is done, and from
then on every login asks for a code.

In development (`METRA_DEBUG=true`) two-factor is not required, so you can
log in with just a password; staff see a warning banner saying so.
`METRA_REQUIRE_MFA` sets it either way (it is on by default in production).

Further users are added under **Settings > Users**. Give each one a role by
adding them to one group:

| Role | Can |
| --- | --- |
| Admin | Everything; also tick "Staff status" so they can open Settings |
| Board (Styrelse) | View, add and edit units, people, contacts and tags; archive; see history |
| Treasurer (Kassör) | View the register (invoicing comes later) |
| Read-only (Läsbehörighet) | View the register |

The roles are shown in the user's language; groups you create yourself keep
the name you give them. Two-factor login is optional for users without staff status; until they turn it
on under **Two-factor login**, every page reminds them to. Every change to the register, every role
change and every opened unit or person page is recorded in the audit log,
shown on the unit and person pages for Admin and Board and under
**Settings > Log entries**.
