import csv
import io
from pathlib import Path

import pytest
from auditlog.models import LogEntry
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse

from apps.register import csv_io
from apps.register.models import Person, Tag, Unit, UnitContact, UnitType

EXAMPLE = Path(settings.BASE_DIR) / "static" / "examples" / "hushall-exempel.csv"


@pytest.fixture
def water(db):
    call_command("load_sample_setup", "water", stdout=io.StringIO())
    return UnitType.objects.get(name="Hushåll")


def upload(text, name="import.csv", bom=False):
    data = text.encode("utf-8")
    return SimpleUploadedFile(name, (b"\xef\xbb\xbf" if bom else b"") + data, "text/csv")


def run_import(client, unit_type, text, mapping=None, skip_existing=True, default_role="owner"):
    """Go through upload and column mapping; return the preview response."""
    data = {"unit_type": unit_type.pk, "file": upload(text)}
    if skip_existing:
        data["skip_existing"] = "on"
    response = client.post(reverse("register:unit_import"), data)
    assert response.status_code == 302, response.context["form"].errors
    page = client.get(reverse("register:unit_import_map"))
    chosen = {name: value for name, value in page.context["form"].initial.items() if value}
    chosen.update(mapping or {})
    chosen["default_role"] = default_role
    response = client.post(reverse("register:unit_import_map"), chosen)
    assert response.status_code == 302, response.context["form"].errors
    return client.get(reverse("register:unit_import_preview"))


def rows_by_line(preview):
    return {row.line: row for row in preview.context["results"]}


# Reading files


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Namn;Ort\nA;B\n", ";"),
        ("Name,City\nA,B\n", ","),
        ("Name\tCity\nA\tB\n", "\t"),
        ("Name\nA\n", ","),
    ],
)
def test_separator_is_detected(text, expected):
    assert csv_io.detect_delimiter(text) == expected


@pytest.mark.parametrize("bom", [True, False])
def test_reads_utf8_with_or_without_bom(bom):
    headers, rows = csv_io.read_csv(upload("Namn;Ort\nÅkervägen 1;Jomala\n\n;\n", bom=bom))

    assert headers == ["Namn", "Ort"]
    assert rows == [["Åkervägen 1", "Jomala"]]  # blank rows are dropped


def test_rejects_files_that_are_not_utf8():
    file = SimpleUploadedFile("x.csv", "Namn\nÅkervägen\n".encode("latin-1"))

    with pytest.raises(csv_io.CSVError, match="UTF-8"):
        csv_io.read_csv(file)


def test_upload_reports_unreadable_files(board_client, water):
    response = board_client.post(
        reverse("register:unit_import"), {"unit_type": water.pk, "file": upload("Namn\n")}
    )

    assert response.status_code == 200
    assert response.context["form"].errors["file"]


# Mapping


def test_columns_are_guessed_from_swedish_and_english_headers(water):
    targets = csv_io.build_targets(water)
    headers = ["Namn", "E-post", "Mätarnummer", "property_id", "Postal code", "Roll", "Okänd"]

    mapping = csv_io.guess_mapping(targets, headers)

    assert mapping == {
        "unit:name": 0,
        "contact:email": 1,
        "custom:meter_number": 2,
        "custom:property_id": 3,
        "unit:postal_code": 4,
        "contact:role": 5,
    }


def test_unit_name_must_be_mapped(board_client, water):
    board_client.post(
        reverse("register:unit_import"), {"unit_type": water.pk, "file": upload("X;Y\n1;2\n")}
    )

    response = board_client.post(reverse("register:unit_import_map"), {"default_role": "owner"})

    assert response.status_code == 200
    assert "unit:name" in response.context["form"].errors


# Import


def test_example_file_imports_cleanly(board_client, water):
    preview = run_import(board_client, water, EXAMPLE.read_text(encoding="utf-8-sig"))
    assert preview.context["error_count"] == 0
    assert preview.context["ok_count"] == 3

    response = board_client.post(reverse("register:unit_import_preview"))

    assert response.status_code == 302
    unit = Unit.objects.get(name="Byvägen 4")
    assert unit.unit_type == water
    assert unit.custom_data == {
        "property_id": "478-401-1-23",
        "meter_number": "M-1001",
        "connection": "Året runt",
    }
    owner = UnitContact.objects.get(unit=unit)
    assert (owner.person.email, owner.role) == ("anna@example.com", "owner")
    assert UnitContact.objects.get(unit__name="Skogsstigen 2").role == "billing"
    bo = Person.objects.get(first_name="Bo")
    assert bo.preferred_channel == "sms"
    assert "register_csv_import" not in board_client.session


