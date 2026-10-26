import datetime
from decimal import Decimal

import pytest

from metra_bookkeeping import countries, statements
from metra_bookkeeping.models import Account, Budget, FiscalYear, Voucher

D = datetime.date
FI = countries.get("fi")


def rows(statement, column=0):
    """{line name: amount} of the rows with amounts."""
    return {row.name: row.amounts[column] for row in statement.rows if row.show_amounts}


@pytest.mark.parametrize("chart", ["association", "cooperative"])
def test_every_template_account_is_on_a_line(chart):
    """An account of a chart template always lands in the statements."""
    income_statement = FI.INCOME_STATEMENTS[chart]
    for account in FI.CHARTS[chart].accounts:
        fmt = income_statement if account.kind in ("income", "expense") else FI.BALANCE_SHEET
        line = fmt.line_for(account.number)
        assert line is not None, account.number
        if fmt is FI.BALANCE_SHEET:
            # Assets on the assets side, the rest on the other.
            on_assets = any(item is line for item in FI.BALANCE_SHEET.sides[0].walk())
            assert on_assets == (account.kind == "asset"), account.number


def test_lines_do_not_overlap():
    for fmt in [*FI.INCOME_STATEMENTS.values(), FI.BALANCE_SHEET]:
        ranges = [r for side in fmt.sides for line in side.walk() for r in line.accounts]
        ranges.sort()
        for (_first, last), (next_first, _) in zip(ranges, ranges[1:], strict=False):
            assert last < next_first, (fmt.key, last, next_first)


def test_the_association_statement_follows_annex_iv(make_voucher, year):
    make_voucher(
        [("1910", "1000.00", "0"), ("2250", "0", "1000.00")],
        date=D(2026, 1, 1),
        kind=Voucher.Kind.OPENING,
    ).post()
    make_voucher([("1910", "800.00", "0"), ("3000", "0", "800.00")], date=D(2026, 2, 1)).post()
    make_voucher([("4610", "120.00", "0"), ("1910", "0", "120.00")], date=D(2026, 2, 3)).post()
    make_voucher([("5000", "200.00", "0"), ("1910", "0", "200.00")], date=D(2026, 2, 4)).post()
    make_voucher([("1910", "500.00", "0"), ("6000", "0", "500.00")], date=D(2026, 1, 20)).post()
    make_voucher([("7500", "99.00", "0"), ("1910", "0", "99.00")], date=D(2026, 2, 4))  # draft

    statement = statements.income_statement(year, year.start, year.end)
    names = [row.name for row in statement.rows]
    assert names == [
        "Varsinainen toiminta",
        "Tuotot",
        "Kulut",
        "Henkilöstökulut",
        "Muut kulut",
        "Tuotto-/Kulujäämä",
        "Varainhankinta",
        "Tuotot",
        "Tuotto-/Kulujäämä",
        "Tilikauden tulos",
        "Tilikauden ylijäämä (alijäämä)",
    ]
    results = [row.amounts[0] for row in statement.rows if row.kind == "result"]
    assert results == [Decimal("480.00"), Decimal("500.00"), Decimal("980.00"), Decimal("980.00")]
    kulut = next(row for row in statement.rows if row.name == "Kulut")
    assert kulut.amounts == [Decimal("-320.00")]
    # The section heading shows no sum of its own; its result line does.
    assert not statement.rows[0].show_amounts
    assert statement.unmapped == []
    assert len(statement.columns) == 1  # no previous year in the books

    swedish = statements.income_statement(year, year.start, year.end, language="sv")
    assert swedish.rows[0].name == "Ordinarie verksamhet"
    assert swedish.title == "Resultaträkning"

    micro = statements.income_statement(year, year.start, year.end, micro=True)
    assert "Henkilöstökulut" not in [row.name for row in micro.rows]
    assert rows(micro)["Kulut"] == Decimal("-320.00")


