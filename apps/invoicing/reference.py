"""Finnish payment references and the bank barcode.

- The Finnish reference number (viitenumero): 3–19 digits plus a check digit
  from the weights 7, 3, 1 counted from the right.
- The RF creditor reference (ISO 11649): "RF", two check digits (mod 97) and
  the reference. Any Finnish reference can be written as an RF reference.
- The virtual barcode (virtuaaliviivakoodi): 54 digits that a bank app reads
  for the account, amount, reference and due date. Version 4 carries a Finnish
  reference, version 5 an RF reference. It needs a Finnish IBAN.
"""

import re
from decimal import Decimal

WEIGHTS = (7, 3, 1)


class ReferenceError(ValueError):
    pass


def fi_check_digit(base):
    if not base.isdigit() or not 3 <= len(base) <= 19:
        raise ReferenceError(f"A reference base is 3–19 digits, not {base!r}")
    total = sum(int(d) * WEIGHTS[i % 3] for i, d in enumerate(reversed(base)))
    return str((10 - total % 10) % 10)


def fi_reference(base):
    """The Finnish reference for a base number: the base plus its check digit."""
    base = str(base)
    return base + fi_check_digit(base)


def is_valid_fi(reference):
    digits = re.sub(r"\s", "", reference)
    return digits.isdigit() and 4 <= len(digits) <= 20 and fi_reference(digits[:-1]) == digits


def _mod97(text):
    """ISO 7064 mod 97-10 of letters and digits (A = 10 … Z = 35)."""
    number = "".join(str(int(c, 36)) for c in text.upper())
    return int(number) % 97


def rf_reference(reference):
    """The RF creditor reference for a reference, e.g. RF33 1234 5…"""
    body = re.sub(r"\s", "", reference).upper()
    check = 98 - _mod97(body + "RF00")
    return f"RF{check:02d}{body}"


def is_valid_rf(reference):
    text = re.sub(r"\s", "", reference).upper()
    return text.startswith("RF") and len(text) <= 25 and _mod97(text[4:] + text[:4]) == 1


def grouped(reference):
    """For people to read: Finnish references in groups of five from the right,
    RF references in groups of four from the left."""
    text = re.sub(r"\s", "", reference)
    if text.upper().startswith("RF"):
        return " ".join(text[i : i + 4] for i in range(0, len(text), 4))
    groups = []
    while text:
        groups.insert(0, text[-5:])
        text = text[:-5]
    return " ".join(groups)


def invoice_base(sequence):
    """The reference base for an invoice: 1 followed by the number, at least 5 digits."""
    return f"1{sequence:04d}"


def virtual_barcode(iban, amount, reference, due_date):
    """The 54-digit virtual barcode, or "" when it cannot be made (not a Finnish
    IBAN, an amount of a million euros or more, or a negative amount)."""
    iban = re.sub(r"\s", "", iban or "").upper()
    if not (iban.startswith("FI") and len(iban) == 18 and iban[2:].isdigit()):
        return ""
    amount = Decimal(amount)
    if amount < 0 or amount >= Decimal("1000000"):
        return ""
    euros, cents = divmod(int((amount * 100).to_integral_value()), 100)
    due = due_date.strftime("%y%m%d") if due_date else "000000"
    reference = re.sub(r"\s", "", reference).upper()
    if reference.startswith("RF"):
        check, body = reference[2:4], reference[4:]
        return f"5{iban[2:]}{euros:06d}{cents:02d}{check}{body.zfill(21)}{due}"
    return f"4{iban[2:]}{euros:06d}{cents:02d}000{reference.zfill(20)}{due}"