def test_values_are_normalised(board_client, water):
    Tag.objects.create(name="Norr")
    text = (
        "Namn;Status;Land;Startdatum;Taggar;Fastighetsbeteckning;Anslutning\n"
        "A;Inaktiv;Åland;1.4.2020;norr;1;sommar\n"
    )
    run_import(board_client, water, text)

    board_client.post(reverse("register:unit_import_preview"))

    unit = Unit.objects.get(name="A")
    assert (unit.status, unit.country, str(unit.start_date)) == ("inactive", "AX", "2020-04-01")
    assert list(unit.tags.values_list("name", flat=True)) == ["Norr"]
    assert unit.custom_data["connection"] == "Sommar"


def test_rows_with_errors_are_reported_and_nothing_is_imported(board_client, water):
    text = (
        "Namn;Fastighetsbeteckning;Anslutning;Taggar;Förnamn;E-post;Roll\n"
        "Bra;1;;;Anna;anna@example.com;Ägare\n"
        ";2;;;;;\n"
        "Fel val;3;Vinter;;;;\n"
        "Utan id;;;;;;\n"
        "Okänd tagg;4;;Söder;;;\n"
        "Fel e-post;5;;;Bo;inte-en-adress;\n"
        "Fel roll;6;;;Cia;cia@example.com;Chef\n"
    )
    preview = run_import(board_client, water, text)
    rows = rows_by_line(preview)

    assert rows[2].status == "ok"
    for line in range(3, 9):
        assert rows[line].status == "error", line
        assert rows[line].errors, line
    assert any("Söder" in error for error in rows[6].errors)
    assert preview.context["error_count"] == 6

    response = board_client.post(reverse("register:unit_import_preview"))

    assert response.status_code == 200
    assert not Unit.objects.exists()
    assert not Person.objects.exists()


def test_existing_units_are_skipped_when_asked(board_client, water):
    Unit.objects.create(unit_type=water, name="Byvägen 4")

    preview = run_import(board_client, water, "Namn;Fastighetsbeteckning\nbyvägen 4;1\nNy;2\n")
    rows = rows_by_line(preview)
    assert (rows[2].status, rows[3].status) == ("skip", "ok")

    board_client.post(reverse("register:unit_import_preview"))
    assert Unit.objects.filter(name__iexact="byvägen 4").count() == 1
    assert Unit.objects.filter(name="Ny").exists()


def test_duplicate_names_in_the_file_are_errors_when_skipping(board_client, water):
    preview = run_import(board_client, water, "Namn;Fastighetsbeteckning\nA;1\nA;2\n")

    assert rows_by_line(preview)[3].status == "error"


def test_existing_units_can_be_imported_again(board_client, water):
    Unit.objects.create(unit_type=water, name="A")

    run_import(board_client, water, "Namn;Fastighetsbeteckning\nA;1\n", skip_existing=False)
    board_client.post(reverse("register:unit_import_preview"))

    assert Unit.objects.filter(name="A").count() == 2


def test_people_are_matched_by_email_then_phone(board_client, water, person):
    by_phone = Person.objects.create(
        first_name="Bo", phone="+358 40 111 2222", preferred_channel="sms"
    )
    text = (
        "Namn;Fastighetsbeteckning;Förnamn;E-post;Telefon\n"
        "A;1;Anna;ANNA@example.com;\n"
        "B;2;Bo;;+358401112222\n"
        "C;3;Ny;ny@example.com;\n"
        "D;4;Ny;ny@example.com;\n"
    )
    preview = run_import(board_client, water, text)
    rows = rows_by_line(preview)
    assert rows[2].person == person
    assert rows[3].person == by_phone
    assert "line 4" in rows[5].contact or "rad 4" in rows[5].contact

    board_client.post(reverse("register:unit_import_preview"))

    assert Person.objects.count() == 3
    assert Unit.objects.get(name="A").contacts.get() == person
    assert Unit.objects.get(name="D").contacts.get() == Person.objects.get(email="ny@example.com")


def test_default_role_is_used_when_the_file_has_none(board_client, water):
    run_import(
        board_client, water, "Namn;Fastighetsbeteckning;Förnamn\nA;1;Anna\n", default_role="contact"
    )
    board_client.post(reverse("register:unit_import_preview"))

    assert UnitContact.objects.get().role == "contact"


