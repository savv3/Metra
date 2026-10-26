import datetime
from decimal import Decimal as D

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.invoicing.models import (
    BillingSettings,
    FeeLine,
    FeeTier,
    Invoice,
    InvoiceLine,
    InvoiceRun,
    LockedError,
)
from apps.invoicing.money import cents, vat_of
from apps.invoicing.runs import build_run, rebuild_invoice, recipient, tiered
from apps.register.models import Organisation, Person, UnitContact


def make_run(plan, rounds=(), period="2026"):
    run = InvoiceRun.objects.create(period_label=period)
    run.plans.add(plan)
    run.rounds.add(*rounds)
    return run


def test_money_rounds_half_up_to_cents():
    assert cents(D("0.125")) == D("0.13")
    assert cents(D("2.675")) == D("2.68")
    assert vat_of(D("100.00"), D("25.5")) == D("25.50")
    assert vat_of(D("0.10"), D("25.5")) == D("0.03")


def test_run_builds_base_fee_and_usage(plan, rounds, make_household, billing):
    last, current = rounds
    unit = make_household("Bystigen 4", [(last, "300"), (current, "342")], first_name="Anna")

    created, _rebuilt, skipped = build_run(make_run(plan, [current]))

    invoice = Invoice.objects.get()
    lines = [
        (line.description, line.quantity, line.unit_label, line.unit_price)
        for line in invoice.lines.all()
    ]
    assert (created, skipped) == (1, [])
    assert invoice.unit == unit and invoice.problems == []
    assert lines == [
        ("Grundavgift 2026", D("1"), "st", D("120")),
        ("Vatten 2026", D("42"), "m³", D("1.50")),
    ]
    # Not VAT registered (the default): no VAT, total is the sum.
    assert (invoice.total_net, invoice.total_vat, invoice.total) == (D("183"), D("0"), D("183"))


def test_vat_is_counted_per_rate_when_registered(plan, rounds, make_household, billing):
    billing.vat_registered = True
    billing.save()
    plan.lines.filter(kind="usage").update(vat_rate=D("14"))
    last, current = rounds
    make_household("A", [(last, "300"), (current, "342")], first_name="Anna")

    build_run(make_run(plan, [current]))

    invoice = Invoice.objects.get()
    assert invoice.vat_breakdown() == [
        (D("14.00"), D("63.00"), D("8.82")),
        (D("25.50"), D("120.00"), D("30.60")),
    ]
    assert (invoice.total_net, invoice.total_vat, invoice.total) == (
        D("183.00"),
        D("39.42"),
        D("222.42"),
    )


def test_missing_or_odd_readings_are_flagged_not_guessed(plan, rounds, make_household, billing):
    last, current = rounds
    make_household("No reading", [(last, "300")], first_name="A")
    make_household("Lower", [(last, "300"), (current, "250")], first_name="B")
    make_household("First reading", [(current, "40")], first_name="C")

    build_run(make_run(plan, [current]))

    by_unit = {i.unit.name: i for i in Invoice.objects.all()}
    for name in ["No reading", "Lower", "First reading"]:
        invoice = by_unit[name]
        assert invoice.problems, name
        assert [line.description for line in invoice.lines.all()] == ["Grundavgift 2026"]


def test_units_without_contact_are_skipped_and_archived_ignored(plan, make_household):
    lonely = make_household("Lonely")
    make_household("Gone", first_name="G").archive()
    make_household("Inactive", first_name="I").__class__.objects.filter(name="Inactive").update(
        status="inactive"
    )

    created, _rebuilt, skipped = build_run(make_run(plan))

    assert created == 0
    assert skipped == [lonely]


def test_recipient_is_the_billing_contact_then_owner(make_household):
    unit = make_household("A", first_name="Owner")
    assert recipient(unit).first_name == "Owner"
    payer = Person.objects.create(first_name="Payer")
    UnitContact.objects.create(unit=unit, person=payer, role="billing")
    assert recipient(unit) == payer


