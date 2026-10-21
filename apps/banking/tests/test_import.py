import datetime
from decimal import Decimal as D

import pytest

from apps.banking import importers
from apps.banking.matching import AlreadyImported, import_file, normalise
from apps.banking.models import BankStatement, BankTransaction
from apps.invoicing.models import Payment
from apps.invoicing.payments import record_payment
from apps.invoicing.reference import grouped, rf_reference
from apps.plugins.hooks import BANK_IMPORTERS, hooks

from .files import camt053, camt054, entry, tx


def spaced(reference):
    return "000" + grouped(reference)


@pytest.fixture
def october(invoices):
    """A camt.054 batch: one exact payment, one by RF reference, one partial,
    one unknown reference and one without a reference."""
    a, b, c = invoices["Bystigen 4"], invoices["Bystigen 6"], invoices["Bystigen 8"]
    return camt054(
        entry(
            "647.00",
            [
                tx("183.00", spaced(a.reference), ref_id="A1"),
                tx("183.00", rf_reference(b.reference), name="Bo Berg", ref_id="A2"),
                tx("100.00", c.reference, name="Cia Carlsson", ref_id="A3"),
                tx("90.00", "1009", ref_id="A4"),
                tx("91.00", message="Vattenavgift Bystigen 8", ref_id="A5"),
            ],
            ref="BATCH1",
        )
    )


def test_normalise_ignores_spaces_zeros_and_rf():
    assert normalise("000 10016") == "10016"
    assert normalise(rf_reference("10016")) == "10016"
    assert normalise("rf" + rf_reference("10016")[2:]) == "10016"


def test_import_records_exact_payments_and_holds_the_rest(october, invoices):
    statement = import_file("oct.xml", october)

    assert statement.format == "camt.054"
    assert statement.account == "FI2112345600000785"
    lines = {line.bank_reference: line for line in statement.transactions.all()}
    assert {k: (v.status, v.reason) for k, v in lines.items()} == {
        "A1": ("matched", ""),
        "A2": ("matched", ""),
        "A3": ("review", "partial"),
        "A4": ("review", "unknown"),
        "A5": ("review", "no_reference"),
    }
    for name in ["Bystigen 4", "Bystigen 6"]:
        invoices[name].refresh_from_db()
        assert invoices[name].status == "paid"
    assert lines["A1"].payment.amount == D("183.00")
    assert lines["A1"].payment.paid_on == datetime.date(2026, 10, 15)
    assert lines["A1"].payer_name == "Anna Andersson"
    assert lines["A3"].invoice == invoices["Bystigen 8"]
    assert lines["A3"].payment is None
    assert invoices["Bystigen 8"].payments.count() == 0


def test_the_same_file_twice_changes_nothing(october):
    first = import_file("oct.xml", october)

    with pytest.raises(AlreadyImported) as raised:
        import_file("oct-again.xml", october)

    assert raised.value.statement == first
    assert BankStatement.objects.count() == 1
    assert Payment.objects.count() == 2


def test_a_statement_after_the_notification_skips_known_lines(october, invoices):
    import_file("oct.xml", october)
    c = invoices["Bystigen 8"]
    statement = camt053(
        entry("647.00", [tx("183.00", "x", ref_id="A1"), tx("100.00", c.reference, ref_id="A3")]),
        entry("83.00", [tx("83.00", c.reference, ref_id="B1")], booked="2026-10-20"),
        entry("12.40", [tx("12.40", name="Bank", ref_id="F1", debit=True)], debit=True),
    )

    later = import_file("statement.xml", statement)

    assert later.format == "camt.053"
    assert later.skipped == 2
    assert later.starts == datetime.date(2026, 10, 1)
    assert later.ends == datetime.date(2026, 10, 31)
    lines = {line.bank_reference: line for line in later.transactions.all()}
    assert lines["B1"].reason == "partial"  # the 100 € is not recorded yet
    assert lines["F1"].status == "outgoing"
    assert lines["F1"].amount == D("-12.40")
    assert Payment.objects.count() == 2