def test_import_is_rolled_back_when_saving_fails(board_client, water, monkeypatch):
    run_import(board_client, water, "Namn;Fastighetsbeteckning;Förnamn\nA;1;Anna\nB;2;Bo\n")

    def fail(*args, **kwargs):
        if Unit.objects.count() == 2:
            raise RuntimeError("disk full")
        return original(*args, **kwargs)

    original = UnitContact.objects.get_or_create
    monkeypatch.setattr(UnitContact.objects, "get_or_create", fail)

    with pytest.raises(RuntimeError):
        board_client.post(reverse("register:unit_import_preview"))

    assert not Unit.objects.exists()
    assert not Person.objects.exists()


def test_imported_records_are_in_the_audit_log(board_client, water):
    run_import(board_client, water, "Namn;Fastighetsbeteckning;Förnamn\nA;1;Anna\n")
    board_client.post(reverse("register:unit_import_preview"))

    unit = Unit.objects.get()
    entry = LogEntry.objects.get_for_object(unit).get(action=LogEntry.Action.CREATE)
    assert entry.actor.username == "board"
    assert LogEntry.objects.get_for_object(Person.objects.get()).filter(actor__username="board")


@pytest.mark.parametrize("role", ["Treasurer", "Read-only"])
def test_only_board_and_admin_can_import(role_client, water, role):
    client = role_client(role)

    for name in [
        "register:unit_import",
        "register:unit_import_map",
        "register:unit_import_preview",
    ]:
        assert client.get(reverse(name)).status_code == 403


def test_import_button_shows_for_board_only(board_client, role_client):
    assert (
        reverse("register:unit_import")
        in board_client.get(reverse("register:unit_list")).content.decode()
    )


def test_import_steps_need_an_uploaded_file(board_client):
    assert board_client.get(reverse("register:unit_import_preview")).url == reverse(
        "register:unit_import"
    )


# Export


def parse(response):
    content = response.content.decode("utf-8")
    assert content.startswith("﻿")
    return list(csv.reader(io.StringIO(content[1:]), delimiter=";"))


def test_unit_export_follows_filters_and_includes_custom_fields(role_client, water, person):
    unit = Unit.objects.create(
        unit_type=water, name="Åvägen 1", custom_data={"meter_number": "M-1"}
    )
    UnitContact.objects.create(unit=unit, person=person, role="owner")
    Unit.objects.create(unit_type=water, name="Annan", status="inactive")
    client = role_client("Read-only")

    response = client.get(reverse("register:unit_export"), {"status": "active"})

    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert response["Content-Disposition"].startswith("attachment;")
    assert response["Cache-Control"] == "no-store"
    header, *rows = parse(response)
    assert "Mätarnummer" in header and "Fastighetsbeteckning" in header
    assert [row[0] for row in rows] == ["Åvägen 1"]
    assert rows[0][header.index("Mätarnummer")] == "M-1"
    assert "Anna Lindqvist" in rows[0][header.index("Kontakter")]


def test_person_export(role_client, person, unit):
    UnitContact.objects.create(unit=unit, person=person, role="owner")

    header, *rows = parse(role_client("Treasurer").get(reverse("register:person_export")))

    assert header[:3] == ["Förnamn", "Efternamn", "E-post"]
    assert rows[0][:3] == ["Anna", "Lindqvist", "anna@example.com"]
    assert "Byvägen 4" in rows[0][-1]


def test_export_keeps_phone_numbers_but_defuses_formulas(role_client, db):
    Person.objects.create(first_name="=HYPERLINK(1)", phone="+358 40 123", preferred_channel="sms")

    header, *rows = parse(role_client("Read-only").get(reverse("register:person_export")))

    assert rows[0][0] == "'=HYPERLINK(1)"
    assert rows[0][3] == "+358 40 123"


def test_export_is_logged_with_who_and_what(role_client, unit):
    role_client("Read-only").get(reverse("register:unit_export"))

    entry = LogEntry.objects.get(additional_data__export="csv")
    assert entry.actor.username == "read-only"
    assert entry.additional_data["ids"] == [unit.pk]


@pytest.mark.django_db
def test_export_needs_login_and_view_permission(client, make_user):
    for name in ["register:unit_export", "register:person_export"]:
        assert client.get(reverse(name)).status_code == 302
    client.force_login(make_user("nobody"))
    for name in ["register:unit_export", "register:person_export"]:
        assert client.get(reverse(name)).status_code == 403


def test_exported_file_can_be_imported_again(board_client, water):
    Unit.objects.create(unit_type=water, name="Runt", custom_data={"property_id": "9"})
    exported = board_client.get(reverse("register:unit_export")).content.decode("utf-8")
    Unit.objects.all().delete()

    preview = run_import(board_client, water, exported.lstrip("﻿"))

    assert preview.context["error_count"] == 0
    board_client.post(reverse("register:unit_import_preview"))
    assert Unit.objects.get().custom_data == {"property_id": "9"}
