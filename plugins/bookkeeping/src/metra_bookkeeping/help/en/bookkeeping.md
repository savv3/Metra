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

Income statement, balance sheet, budget, automatic entries from invoices
and payments, and closing the year come in later versions of the add-on.