def test_the_cooperative_statement_follows_annex_i(make_voucher, year, chart):
    year.chart = "cooperative"
    year.save()
    for number, name, kind in [
        ("6800", "Poistot", "expense"),
        ("7200", "Korjaukset", "expense"),
        ("8800", "Korkokulut", "expense"),
    ]:
        chart[number] = Account.objects.get_or_create(
            number=number, defaults={"name": name, "kind": kind}
        )[0]
    make_voucher([("1910", "1000.00", "0"), ("3000", "0", "1000.00")], date=D(2026, 3, 1)).post()
    make_voucher([("4400", "300.00", "0"), ("1910", "0", "300.00")], date=D(2026, 3, 2)).post()
    make_voucher([("6800", "100.00", "0"), ("1120", "0", "100.00")], date=D(2026, 3, 3)).post()
    make_voucher([("7200", "50.00", "0"), ("1910", "0", "50.00")], date=D(2026, 3, 4)).post()
    make_voucher([("8800", "10.00", "0"), ("1910", "0", "10.00")], date=D(2026, 3, 5)).post()

    amounts = rows(statements.income_statement(year, year.start, year.end))
    assert amounts["LIIKEVAIHTO"] == Decimal("1000.00")
    assert amounts["Ulkopuoliset palvelut"] == Decimal("-300.00")
    assert amounts["Suunnitelman mukaiset poistot"] == Decimal("-100.00")
    assert amounts["Liiketoiminnan muut kulut"] == Decimal("-50.00")
    assert amounts["LIIKEVOITTO (-TAPPIO)"] == Decimal("550.00")
    assert amounts["Korkokulut ja muut rahoituskulut"] == Decimal("-10.00")
    assert amounts["VOITTO (TAPPIO) ENNEN TILINPÄÄTÖSSIIRTOJA JA VEROJA"] == Decimal("540.00")
    assert amounts["TILIKAUDEN VOITTO (TAPPIO)"] == Decimal("540.00")
    # Lines with nothing in them are left out.
    assert "Valmistus omaan käyttöön" not in amounts


def test_an_account_outside_the_format_is_listed(make_voucher, year, chart):
    odd = Account.objects.create(number="39999", name="Odd income", kind="income")
    chart["39999"] = odd
    make_voucher([("1910", "10.00", "0"), ("39999", "0", "10.00")]).post()
    statement = statements.income_statement(year, year.start, year.end)
    assert statement.unmapped == [odd]


def test_the_previous_year_is_beside_it(make_voucher, year):
    before = FiscalYear.objects.create(start=D(2025, 1, 1), end=D(2025, 12, 31))
    make_voucher([("1910", "300.00", "0"), ("6000", "0", "300.00")], date=D(2025, 5, 1)).post()
    make_voucher([("1910", "400.00", "0"), ("6000", "0", "400.00")], date=D(2026, 5, 1)).post()
    statement = statements.income_statement(year, year.start, year.end)
    assert [column.year for column in statement.columns] == [year, before]
    assert [c.label for c in statement.columns] == ["1.1.–31.12.2026", "1.1.–31.12.2025"]
    assert rows(statement)["Tuotot"] == Decimal("400.00")
    assert rows(statement, 1)["Tuotot"] == Decimal("300.00")
    # A part of the year is compared with the same dates a year earlier.
    spring = statements.income_statement(year, D(2026, 1, 1), D(2026, 4, 30))
    assert [(c.start, c.end) for c in spring.columns][1] == (D(2025, 1, 1), D(2025, 4, 30))
    assert rows(spring, 1).get("Tuotot") is None  # nothing in either: left out
    alone = statements.income_statement(year, year.start, year.end, compare=False)
    assert len(alone.columns) == 1


