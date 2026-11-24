from decimal import Decimal as D

import pytest
from django.urls import reverse

from apps.invoicing.models import Invoice, InvoiceRun


@pytest.fixture
def run(treasurer_client, plan, rounds, make_household, billing):
    last, current = rounds
    make_household("Bystigen 4", [(last, "300"), (current, "342")], first_name="Anna")
    make_household("Bystigen 6", [(last, "100")], first_name="Bo")
    response = treasurer_client.post(
        reverse("invoicing:run_create"),
        {
            "period_label": "2026",
            "supply_start": "2026-01-01",
            "supply_end": "2026-12-31",
            "plans": [plan.pk],
            "rounds": [current.pk],
        },
    )
    run = InvoiceRun.objects.get()
    assert response.url == run.get_absolute_url()
    return run


def test_a_run_says_what_period_it_supplies(treasurer_client, run):
    invoice = run.invoices.first()
    assert (str(invoice.supply_start), str(invoice.supply_end)) == ("2026-01-01", "2026-12-31")
    assert invoice.supply_display == "1.1.2026–31.12.2026"
    response = treasurer_client.post(
        reverse("invoicing:run_create"),
        {"period_label": "2027", "supply_start": "2027-12-31", "supply_end": "2027-01-01"},
    )
    assert InvoiceRun.objects.count() == 1
    assert response.status_code == 200


def test_run_page_lists_drafts_to_check(treasurer_client, run):
    page = treasurer_client.get(run.get_absolute_url(), HTTP_ACCEPT_LANGUAGE="en").content.decode()

    assert "1 draft to check" in page
    assert "Bystigen 6" in page


def test_issue_all_holds_back_drafts_with_problems(treasurer_client, run):
    treasurer_client.post(reverse("invoicing:run_issue", args=[run.pk]))

    statuses = dict(run.invoices.values_list("unit__name", "status"))
    assert statuses == {"Bystigen 4": "issued", "Bystigen 6": "draft"}


def test_edit_a_draft_and_issue_it(treasurer_client, run):
    invoice = run.invoices.get(unit__name="Bystigen 6")
    lines = list(invoice.lines.all())
    data = {
        "lines-TOTAL_FORMS": "2",
        "lines-INITIAL_FORMS": "1",
        "lines-MIN_NUM_FORMS": "0",
        "lines-MAX_NUM_FORMS": "1000",
        "lines-0-id": lines[0].pk,
        "lines-0-description": lines[0].description,
        "lines-0-quantity": "1",
        "lines-0-unit_label": "st",
        "lines-0-unit_price": "120",
        "lines-0-vat_rate": "25,5",
        "lines-1-description": "Uppskattad förbrukning",
        "lines-1-quantity": "40",
        "lines-1-unit_label": "m³",
        "lines-1-unit_price": "1,50",
        "lines-1-vat_rate": "25,5",
        "note": "Mätaren lästes inte av.",
    }

    treasurer_client.post(invoice.get_absolute_url(), data)
    invoice.refresh_from_db()
    assert invoice.total == D("180.00")

    treasurer_client.post(reverse("invoicing:invoice_issue", args=[invoice.pk]))
    invoice.refresh_from_db()
    assert invoice.status == "issued" and invoice.number


def test_issued_invoice_page_offers_a_credit_note(treasurer_client, run):
    invoice = run.invoices.get(unit__name="Bystigen 4")
    invoice.issue()

    page = treasurer_client.get(invoice.get_absolute_url()).content.decode()
    response = treasurer_client.post(reverse("invoicing:invoice_credit", args=[invoice.pk]))

    assert reverse("invoicing:invoice_credit", args=[invoice.pk]) in page
    note = Invoice.objects.get(kind="credit_note")
    assert response.url == note.get_absolute_url()
    assert note.total == -invoice.total


def test_invoice_list_filters(treasurer_client, run):
    run.invoices.get(unit__name="Bystigen 4").issue()

    drafts = treasurer_client.get(reverse("invoicing:invoice_list"), {"status": "draft"})
    issued = treasurer_client.get(
        reverse("invoicing:invoice_list"), {"status": "issued"}, HTTP_HX_TARGET="results"
    )

    assert [i.unit.name for i in drafts.context["page"]] == ["Bystigen 6"]
    assert issued.templates[0].name == "invoicing/_invoice_results.html"
    assert [i.unit.name for i in issued.context["page"]] == ["Bystigen 4"]


