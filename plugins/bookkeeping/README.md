# Bookkeeping plugin

Double-entry books in Metra for a small association or cooperative,
following the Finnish Accounting Act (kirjanpitolaki):

- financial years of 12 months (1 to 18 for a first or changed one), each
  starting the day after the previous one ends;
- a chart of accounts from a template, for a registered association or for
  a cooperative or company, in the installation's language, then edited in
  the app. An account with entries keeps its number and kind;
- vouchers with a date, a description, debit and credit lines and attached
  receipts (PDFs or photos). Posting checks that a voucher balances, gives
  it the next number in its series and year, and locks it. Drafts have no
  number, so numbers have no gaps;
- corrections by reversing vouchers: a posted voucher never changes and is
  never deleted;
- the journal (päiväkirja), general ledger (pääkirja) and trial balance,
  for a year or part of it, printable;
- a list of drafts past the legal booking time (four months after the end
  of their month), and on each year the dates until which its books and
  vouchers must be kept.

Official, but off until `METRA_PLUGINS=bookkeeping`. Admin and Treasurer
keep the books; Board and Read-only (for example the auditor) read them.
Once the books have posted vouchers, the add-on cannot be turned off under
Settings > Add-ons, so that they stay readable for the legal period.
Removing it from `METRA_PLUGINS` on the server is not stopped: keep the books
another way first (reports, receipts and a backup). The tables stay in the database.

What differs between countries is in `countries/` (Finland in `fi.py`).
The plan for the rest (postings from invoices and payments, VAT, financial
statements, budget, year-end and exports) is the phase 9 build plan in
[docs/architecture.md](../../docs/architecture.md#phase-9-build-plan).

Personal data: voucher descriptions and receipts can name people. They are
bookkeeping material, kept for the legal period and left out of erasure.

The rules here are from general knowledge of the law, not legal advice; an
authorised accountant should check them before the first real year.
