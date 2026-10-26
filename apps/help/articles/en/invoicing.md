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

The run also gives the supply period: the first and last day the fees are
for, such as 1.1.–31.12. It is printed on each invoice as the delivery
period. VAT follows it rather than the invoice date: for water and other
continuous supplies, VAT is due for the month the period ends in, at the
rate in force then. A single invoice can have its own delivery date or
period; without one, the invoice date counts.

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

## For the accountant

**Export as CSV** under the invoice list gives every issued invoice with
totals, VAT, credits, payments and what is outstanding. **Export payments**
gives payments and reminder fees for a period.