def test_fee_line_conditions_and_tags(plan, make_household, household):
    from apps.register.models import Tag

    FeeLine.objects.create(
        plan=plan,
        description="Sommaravgift",
        unit_price=D("10"),
        condition_field="connection",
        condition_value="Sommar",
        order=5,
    )
    plan.lines.filter(kind="usage").delete()
    summer = make_household("Summer", first_name="S")
    summer.custom_data = {"connection": "Sommar"}
    summer.save()
    make_household("All year", first_name="Y")

    build_run(make_run(plan))

    lines = {
        i.unit.name: [line.description for line in i.lines.all()] for i in Invoice.objects.all()
    }
    assert lines == {
        "Summer": ["Grundavgift 2026", "Sommaravgift"],
        "All year": ["Grundavgift 2026"],
    }
    north = Tag.objects.create(name="North")
    plan.tag = north
    plan.save()
    plan.refresh_from_db()
    assert not plan.applies_to(summer)


def test_tiers_split_usage(plan):
    line = plan.lines.get(kind="usage")
    FeeTier.objects.create(line=line, up_to=D("50"), unit_price=D("1"))
    FeeTier.objects.create(line=line, up_to=None, unit_price=D("2"))

    assert tiered(line, D("30")) == [(D("30"), D("1"), "0–50")]
    parts = tiered(line, D("80"))
    assert [(q, p) for q, p, _label in parts] == [(D("50"), D("1")), (D("30"), D("2"))]
    assert tiered(plan.lines.get(kind="fixed"), D("5")) == [(D("5"), D("120"), "")]


def test_rebuild_after_entering_the_missing_reading(plan, rounds, make_household, billing):
    from apps.readings.models import Reading

    last, current = rounds
    unit = make_household("A", [(last, "300")], first_name="A")
    build_run(make_run(plan, [current]))
    invoice = Invoice.objects.get()
    assert invoice.problems

    Reading.objects.create(round=current, unit=unit, value=D("320"))
    rebuild_invoice(invoice)

    invoice.refresh_from_db()
    assert invoice.problems == []
    assert invoice.total == D("150.00")


def test_issuing_numbers_without_gaps_and_locks(plan, rounds, make_household, billing, make_user):
    billing.number_prefix = "2026-"
    billing.next_number = 41
    billing.save()
    last, current = rounds
    for name in ["A", "B"]:
        make_household(name, [(last, "1"), (current, "2")], first_name=name)
    build_run(make_run(plan, [current]))
    user = make_user("treasurer", "Treasurer")

    first, second = Invoice.objects.order_by("unit__name")
    first.issue(user)
    second.issue(user)

    assert (first.number, second.number) == ("2026-41", "2026-42")
    assert BillingSettings.current().next_number == 43
    assert first.issue_date == timezone.localdate()
    assert first.due_date == timezone.localdate() + datetime.timedelta(days=14)
    assert first.seller["business_id"] == "1234567-8"
    assert first.seller["iban"] == "FI21 1234 5600 0007 85"
    assert first.seller["vat_exemption_text"].startswith("Ej momsskyldig")
    assert first.buyer == {
        "name": "A",
        "address": ["A", "22240 Hammarland"],
        "email": "",
        "unit": "A",
    }
    first.note = "changed"
    with pytest.raises(LockedError):
        first.save()
    with pytest.raises(LockedError):
        first.delete()
    with pytest.raises(LockedError):
        first.lines.first().delete()
    with pytest.raises(LockedError):
        InvoiceLine.objects.create(invoice=first, description="x", unit_price=1)


def test_issued_invoices_keep_what_they_said(plan, rounds, make_household, billing):
    last, current = rounds
    unit = make_household("A", [(last, "1"), (current, "2")], first_name="Anna")
    build_run(make_run(plan, [current]))
    invoice = Invoice.objects.get()
    invoice.issue()

    person = unit.unit_contacts.get().person
    person.first_name = "Annika"
    person.save()
    billing.iban = "FI00 0000"
    billing.save()

    invoice.refresh_from_db()
    assert invoice.buyer["name"] == "Anna"
    assert invoice.seller["iban"] == "FI21 1234 5600 0007 85"


