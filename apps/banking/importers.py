"""Reading bank files. Each format is an importer; the core reads ISO 20022
camt.054 and camt.053, and plugins add others with ``api.add_bank_importer``.

An importer turns a file's bytes into a ``ParsedStatement``: the account,
the period and one ``ParsedLine`` per transaction. It does not touch the
database; ``apps.banking.matching`` stores the lines and matches them.
"""

import datetime
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from apps.plugins.hooks import BANK_IMPORTERS, hooks

MAX_SIZE = 20 * 1024 * 1024


class StatementError(ValueError):
    """The file cannot be read. The message is shown to the user."""


@dataclass
class ParsedLine:
    booked_on: datetime.date
    amount: Decimal  # positive for money in, negative for money out
    currency: str = "EUR"
    value_date: datetime.date | None = None
    reference: str = ""  # a structured payment reference, as given
    message: str = ""  # free text from the payer
    payer_name: str = ""
    payer_account: str = ""
    bank_reference: str = ""  # the bank's own id for the line (archive reference)


@dataclass
class ParsedStatement:
    format: str  # the importer's name
    account: str = ""  # IBAN
    starts: datetime.date | None = None
    ends: datetime.date | None = None
    lines: list = field(default_factory=list)


class Importer:
    """A bank file format. ``name`` is a stable slug, ``label`` is shown to users."""

    name = ""
    label = ""

    def accepts(self, data: bytes) -> bool:
        raise NotImplementedError

    def parse(self, data: bytes) -> ParsedStatement:
        raise NotImplementedError


# ISO 20022 cash management (camt)


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _child(element, *path):
    """The first descendant along ``path`` of local names, ignoring namespaces."""
    for name in path:
        if element is None:
            return None
        element = next((c for c in element if _local(c.tag) == name), None)
    return element


def _children(element, name):
    return [c for c in element if _local(c.tag) == name] if element is not None else []


def _text(element, *path):
    found = _child(element, *path)
    return (found.text or "").strip() if found is not None else ""


def _date(element, *path):
    """A date from <Dt> or <DtTm> under ``path``."""
    found = _child(element, *path)
    value = _text(found, "Dt") or _text(found, "DtTm")[:10]
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value[:10])
    except ValueError as error:
        raise StatementError(_("The file has a date that cannot be read: %s") % value) from error


def _amount(element):
    try:
        return Decimal(element.text.strip()), element.get("Ccy", "EUR")
    except (AttributeError, InvalidOperation) as error:
        raise StatementError(_("The file has an amount that cannot be read.")) from error


def _root(data):
    if len(data) > MAX_SIZE:
        raise StatementError(_("The file is too large to be a bank file."))
    # Bank files never declare a document type; refusing one rules out entity tricks.
    if b"<!DOCTYPE" in data[:4096].upper():
        raise StatementError(_("The file is not a bank file Metra can read."))
    try:
        return ET.fromstring(data)
    except ET.ParseError as error:
        raise StatementError(_("The file is not valid XML.")) from error


