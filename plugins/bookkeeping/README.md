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
- postings from Metra: issued invoices and credit notes (on the accrual
  basis), payments and reminder fees become vouchers in their own series
  automatically, each pointing to the invoice that is its evidence, with
  accounts chosen per fee line or VAT rate;
- VAT on voucher lines, with the rate in force on the voucher's date
  stored on each line, dated VAT registration, and separate accounts for
  sales VAT, purchase VAT and the VAT settlement. Reverse charge and
  imports are not supported yet;
- the income statement and balance sheet in the formats of the decree on
  small and micro entities (PMA 1753/2015; the non-profit format for
  associations), with the decree's own Finnish and Swedish line names, the
  previous year beside them, the size class and the shorter micro-entity
  format. Accounts land on lines by their number;
- a budget per account and year, followed up against the books;
- a VAT summary per VAT period by rate, dated by the supply and by advance
  payments, that says when it is not ready for the return;
- every report as a PDF and a CSV file;
- locking months once reported, and closing a year: its chart of accounts
  is kept as it was, it is locked for good, and the next year opens with
  the closing balances and the result carried to equity, enforced by
  database triggers like posted vouchers;
- a fixed asset register with depreciation plans, and year-end entries
  proposed from it and from invoices issued after the year;
- the year-end package for the auditor as one PDF: statements, notes,
  signature page, balance sheet specifications, list of books and
  material, chart of accounts, journal and ledger;
- export of a year for an accountant or for keeping outside Metra: a ZIP
  with the chart of accounts and balances and every voucher line as CSV,
  the receipts, and the year in SIE 4 (or the SIE 4 file alone), recorded
  in the audit log;
- a list of drafts past the legal booking time (four months after the end
  of their month), and a retention page with, for each year, the dates
  until which its books and vouchers must be kept (from the country
  module; KPL 2:10 in Finland). These are the Accounting Act's minimums:
  grant terms, the VAT adjustment period of property investments or an
  open tax audit or dispute can require longer. Nothing is removed
  automatically.

Official, but off until `METRA_PLUGINS=bookkeeping`. Admin and Treasurer
keep the books; Board and Read-only (for example the auditor) read them.
Once the books have posted vouchers, the add-on cannot be turned off under
Settings > Add-ons, so that they stay readable for the legal period.
Removing it from `METRA_PLUGINS` on the server is not stopped: keep the books
another way first (export every year, keep the year-end packages and a
backup). The tables stay in the database.

What differs between countries is in `countries/` (Finland in `fi.py`),
including the retention periods. The plan is the phase 9 build plan in
[docs/history/build-plans.md](../../docs/history/build-plans.md#phase-9-build-plan).

Personal data: voucher descriptions and receipts can name people, and the
invoices behind vouchers name their recipients. They are bookkeeping
material, kept for the legal period and left out of erasure (GDPR art.
17(3)(b)): the books hold copies of names as booked, so changing,
archiving or anonymising a person in the register leaves them as they were.

The rules here are from general knowledge of the law, not legal advice; an
authorised accountant should check them before the first real year.