def test_the_balance_sheet_balances_with_the_result_for_the_year(make_voucher, year, chart):
    chart["2610"].long_term = True
    chart["2610"].save()
    make_voucher(
        [("1910", "5000.00", "0"), ("2250", "0", "2000.00"), ("2610", "0", "3000.00")],
        date=D(2026, 1, 1),
        kind=Voucher.Kind.OPENING,
    ).post()
    make_voucher([("1700", "800.00", "0"), ("3000", "0", "800.00")], date=D(2026, 2, 1)).post()
    make_voucher([("4610", "120.00", "0"), ("2871", "0", "120.00")], date=D(2026, 2, 3)).post()

    sheet = statements.balance_sheet(year, year.end)
    amounts = rows(sheet)
    assert amounts["Myyntisaamiset"] == Decimal("800.00")
    assert amounts["Rahat ja pankkisaamiset"] == Decimal("5000.00")
    assert amounts["Vastaavaa yhteensä"] == Decimal("5800.00")
    assert amounts["Edellisten tilikausien voitto (tappio)"] == Decimal("2000.00")
    assert amounts["Tilikauden voitto (tappio)"] == Decimal("680.00")
    assert amounts["Lainat rahoituslaitoksilta"] == Decimal("3000.00")
    assert amounts["Ostovelat"] == Decimal("120.00")
    assert amounts["josta pitkäaikaista"] == Decimal("3000.00")
    assert amounts["Vastattavaa yhteensä"] == Decimal("5800.00")
    assert sheet.balances

    # At an earlier day, from the year's entries up to it.
    january = rows(statements.balance_sheet(year, D(2026, 1, 31)))
    assert january["Vastaavaa yhteensä"] == Decimal("5000.00")
    assert "Tilikauden voitto (tappio)" in january  # always shown, here 0

    micro = statements.balance_sheet(year, year.end, micro=True)
    names = [row.name for row in micro.rows]
    assert "Myyntisaamiset" not in names and "Saamiset" in names
    assert rows(micro)["josta lyhytaikaista"] == Decimal("120.00")
    assert micro.balances


def test_size_class(make_voucher, year, chart):
    make_voucher([("1910", "500.00", "0"), ("3000", "0", "500.00")]).post()
    size = statements.size_class(year)
    assert size.key == "micro"
    assert size.provisional

    # Over two micro limits in one of the two years: small, to be safe.
    before = FiscalYear.objects.create(start=D(2025, 1, 1), end=D(2025, 12, 31), staff=11)
    make_voucher([("1910", "950000.00", "0"), ("3000", "0", "950000.00")], date=D(2025, 6, 1))
    Voucher.objects.get(year=before).post()
    assert statements.size_class(year).key == "small"
    assert statements.size_class(year).years[1].over_micro == 3

    before.staff = 60
    before.save()
    make_voucher([("1910", "16000000.00", "0"), ("3000", "0", "16000000.00")], date=D(2025, 7, 1))
    Voucher.objects.filter(year=before, status="draft").get().post()
    assert statements.size_class(year).key == "larger"


def test_turnover_is_counted_for_twelve_months(make_voucher, year):
    half = year
    half.end, half.length_reason = D(2026, 6, 30), FiscalYear.Length.FIRST
    half.save()
    make_voucher([("1910", "100.00", "0"), ("3000", "0", "100.00")], date=D(2026, 2, 1)).post()
    assert statements.turnover(half) == Decimal("200.00")


def test_budget_against_actual(make_voucher, year, chart):
    Budget.objects.create(year=year, account=chart["6000"], amount=Decimal("1000"))
    Budget.objects.create(year=year, account=chart["4610"], amount=Decimal("400"))
    make_voucher([("1910", "600.00", "0"), ("6000", "0", "600.00")]).post()
    make_voucher([("4610", "100.00", "0"), ("1910", "0", "100.00")]).post()
    make_voucher([("4700", "50.00", "0"), ("1910", "0", "50.00")]).post()

    income, expenses, totals = statements.budget_report(year, year.start, year.end)
    assert [(r.account.number, r.budget, r.actual) for r in income] == [
        ("6000", Decimal("1000"), Decimal("600.00"))
    ]
    assert income[0].used == 60
    assert [(r.account.number, r.budget, r.actual) for r in expenses] == [
        ("4610", Decimal("400"), Decimal("100.00")),
        ("4700", Decimal("0"), Decimal("50.00")),
    ]
    assert expenses[1].used is None
    assert totals["result"].budget == Decimal("600")
    assert totals["result"].actual == Decimal("450.00")