def test_overdue_filter(treasurer_client, run):
    import datetime

    invoice = run.invoices.get(unit__name="Bystigen 4")
    invoice.issue()
    Invoice.objects.filter(pk=invoice.pk).update(due_date=datetime.date(2020, 1, 1))

    overdue = treasurer_client.get(reverse("invoicing:invoice_list"), {"status": "overdue"})

    assert [i.pk for i in overdue.context["page"]] == [invoice.pk]


def test_board_can_look_but_not_change(role_client, run):
    board = role_client("Board")
    invoice = run.invoices.first()

    assert board.get(reverse("invoicing:invoice_list")).status_code == 200
    assert board.get(invoice.get_absolute_url()).status_code == 200
    assert board.post(reverse("invoicing:invoice_issue", args=[invoice.pk])).status_code == 403
    assert board.get(reverse("invoicing:run_create")).status_code == 403
    assert (
        'name="lines-0-description"' not in board.get(invoice.get_absolute_url()).content.decode()
    )


def test_read_only_cannot_see_invoices(role_client, run):
    client = role_client("Read-only")

    assert client.get(reverse("invoicing:invoice_list")).status_code == 403
    assert client.get(run.invoices.first().get_absolute_url()).status_code == 403


def test_water_sample_adds_the_fee_plan(db):
    from django.core.management import call_command

    from apps.invoicing.models import FeePlan

    call_command("load_sample_setup", "water")

    plan = FeePlan.objects.get()
    lines = list(plan.lines.values_list("kind", "description", "unit_price"))
    assert plan.name == "Kommunal vattenavgift"
    assert lines == [
        ("fixed", "Grundavgift {period}", D("120.0000")),
        ("usage", "Vatten {period}", D("1.5000")),
    ]


def test_fee_plan_links_for_staff_who_may_see_them(make_user, client, settings):
    settings.REQUIRE_MFA = False
    plans = reverse("admin:invoicing_feeplan_changelist")
    billing = reverse("admin:invoicing_billingsettings_changelist")
    client.force_login(make_user("tina", "Treasurer", is_staff=True))

    runs = client.get(reverse("invoicing:run_list"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    form = client.get(reverse("invoicing:run_create"), HTTP_ACCEPT_LANGUAGE="en").content.decode()

    assert f'href="{plans}"' in runs and f'href="{billing}"' in runs
    assert f'href="{plans}"' in form


def test_fee_plan_links_are_hidden_without_permission(role_client, make_user, client):
    plans = reverse("admin:invoicing_feeplan_changelist")
    billing = reverse("admin:invoicing_billingsettings_changelist")
    # Board may view invoicing but is no staff; a Treasurer who is no staff cannot open Settings.
    for user in [make_user("bo", "Board"), make_user("tre", "Treasurer")]:
        client.force_login(user)
        page = client.get(reverse("invoicing:run_list"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
        assert plans not in page and billing not in page
        assert "under Settings > Invoice settings" in page


def _primary_buttons(page):
    return page.count("button--primary")


def test_run_page_shows_the_steps_with_one_primary_button(treasurer_client, run):
    page = treasurer_client.get(run.get_absolute_url(), HTTP_ACCEPT_LANGUAGE="en").content.decode()

    # One draft has a problem, one is ready: checking is the current step and
    # issuing the ready one is the only primary action.
    assert page.index("1 · Check") < page.index("2 · Issue") < page.index("3 · Send")
    assert 'class="step step--current"' in page.split("2 · Issue")[0]
    assert "Issue 1 invoice</button>" in page
    assert _primary_buttons(page.split('<ol class="steps">')[1].split("</ol>")[0]) == 1
    assert 'class="crumbs"' in page and reverse("invoicing:run_list") in page


def test_run_page_offers_sending_once_everything_is_issued(treasurer_client, run):
    run.invoices.filter(unit__name="Bystigen 6").delete()
    treasurer_client.post(reverse("invoicing:run_issue", args=[run.pk]))

    page = treasurer_client.get(run.get_absolute_url(), HTTP_ACCEPT_LANGUAGE="en").content.decode()

    assert "Nothing to issue." in page
    assert 'class="button button--primary">Send 1 invoice</button>' in page


def test_invoice_pages_share_tabs(treasurer_client, run):
    for name, current in (
        ("invoicing:invoice_list", "All invoices"),
        ("invoicing:overdue_list", "Overdue invoices"),
        ("invoicing:run_list", "Invoice runs"),
    ):
        page = treasurer_client.get(reverse(name), HTTP_ACCEPT_LANGUAGE="en").content.decode()
        tabs = page.split('class="filter-tabs"')[1].split("</nav>")[0]
        assert f'aria-current="page">{current}</a>' in tabs
        assert tabs.count('aria-current="page"') == 1