def test_the_supply_period_is_kept_and_credited(plan, rounds, make_household, billing):
    """VAT follows the supply (AVL 15 §), so the invoice states it (AVL 209 e §)."""
    last, current = rounds
    make_household("A", [(last, "1"), (current, "2")], first_name="Anna")
    build_run(make_run(plan, [current]))
    invoice = Invoice.objects.get()
    invoice.supply_end = datetime.date(2026, 12, 31)
    invoice.save()
    invoice.issue()

    assert invoice.supply_start == invoice.supply_end == datetime.date(2026, 12, 31)
    assert invoice.supply_date == datetime.date(2026, 12, 31)
    note = invoice.make_credit_note()
    assert note.supply_end == invoice.supply_end


def test_without_a_supply_period_the_invoice_date_is_the_supply_date(
    plan, rounds, make_household, billing
):
    last, current = rounds
    make_household("A", [(last, "1"), (current, "2")], first_name="Anna")
    build_run(make_run(plan, [current]))
    invoice = Invoice.objects.get()
    invoice.issue()

    assert invoice.supply_start == invoice.supply_end == invoice.issue_date


def test_an_invoice_that_cannot_be_issued_says_why(make_household, billing, household):
    unit = make_household("A", first_name="Anna")
    unit.street_address = unit.city = unit.postal_code = ""
    unit.save()
    invoice = Invoice.objects.create(unit=unit, person=unit.unit_contacts.get().person)

    problems = invoice.check_can_issue()

    assert len(problems) == 2  # no lines, no address
    with pytest.raises(ValidationError):
        invoice.issue()
    assert BillingSettings.current().next_number == 1


def test_credit_notes_negate_and_cannot_overcredit(plan, rounds, make_household, billing):
    last, current = rounds
    make_household("A", [(last, "300"), (current, "342")], first_name="Anna")
    build_run(make_run(plan, [current]))
    invoice = Invoice.objects.get()
    invoice.issue()

    partial = invoice.make_credit_note()
    partial.lines.filter(description__startswith="Grundavgift").delete()
    partial.compute_totals()
    partial.save()
    partial.issue()

    invoice.refresh_from_db()
    assert partial.kind == Invoice.Kind.CREDIT_NOTE and partial.credits == invoice
    assert partial.total == D("-63.00")
    assert partial.due_date is None
    assert partial.number == "2"
    assert invoice.status == Invoice.Status.ISSUED
    assert invoice.creditable_amount() == D("120.00")

    too_much = invoice.make_credit_note()
    assert "credits more" in " ".join(str(p) for p in too_much.check_can_issue())
    too_much.lines.filter(description__startswith="Vatten").delete()
    too_much.issue()

    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.CREDITED
    with pytest.raises(ValidationError):
        partial.make_credit_note()


def test_the_next_number_cannot_go_back(plan, rounds, make_household, billing):
    last, current = rounds
    make_household("A", [(last, "1"), (current, "2")], first_name="A")
    build_run(make_run(plan, [current]))
    Invoice.objects.get().issue()
    billing.refresh_from_db()

    billing.next_number = 1
    with pytest.raises(ValidationError):
        billing.full_clean()


def test_invoices_need_the_sellers_legal_details(plan, rounds, make_household, billing):
    last, current = rounds
    make_household("A", [(last, "1"), (current, "2")], first_name="A")
    build_run(make_run(plan, [current]))
    invoice = Invoice.objects.get()
    organisation = Organisation.current()

    organisation.business_id = ""
    organisation.save()
    assert any("business ID" in str(p) for p in invoice.check_can_issue())

    organisation.business_id = "1234567-8"
    organisation.save()
    billing.vat_registered = True
    billing.save()
    assert any("VAT number" in str(p) for p in invoice.check_can_issue())

    organisation.vat_number = "FI12345678"
    organisation.save()
    assert invoice.check_can_issue() == []
