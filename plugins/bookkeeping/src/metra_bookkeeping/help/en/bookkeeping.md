# Bookkeeping

The Bookkeeping add-on keeps the organisation's books in Metra: double
entry, with numbered vouchers and receipts, following the Finnish Accounting
Act. An admin turns it on under Settings > Add-ons. The treasurer keeps the
books; the board and the read-only role (for example the auditor) can read
them.

## Starting the books

Open **Bookkeeping** and choose the first financial year and a chart of
accounts:

- **Association** for a registered association (yhdistys), with
  membership fees and fundraising, and a surplus or deficit;
- **Cooperative or company** for a cooperative (osuuskunta), such as a
  water cooperative, or a company, with sales and a profit or loss.

The chart is a starting point. Under **Chart of accounts** you can add
accounts, rename them and stop using the ones you do not need. Once an
account has entries, its number and kind stay as they are.

Then enter the balances the year starts with, from last year's balance
sheet, as the first voucher, of the kind **Opening balances**.

A financial year is 12 months and starts the day after the previous one
ends. The first year, or a year whose dates change, can be 1 to 18 months.

## Vouchers

Every entry in the books rests on a voucher. Under **New voucher**, give
the date, a description and the lines: each line goes to one account, as a
debit or a credit. Debits and credits must add up to the same amount.

For example, an electricity bill of 84.50 € paid from the bank account:

| Account | Debit | Credit |
| --- | --- | --- |
| 4610 Electricity | 84.50 | |
| 1910 Bank account | | 84.50 |

A voucher is a draft until you post it. Attach the receipt (a PDF or a
photo) to the draft, then press **Post**. Posting checks that the voucher
balances, gives it the next number and locks it. Numbers have no gaps:
drafts have no number, so deleting a draft leaves no gap.

## VAT

If the organisation is VAT registered, add the dates of its registration
under **Bookkeeping of invoices** > **VAT registration**. VAT can then be
booked on days inside a registration, and only at a rate in force on the
voucher's date: the reduced rate, for example, was 14 % until 31.12.2025
and is 13.5 % from 1.1.2026. Each line keeps the rate it was booked with.

On a voucher, mark the line with the price without VAT and the VAT line
with the same VAT code. For a purchase of 100 € + 25.5 % VAT:

| Account | Debit | Credit | VAT |
| --- | --- | --- | --- |
| 4000 Materials and supplies | 100.00 | | Purchases 25.5 % |
| 1765 VAT on purchases | 25.50 | | Purchases 25.5 % |
| 1910 Bank account | | 125.50 | |

Sales VAT, purchase VAT and the VAT to pay have accounts of their own.
For each VAT period, move the sales and purchase VAT to the VAT settlement
account (2939) with a voucher, and book the payment of the tax against it.

Reverse charge (services bought from other EU countries, construction) and
imports, including goods across the Åland tax border, are not supported
yet. Book them by hand without a VAT code, and check them with an
accountant.

## Invoices and payments

Metra can book invoicing for you. Under **Bookkeeping of invoices**,
choose the day automatic posting starts and the accounts:

- each issued invoice is booked on its invoice date: receivables on the
  debit side, sales (and sales VAT) on the credit side;
- a credit note is booked the same way, the other way round;
- a payment is booked on the day it was paid: bank account on the debit
  side, receivables on the credit side;
- a reminder fee is booked on the day of the reminder, to the reminder
  fees account, without VAT.

Sales go to the account chosen for the invoice line's fee line, else to
the account chosen for its VAT rate, else to the default sales account.
Invoices go to their own voucher series (L) and payments to another (S).

An invoice's voucher is dated the invoice date, but its VAT belongs to the
month of the invoice's delivery date or the end of its delivery period,
which the voucher shows. An invoice issued in January for last year's water
therefore has its VAT in last December's period, at last year's rate.

The settings page checks that the receivables account, when automatic
posting starts, equals what the invoices issued before then had
outstanding, and warns when they differ.

Each such voucher is posted at once and shows the invoice it comes from;
the invoice is its evidence, and the invoice page shows its vouchers. If
one cannot be posted (an account no longer in use, say), it stays a draft
for you to fix and post. Invoices and payments made while posting was off,
or dated in no open financial year, are listed on the Bookkeeping page;
**Post them now** books them, once.

Choose the start day after anything already booked by hand, so nothing is
booked twice. Invoices from before the start day are part of the opening
balances: their payments, if made after the start day, are booked against
the receivables account as usual.

The receivables account then equals what is outstanding on the invoices:
invoices less credit notes and payments, plus reminder fees.