class Camt(Importer):
    """camt.053 (account statement) and camt.054 (debit and credit
    notification). Both list entries (Ntry); a batch entry holds one
    transaction detail (TxDtls) per payment, and each becomes a line."""

    container = ""  # BkToCstmrStmt or BkToCstmrDbtCdtNtfctn
    report = ""  # Stmt or Ntfctn

    def accepts(self, data):
        head = data[:4096]
        return b"<" in head and self.container.encode() in data[:65536]

    def parse(self, data):
        root = _root(data)
        container = _child(root, self.container)
        if container is None:
            raise StatementError(_("The file is not a %s file.") % self.label)
        statement = ParsedStatement(format=self.name)
        for report in _children(container, self.report):
            account = _text(report, "Acct", "Id", "IBAN")
            statement.account = statement.account or account
            period = _child(report, "FrToDt")
            for name, attr in (("FrDtTm", "starts"), ("ToDtTm", "ends")):
                value = _text(period, name) or _text(period, name.replace("DtTm", "Dt"))
                if value:
                    day = datetime.date.fromisoformat(value[:10])
                    current = getattr(statement, attr)
                    if current is None or (day < current if attr == "starts" else day > current):
                        setattr(statement, attr, day)
            for entry in _children(report, "Ntry"):
                statement.lines += self._lines(entry)
        if statement.starts is None and statement.lines:
            statement.starts = min(line.booked_on for line in statement.lines)
            statement.ends = max(line.booked_on for line in statement.lines)
        return statement

    def _lines(self, entry):
        status = _text(entry, "Sts", "Cd") or _text(entry, "Sts")
        if status and status != "BOOK":
            return []
        amount, currency = _amount(_child(entry, "Amt"))
        sign = -1 if _text(entry, "CdtDbtInd") == "DBIT" else 1
        booked_on = _date(entry, "BookgDt") or _date(entry, "ValDt")
        if booked_on is None:
            raise StatementError(_("An entry in the file has no booking date."))
        common = {
            "booked_on": booked_on,
            "value_date": _date(entry, "ValDt"),
            "currency": currency,
        }
        entry_ref = _text(entry, "AcctSvcrRef")
        details = [tx for d in _children(entry, "NtryDtls") for tx in _children(d, "TxDtls")]
        if not details:
            return [ParsedLine(amount=sign * amount, bank_reference=entry_ref, **common)]
        lines = []
        for index, tx in enumerate(details, start=1):
            # An element without children is falsy, so test for None.
            tx_amount = _child(tx, "Amt")
            if tx_amount is None:
                tx_amount = _child(tx, "AmtDtls", "TxAmt", "Amt")
            if tx_amount is None:
                if len(details) > 1:
                    raise StatementError(_("A payment in a batch entry has no amount."))
                value = amount
            else:
                value, _currency = _amount(tx_amount)
            tx_sign = {"DBIT": -1, "CRDT": 1}.get(_text(tx, "CdtDbtInd"), sign)
            own_ref = _text(tx, "Refs", "AcctSvcrRef")
            if not own_ref and entry_ref:
                own_ref = entry_ref if len(details) == 1 else f"{entry_ref}#{index}"
            party = "Cdtr" if tx_sign < 0 else "Dbtr"
            parties = _child(tx, "RltdPties")
            name = _text(parties, party, "Nm") or _text(parties, party, "Pty", "Nm")
            account = _text(parties, f"{party}Acct", "Id", "IBAN") or _text(
                parties, f"{party}Acct", "Id", "Othr", "Id"
            )
            remittance = _child(tx, "RmtInf")
            reference = _text(remittance, "Strd", "CdtrRefInf", "Ref")
            message = " ".join(
                (u.text or "").strip() for u in _children(remittance, "Ustrd")
            ).strip()
            lines.append(
                ParsedLine(
                    amount=tx_sign * value,
                    reference=reference,
                    message=message[:500],
                    payer_name=name[:200],
                    payer_account=account[:40],
                    bank_reference=own_ref,
                    **common,
                )
            )
        return lines


class Camt054(Camt):
    name = "camt.054"
    label = gettext_lazy("ISO 20022 camt.054 (reference payments)")
    container = "BkToCstmrDbtCdtNtfctn"
    report = "Ntfctn"


class Camt053(Camt):
    name = "camt.053"
    label = gettext_lazy("ISO 20022 camt.053 (account statement)")
    container = "BkToCstmrStmt"
    report = "Stmt"


CORE = [Camt054(), Camt053()]


def importers():
    """The core importers, then those plugins add."""
    return CORE + [item() if isinstance(item, type) else item for item in hooks.get(BANK_IMPORTERS)]


def parse(data):
    """Read a bank file with the first importer that accepts it."""
    for importer in importers():
        if importer.accepts(data):
            return importer.parse(data)
    raise StatementError(
        _("Metra cannot read this file. Download the bank's camt.054 or camt.053 file (XML).")
    )