def test_lines_without_archive_reference_are_still_imported_once(invoices):
    a = invoices["Bystigen 4"]
    data = camt054(entry("183.00", [tx("183.00", a.reference)]))
    other = camt054(entry("183.00", [tx("183.00", a.reference)]), msg_id="N2")

    import_file("one.xml", data)
    again = import_file("two.xml", other)

    assert again.skipped == 1
    assert Payment.objects.filter(invoice=a).count() == 1


def test_paid_too_much_and_already_paid(invoices):
    a, b = invoices["Bystigen 4"], invoices["Bystigen 6"]
    record_payment(b, D("183"), datetime.date(2026, 10, 1))
    data = camt054(
        entry(
            "383.00",
            [tx("200.00", a.reference, ref_id="X1"), tx("183.00", b.reference, ref_id="X2")],
        )
    )

    statement = import_file("x.xml", data)

    reasons = dict(statement.transactions.values_list("bank_reference", "reason"))
    assert reasons == {"X1": "too_much", "X2": "paid"}
    assert Payment.objects.count() == 1


def test_two_payments_in_one_file_for_the_same_invoice(invoices):
    a = invoices["Bystigen 4"]
    data = camt054(
        entry("183.00", [tx("183.00", a.reference, ref_id="Y1")]),
        entry("183.00", [tx("183.00", a.reference, ref_id="Y2")], booked="2026-10-16"),
    )

    statement = import_file("y.xml", data)

    reasons = dict(statement.transactions.values_list("bank_reference", "reason"))
    assert reasons == {"Y1": "", "Y2": "paid"}


def test_pending_entries_are_left_out(invoices):
    a = invoices["Bystigen 4"]
    data = camt054(entry("183.00", [tx("183.00", a.reference, ref_id="P1")], status="PDNG"))

    statement = import_file("p.xml", data)

    assert statement.transactions.count() == 0


def test_an_entry_without_details_is_one_line(db):
    data = camt054(entry("50.00", [], ref="SINGLE").replace("<NtryDtls></NtryDtls>", ""))

    statement = import_file("s.xml", data)

    line = statement.transactions.get()
    assert (line.amount, line.bank_reference, line.reason) == (D("50.00"), "SINGLE", "no_reference")


@pytest.mark.parametrize(
    "data",
    [
        b"Datum;Belopp\n2026-10-15;183,00\n",
        b"<Document><BkToCstmrStmt><Stmt><Ntry><Amt>x</Amt>",
        b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]>'
        b"<Document><BkToCstmrStmt/></Document>",
    ],
)
def test_files_metra_cannot_read_are_refused(db, data):
    with pytest.raises(importers.StatementError):
        import_file("bad", data)
    assert not BankStatement.objects.exists()
    assert not BankTransaction.objects.exists()


class Csv(importers.Importer):
    name = "test-csv"
    label = "Test CSV"

    def accepts(self, data):
        return data.startswith(b"date;")

    def parse(self, data):
        statement = importers.ParsedStatement(format=self.name, account="FI00 TEST")
        for row in data.decode().splitlines()[1:]:
            day, amount, reference = row.split(";")
            statement.lines.append(
                importers.ParsedLine(
                    booked_on=datetime.date.fromisoformat(day),
                    amount=D(amount),
                    reference=reference,
                )
            )
        return statement


def test_plugins_add_formats(invoices):
    from apps.plugins import api

    a = invoices["Bystigen 4"]
    api.add_bank_importer(Csv)
    try:
        data = f"date;amount;ref\n2026-10-15;183.00;{a.reference}".encode()
        statement = import_file("bank.csv", data)
    finally:
        hooks.clear(BANK_IMPORTERS)

    assert statement.format == "test-csv"
    assert statement.account == "FI00TEST"
    assert statement.transactions.get().status == "matched"
