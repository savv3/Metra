import datetime

import pytest

from apps.invoicing.reference import (
    ReferenceError,
    fi_reference,
    grouped,
    invoice_base,
    is_valid_fi,
    is_valid_rf,
    rf_reference,
    virtual_barcode,
)


def test_finnish_reference_check_digit():
    # Examples from the Finnish banks' reference number guide.
    assert fi_reference("1234561") == "12345614"
    assert is_valid_fi("86851 62596 19897")
    assert not is_valid_fi("86851 62596 19898")
    assert fi_reference("100") == "1009"
    with pytest.raises(ReferenceError):
        fi_reference("12")


def test_rf_reference_iso_11649():
    assert rf_reference("539007547034") == "RF18539007547034"  # the standard's example
    assert is_valid_rf("RF18 5390 0754 7034")
    assert not is_valid_rf("RF19 5390 0754 7034")
    assert is_valid_rf(rf_reference(fi_reference("10001")))


def test_grouping_for_reading():
    assert grouped("868516259619897") == "86851 62596 19897"
    assert grouped("RF18539007547034") == "RF18 5390 0754 7034"


def test_invoice_references_are_unique_per_number():
    assert invoice_base(1) == "10001"
    assert fi_reference(invoice_base(1)) != fi_reference(invoice_base(10))


def test_virtual_barcode_version_4():
    # Example 1 of the Finance Finland virtual barcode specification.
    code = virtual_barcode(
        "FI79 4405 2020 0360 82", "4883.15", "86851 62596 19897", datetime.date(2010, 6, 12)
    )
    assert code == "479440520200360820048831500000000868516259619897100612"
    assert len(code) == 54


def test_virtual_barcode_version_5_for_rf():
    code = virtual_barcode("FI58 1017 1000 0001 22", "482.99", "RF18539007547034", None)
    # version, account, euros, cents, RF check digits, reference (21), no due date
    assert (
        code
        == "5" + "5810171000000122" + "000482" + "99" + "18" + "539007547034".zfill(21) + "000000"
    )
    assert len(code) == 54


def test_no_barcode_without_finnish_iban_or_for_odd_amounts():
    date = datetime.date(2026, 11, 1)
    assert virtual_barcode("SE45 5000 0000 0583 9825 7466", "10", "1009", date) == ""
    assert virtual_barcode("FI79 4405 2020 0360 82", "-1", "1009", date) == ""
    assert virtual_barcode("FI79 4405 2020 0360 82", "1000000", "1009", date) == ""
