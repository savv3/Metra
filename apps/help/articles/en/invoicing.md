# Invoicing

## Settings and fees

Under **Settings > Invoicing > Invoice settings** an admin sets the bank account, payment
terms, VAT, numbering and the texts on invoices. **Settings > Invoicing > Fee plans** says
what units pay: fixed fees and fees per unit of a reading (such as per m³),
optionally in price tiers, each with its VAT rate.

## Making invoices

**Invoices > Invoice runs > New invoice run** picks the period, the fee plans
and the reading round, and makes a draft invoice for each unit, addressed to
its billing contact or owner. Drafts with a missing or odd reading are marked
**Check**: enter the reading and rebuild the draft, or edit its lines.

**Issue all checked drafts** on the run page, or **Issue invoice** on a single
draft, gives each invoice its number and dates and locks it. An issued
invoice is never changed: a mistake is corrected with a credit note (**Make a
credit note** on the invoice), which can credit all or part of it.

## Sending

Issued invoices go out by email as a PDF with the payment reference, bank
barcode and a payment QR code. Those without email, or who prefer post, are
listed for printing, and **PDF of invoices for post** on the run page gives
their letters in one file. Members also find their invoices on their own
page.

## Payments and reminders

Record payments on the invoice page with **Record a payment**, in full or in
parts. An invoice is **Paid** when nothing is outstanding. Payments are never
changed or deleted; to undo one, record the same amount as a negative
payment.

**Invoices > Overdue** lists unpaid invoices past their due date. **Send
reminders to the chosen** sends a payment reminder on each person's preferred
channel (email or SMS, or the other one if they have no address for it), or
by letter to those who prefer post or have neither, with the reminder fee if one is set and at least 14 days to pay.

## Bank files

Instead of recording each payment by hand, download the bank's file of
incoming payments from your online bank and upload it under **Invoices > Bank
files**. Metra reads ISO 20022 XML files: camt.054, the file of reference
payments, and camt.053, the account statement. Every payment whose reference
belongs to an invoice and that pays exactly what is left is recorded on that
invoice. The reference may be the Finnish one or the RF one, with or without
spaces.

Payments with no reference or an unknown one, partial payments and payments of
too much are marked **To review**: record those by hand on the right invoice.
Money paid out is listed but not matched. Uploading the same file twice changes
nothing, and a payment already imported from an earlier file (such as the
reference payments file before the month's statement) is skipped. Each
imported file shows its lines and what happened to each one.

## For the accountant

**Export as CSV** under the invoice list gives every issued invoice with
totals, VAT, credits, payments and what is outstanding. **Export payments**
gives payments and reminder fees for a period.