A wrong automatic voucher is corrected like any other: reverse it, and
enter the right entry as a new voucher.

## Correcting a mistake

A posted voucher never changes and cannot be deleted. To correct one, open
it and press **Reverse**: a new voucher with the same lines on the opposite
side cancels it, and both stay in the books. Then enter the right entry as a
new voucher. A receipt can still be added to a posted voucher, but not
removed.

## Reports

- **Journal**: the posted entries in date order.
- **General ledger**: the entries account by account, with the balance
  after each entry. Click an account to see only that account.
- **Trial balance**: every account's balance at the start and end of the
  period, and the period's debits and credits.

Each report can cover the whole financial year or a few dates in it, and
can be printed. Balances are shown as debit minus credit.

## When to book

The law asks for cash payments to be booked promptly, day by day, and other
entries at the latest four months after the end of their month. The
Bookkeeping page lists drafts that are past that.

## How long the books are kept

The year's page shows how long its material must be kept: the financial
statements, journal, ledger, chart of accounts and list of books 10 years
from the end of the financial year; vouchers and receipts 6 years from the
end of the calendar year in which the financial year ended. Nothing is
deleted automatically. Once the books have posted vouchers, the add-on
cannot be turned off, so that they stay readable.

An administrator who removes the add-on from the server (from `METRA_PLUGINS`) must first keep the books for the legal period another way: save the reports and receipts, and keep a backup. The data stays in the database, but cannot be read in Metra while the add-on is not installed.

Closing the year comes in a later version of the add-on.

## Financial statements

**Income statement** and **Balance sheet** show the books in the formats
of the decree on the financial statements of small and micro entities
(PMA 1753/2015): an association gets the non-profit income statement, with
its own activities, fundraising, and investment and financing, each with a
surplus or deficit; a cooperative or company gets the standard income
statement with net sales and operating profit. The balance sheet is the
same for both.

The line names are the decree's own, in Finnish or Swedish: choose the
language under **Language**. The statements are kept in Finnish or
Swedish; an English version can be shown, but it is a translation and not
for filing. The previous financial year is shown beside the period when it
is in Metra.

Each account goes to the line its number falls in. The chart templates
follow this, and an account you add lands on the line of its number's
range: for example 1700–1749 trade receivables, 1900–1999 cash and bank,
2610–2699 loans from credit institutions, 2871–2879 trade payables. If an
account falls on no line, the statement lists it and leaves it out, so
give it a number in the right range. Tick **Long-term** on an account for a
receivable or liability due after more than a year; keep the part due
within a year on an account of its own.

The profit or surplus for the year is worked out from the income and
expense accounts, so the balance sheet balances before the year is closed.

### Size class

Under the statements Metra shows the size class, from the balance sheet
total, the turnover (counted for 12 months) and the average staff of the
year and the year before. Enter the year's average staff on the year's
page. A **micro entity** may use the shorter format, which leaves out the
lettered breakdowns and shows how much of the debt is short-term; the full
format is always allowed. Metra stays on the safe side: an entity is
micro only if no more than one micro limit is exceeded in either year.
For an association, all its income counts as turnover. When even the
small-entity limits are exceeded, the decree no longer applies: ask an
accountant.

## Budget

Under **Budget**, **Edit the budget** takes the year's expected income and
costs per account, as positive amounts. **Budget** then compares them with
what is booked in the chosen dates, per account and in total.

## VAT summary

**VAT summary** adds up the sales and purchase VAT by rate for each VAT
period, with the tax to pay or to get back and the day the return is due.
Choose the VAT period (month, quarter or calendar year) on the VAT
registration.

The VAT follows the supply, not the voucher's date:

- an invoice counts at the end of its delivery period (or on its delivery
  date);
- the part of an invoice paid before its delivery period ends is an
  advance payment: its VAT is due for the month it was paid;
- a receipt entered by hand counts on the voucher's date;
- a reversal counts where the voucher it reverses counted, since a VAT
  error is corrected for the period it was made in.

Only lines with a VAT code are in the summary. Reverse charge, imports
(also across the Åland tax border) and entries booked without a VAT code
are not: add those to the return yourself. The summary says when it is
not ready to copy into the return: when an entry on a VAT account has no
VAT code, a draft voucher has VAT, or invoices and payments are waiting
for their vouchers. It also lists what was posted after a period ended, in
case that period's return was already filed.

## Printing and files

Every report can be printed, saved as a **PDF** or downloaded as a **CSV**
file for a spreadsheet.
