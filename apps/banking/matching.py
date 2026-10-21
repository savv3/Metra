"""Storing a bank file's lines and matching them to invoices.

A line is matched by its payment reference: Finnish or RF, with or without
spaces and leading zeros, and an RF reference also matches the Finnish
reference inside it. A line that pays exactly what is outstanding on an
issued invoice is recorded as a payment; every other incoming line gets a
reason and waits for the treasurer.
"""

import hashlib
import re
from collections import Counter
from decimal import Decimal

from django.db import transaction
from django.utils.translation import gettext as _

from apps.invoicing.models import Invoice
from apps.invoicing.payments import record_payment
from apps.invoicing.reference import is_valid_rf

from . import importers
from .models import BankStatement, BankTransaction

Status = BankTransaction.Status
Reason = BankTransaction.Reason


class AlreadyImported(Exception):
    def __init__(self, statement):
        super().__init__(str(statement))
        self.statement = statement


def normalise(reference):
    """The comparable form of a payment reference: no spaces, no leading
    zeros, and an RF reference reduced to the reference it wraps."""
    text = re.sub(r"\s", "", reference or "").upper()
    if text.startswith("RF") and is_valid_rf(text):
        text = text[4:]
    return text.lstrip("0")


def _invoices_by_reference():
    invoices = Invoice.objects.issued().filter(kind=Invoice.Kind.INVOICE).exclude(reference="")
    return {normalise(invoice.reference): invoice for invoice in invoices}


def _key(account, line, seen):
    """A stable id for a line across files: the bank's archive reference, or
    a checksum of what the line says when the bank gives none."""
    if line.bank_reference:
        return f"{account}:{line.bank_reference}"[:200]
    text = "|".join(
        str(part)
        for part in (
            account,
            line.booked_on,
            line.amount,
            line.currency,
            line.reference,
            line.message,
            line.payer_name,
            line.payer_account,
        )
    )
    digest = hashlib.sha256(text.encode()).hexdigest()
    seen[digest] += 1
    return f"{account}:sha256:{digest}#{seen[digest]}"


def match(line, invoices, user=None):
    """Decide what to do with a stored line, recording a payment when it
    pays an invoice exactly. ``invoices`` maps normalised references."""
    if line.amount < 0:
        line.status, line.reason = Status.OUTGOING, Reason.NONE
        return line
    line.status = Status.REVIEW
    invoice = invoices.get(normalise(line.reference)) if line.reference else None
    line.invoice = invoice
    if line.currency != "EUR":
        line.reason = Reason.CURRENCY
    elif not line.reference:
        line.reason = Reason.NO_REFERENCE
    elif invoice is None:
        line.reason = Reason.UNKNOWN_REFERENCE
    elif invoice.status == Invoice.Status.CREDITED:
        line.reason = Reason.CREDITED
    else:
        outstanding = invoice.outstanding()
        if outstanding <= 0:
            line.reason = Reason.ALREADY_PAID
        elif line.amount < outstanding:
            line.reason = Reason.PARTIAL
        elif line.amount > outstanding:
            line.reason = Reason.TOO_MUCH
        else:
            line.payment = record_payment(
                invoice,
                line.amount,
                line.booked_on,
                reference=line.reference[:40],
                note=(_("Bank file %(file)s") % {"file": line.statement.file_name})[:200],
                user=user,
            )
            line.status, line.reason = Status.MATCHED, Reason.NONE
    return line


@transaction.atomic
def import_file(name, data, user=None):
    """Read, store and match a bank file. Raises StatementError for a file
    that cannot be read and AlreadyImported for one imported before."""
    file_hash = hashlib.sha256(data).hexdigest()
    if earlier := BankStatement.objects.filter(file_hash=file_hash).first():
        raise AlreadyImported(earlier)
    parsed = importers.parse(data)
    account = re.sub(r"\s", "", parsed.account).upper()
    statement = BankStatement.objects.create(
        file_name=name[:255],
        file_hash=file_hash,
        format=parsed.format,
        account=account,
        starts=parsed.starts,
        ends=parsed.ends,
        imported_by=user,
    )
    seen = Counter()
    keyed = [(_key(account, line, seen), line) for line in parsed.lines]
    known = set(
        BankTransaction.objects.filter(key__in=[key for key, _line in keyed]).values_list(
            "key", flat=True
        )
    )
    invoices = _invoices_by_reference()
    for key, parsed_line in keyed:
        if key in known:
            statement.skipped += 1
            continue
        known.add(key)
        line = BankTransaction(
            statement=statement,
            key=key,
            booked_on=parsed_line.booked_on,
            value_date=parsed_line.value_date,
            amount=Decimal(parsed_line.amount).quantize(Decimal("0.01")),
            currency=parsed_line.currency[:3].upper(),
            reference=re.sub(r"\s", "", parsed_line.reference)[:40],
            message=parsed_line.message[:500],
            payer_name=parsed_line.payer_name[:200],
            payer_account=re.sub(r"\s", "", parsed_line.payer_account)[:40],
            bank_reference=parsed_line.bank_reference[:100],
        )
        match(line, invoices, user)
        line.save()
    if statement.skipped:
        statement.save(update_fields=["skipped"])
    return statement
