# Might do later

Ideas that were on the roadmap but are not planned for now. Any of them can
go back into the phase list in [architecture.md](architecture.md#roadmap)
when there is a need.

## Bank file import

Import the bank's ISO 20022 statement files (camt.054 for incoming
reference payments, camt.053 as a fallback) and match payments to open
invoices by reference number, Finnish or RF. Unmatched and partial
payments land in a review list for the treasurer. Importing the same file
twice is safe. Bank formats sit behind an importer interface, open to
plugins. With the bookkeeping plugin, imported bank lines would also be
matched to vouchers.

A first part, parsing camt.053 and camt.054 files and matching by
reference number, with tests, is kept on the branch
`claude/project-thread-ky14sp`.

## E-invoicing

Send invoices as Finvoice to business clients and members who ask for it,
through an operator behind a provider interface, chosen per unit. Peppol
follows when a client needs it. Households keep getting PDFs.

## Privacy automation

Admin-set retention rules per kind of data (archived people, old
messages, readings, attachments, audit entries) run on a schedule in the
worker, with a preview of what the next run removes and a log of what it
did. Bookkeeping material keeps its legal period and is never removed
early.
