from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.banking.matching import import_file
from apps.banking.models import BankStatement
from apps.invoicing.models import Payment

from .files import camt054, entry, tx

LIST = reverse("banking:statement_list")
UPLOAD = reverse("banking:statement_upload")


def upload(client, data, name="oct.xml"):
    return client.post(UPLOAD, {"file": SimpleUploadedFile(name, data)}, follow=True)


def test_treasurer_imports_a_file(treasurer_client, invoices):
    a, c = invoices["Bystigen 4"], invoices["Bystigen 8"]
    data = camt054(
        entry(
            "283.00",
            [tx("183.00", a.reference, ref_id="A1"), tx("100.00", c.reference, ref_id="A2")],
        )
    )

    response = upload(treasurer_client, data)

    statement = BankStatement.objects.get()
    assert response.redirect_chain[-1][0] == statement.get_absolute_url()
    text = response.content.decode()
    assert "1 payment was recorded on its invoice" in text
    assert "1 payment needs checking by hand" in text
    assert "Less than the amount to pay" in text
    assert statement.imported_by.username == "treasurer"


def test_importing_again_says_so(treasurer_client, invoices):
    data = camt054(entry("183.00", [tx("183.00", invoices["Bystigen 4"].reference)]))
    upload(treasurer_client, data)

    response = upload(treasurer_client, data, "copy.xml")

    assert "This file was imported on" in response.content.decode()
    assert BankStatement.objects.count() == 1
    assert Payment.objects.count() == 1


def test_a_file_metra_cannot_read_shows_an_error(treasurer_client, db):
    response = upload(treasurer_client, b"not a bank file")

    assert response.status_code == 200
    assert "Metra cannot read this file" in response.content.decode()
    assert not BankStatement.objects.exists()


def test_board_sees_bank_files_but_cannot_import(board_client, invoices):
    statement = import_file("oct.xml", camt054(entry("1.00", [tx("1.00", ref_id="Z")])))

    response = board_client.get(LIST)
    assert response.status_code == 200
    assert statement.file_name in response.content.decode()
    assert UPLOAD not in response.content.decode()
    assert board_client.get(statement.get_absolute_url()).status_code == 200
    assert upload(board_client, camt054(entry("2.00", []))).status_code == 403


def test_read_only_cannot_see_bank_files(role_client, db):
    client = role_client("Read-only")

    assert client.get(LIST).status_code == 403


def test_invoice_list_links_to_bank_files(treasurer_client, db):
    response = treasurer_client.get(reverse("invoicing:invoice_list"))

    assert LIST in response.content.decode()
