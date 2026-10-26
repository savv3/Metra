"""The financial statements: the income statement and the balance sheet in
the formats of the country's rules (for Finland the PMA decree 1753/2015),
the size class that decides how short they may be, and the budget
follow-up. Only posted vouchers count.

Each account goes to the line of the format its number falls in (see
countries.Line), so the statements need no setup. Accounts that fall on no
line are listed, never left out silently, since the statements would then
not agree with the books.
"""

import datetime
from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Sum

from . import countries
from .models import Account, Budget, FiscalYear, Voucher, VoucherLine, months_between

ZERO = Decimal("0.00")
INCOME_STATEMENT_KINDS = (Account.Kind.INCOME, Account.Kind.EXPENSE)
BALANCE_SHEET_KINDS = (Account.Kind.ASSET, Account.Kind.LIABILITY, Account.Kind.EQUITY)


def _lines(year, start, end):
    return VoucherLine.objects.filter(
        voucher__year=year,
        voucher__status=Voucher.Status.POSTED,
        voucher__date__range=(start, end),
    )


def account_sums(year, start, end, kinds):
    """{account: (debit minus credit, of which on long-term accounts)} for
    the accounts of ``kinds`` with posted entries from ``start`` to ``end``."""
    rows = (
        _lines(year, start, end)
        .filter(account__kind__in=kinds)
        .values("account")
        .annotate(debit=Sum("debit"), credit=Sum("credit"))
    )
    sums = {row["account"]: (row["debit"] or ZERO) - (row["credit"] or ZERO) for row in rows}
    accounts = Account.objects.in_bulk(list(sums))
    return {accounts[pk]: amount for pk, amount in sums.items()}


def result(year, start, end):
    """Income less expenses from ``start`` to ``end``: the profit or surplus."""
    return -sum(account_sums(year, start, end, INCOME_STATEMENT_KINDS).values(), ZERO)


# Periods and columns


@dataclass
class Column:
    year: FiscalYear
    start: datetime.date
    end: datetime.date
    label: str


def _day(date):
    return f"{date.day}.{date.month}.{date.year}"


def _years_back(date, years=1):
    try:
        return date.replace(year=date.year - years)
    except ValueError:  # 29 February
        return date.replace(year=date.year - years, day=28)


def comparison(year, start, end):
    """The same period of the previous financial year, or None: the whole
    year for a whole year, else the same dates a year earlier, within it."""
    previous = year.previous()
    if previous is None:
        return None
    if (start, end) == (year.start, year.end):
        return previous, previous.start, previous.end
    first, last = max(_years_back(start), previous.start), min(_years_back(end), previous.end)
    if first > last:
        return None
    return previous, first, last


def columns(year, start, end, compare=True, balance=False):
    """The period, and the previous year's beside it when there is one."""
    periods = [(year, start, end)]
    if compare and (before := comparison(year, start, end)):
        periods.append(before)
    return [
        Column(y, s, e, _day(e) if balance else f"{s.day}.{s.month}.–{_day(e)}")
        for y, s, e in periods
    ]


# Statements


@dataclass
class Row:
    name: str
    depth: int
    amounts: list
    kind: str = "item"  # heading, item, result, total or note
    lettered: bool = False
    added: bool = False
    # A heading whose section ends in a result line shows no sum of its own.
    show_amounts: bool = True


@dataclass
class Statement:
    format: countries.Format
    language: str
    columns: list
    texts: dict
    micro: bool = False
    rows: list = field(default_factory=list)
    # Accounts with an amount that are on no line of the format.
    unmapped: list = field(default_factory=list)
    # Assets less equity and liabilities, per column (balance sheet only).
    difference: list = field(default_factory=list)

    @property
    def title(self):
        return self.format.name(self.language)

    @property
    def balances(self):
        return not any(self.difference)

    @property
    def problems(self):
        """Why the statement is preliminary, in its own language. Printed on
        the PDF and CSV too, so an unfinished statement is never taken for
        the financial statements to be signed (KPL 3:1, 3:7). Until a year
        can be closed, every statement has one."""
        texts = self.texts
        reasons = []
        first = self.columns[0]
        if first.year.is_open:
            reasons.append(texts["open_year"])
        if (first.start, first.end) != (first.year.start, first.year.end):
            reasons.append(texts["part_of_year"])
        if self.unmapped:
            accounts = ", ".join(str(account) for account in self.unmapped)
            reasons.append(f"{texts['unmapped']} {accounts}")
        if not self.balances:
            reasons.append(texts["unbalanced"])
        return reasons


def _rules(year):
    return countries.get(year.country)


def _zeros(count):
    return [ZERO] * count


def _add(a, b):
    return [x + y for x, y in zip(a, b, strict=True)]


def _assign(fmt, sums_by_column, sign):
    """{id(line): [amount per column]} of the lines' own accounts, the same
    for their long-term accounts, and the accounts on no line."""
    own, long_term, unmapped = {}, {}, set()
    count = len(sums_by_column)
    for index, sums in enumerate(sums_by_column):
        for account, amount in sums.items():
            line = fmt.line_for(account.number)
            if line is None:
                if amount:
                    unmapped.add(account)
                continue
            own.setdefault(id(line), _zeros(count))[index] += sign(line) * amount
            if account.long_term:
                long_term.setdefault(id(line), _zeros(count))[index] += sign(line) * amount
    return own, long_term, sorted(unmapped, key=lambda account: account.number)


def _evaluate(lines, own, computed, values, count):
    """Work out each line's amounts into ``values``; return the sum of the
    lines that are not results (what a result line below them shows)."""
    total = _zeros(count)
    for line in lines:
        if line.result:
            values[id(line)] = list(total)
            continue
        if line.computed:
            amounts = list(computed[line.computed])
        else:
            below = _evaluate(line.lines, own, computed, values, count)
            amounts = _add(own.get(id(line), _zeros(count)), below)
        values[id(line)] = amounts
        total = _add(total, amounts)
    return total


class _Rows:
    """Turns a format's lines with their amounts into rows: lines with no
    amount this year or the year before are left out; a micro entity's
    lettered breakdowns too (PMA 4:1, 4:2)."""

    def __init__(self, statement, values, long_term):
        self.statement = statement
        self.values = values
        self.long_term = long_term
        self.count = len(statement.columns)

    def _long_term(self, line):
        total = _zeros(self.count)
        for item in line.walk():
            total = _add(total, self.long_term.get(id(item), _zeros(self.count)))
        return total

    def __call__(self, lines, depth):
        statement = self.statement
        rows = []
        for line in lines:
            if statement.micro and line.lettered:
                continue
            name = line.name(statement.language)
            amounts = self.values[id(line)]
            if line.result:
                rows.append(Row(name, depth, amounts, "result"))
                continue
            children = self(line.lines, depth + 1)
            if not (any(amounts) or line.computed or any(r.kind != "result" for r in children)):
                continue
            kind = "heading" if children else "item"
            ends_in_result = bool(children) and children[-1].kind == "result"
            rows.append(
                Row(name, depth, amounts, kind, line.lettered, line.added, not ends_in_result)
            )
            rows.extend(children)
            texts = statement.texts
            if kind == "item" and any(long := self._long_term(line)):
                rows.append(Row(texts["long_term"], depth + 1, long, "note"))
            if statement.micro and line.key == "liabilities":
                # A micro entity shows how much of its debt is short-term (PMA 4:2).
                short = [a - b for a, b in zip(amounts, self._long_term(line), strict=True)]
                rows.append(Row(texts["short_term"], depth + 1, short, "note"))
        return rows


def _statement(fmt, year, cols, sums, sign, computed, micro, language):
    own, long_term, unmapped = _assign(fmt, sums, sign)
    values = {}
    for side in fmt.sides:
        _evaluate([side], own, computed, values, len(cols))
    texts = {
        key: text[language] if language in text else text["en"]
        for key, text in _rules(year).TEXTS.items()
    }
    statement = Statement(fmt, language, cols, texts, micro, unmapped=unmapped)
    return statement, _Rows(statement, values, long_term), values


def income_statement(year, start, end, language="fi", compare=True, micro=False):
    """The income statement from ``start`` to ``end``: income positive,
    expenses negative, in the format for the year's kind of organisation."""
    fmt = _rules(year).INCOME_STATEMENTS[year.chart]
    cols = columns(year, start, end, compare)
    sums = [account_sums(c.year, c.start, c.end, INCOME_STATEMENT_KINDS) for c in cols]
    statement, rows, _values = _statement(
        fmt, year, cols, sums, lambda line: -1, {}, micro, language
    )
    statement.rows = rows(fmt.sides[0].lines, 0)
    return statement


def balance_sheet(year, end, language="fi", compare=True, micro=False):
    """The balance sheet at ``end``. The profit or surplus for the year so
    far is worked out from the income and expense accounts, so it shows
    before the year is closed."""
    fmt = _rules(year).BALANCE_SHEET
    cols = columns(year, year.start, end, compare, balance=True)
    assets, equity_and_liabilities = fmt.sides
    asset_lines = {id(line) for line in assets.walk()}
    sums = [account_sums(c.year, c.year.start, c.end, BALANCE_SHEET_KINDS) for c in cols]
    computed = {"result": [result(c.year, c.year.start, c.end) for c in cols]}
    statement, rows, values = _statement(
        fmt,
        year,
        cols,
        sums,
        lambda line: 1 if id(line) in asset_lines else -1,
        computed,
        micro,
        language,
    )
    for side, total in (
        (assets, "total_assets"),
        (equity_and_liabilities, "total_equity_and_liabilities"),
    ):
        statement.rows.append(
            Row(side.name(language), 0, values[id(side)], "heading", show_amounts=False)
        )
        statement.rows.extend(rows(side.lines, 1))
        statement.rows.append(Row(statement.texts[total], 0, values[id(side)], "total"))
    statement.difference = [
        a - b for a, b in zip(values[id(assets)], values[id(equity_and_liabilities)], strict=True)
    ]
    return statement


# Size class


@dataclass
class YearSize:
    year: FiscalYear
    balance_total: Decimal
    turnover: Decimal
    staff: Decimal
    over_micro: int
    over_small: int


@dataclass
class SizeClass:
    key: str  # micro, small or larger
    limits: countries.SizeLimits
    years: list

    @property
    def is_micro(self):
        return self.key == "micro"

    @property
    def provisional(self):
        return any(item.year.is_open for item in self.years)


def turnover(year):
    """The year's turnover, scaled to 12 months: net sales for a
    cooperative or company; for an association, all its income (the
    non-profit format has no net sales, and the larger figure keeps the
    size class on the safe side)."""
    fmt = _rules(year).INCOME_STATEMENTS[year.chart]
    sums = account_sums(year, year.start, year.end, INCOME_STATEMENT_KINDS)
    if year.chart == "association":
        amount = -sum(
            (amount for account, amount in sums.items() if account.kind == Account.Kind.INCOME),
            ZERO,
        )
    else:
        net_sales = next(line for line in fmt.sides[0].walk() if line.key == "net_sales")
        amount = -sum((a for acc, a in sums.items() if net_sales.covers(acc.number)), ZERO)
    months = months_between(year.start, year.end)
    return (amount * 12 / months).quantize(Decimal("0.01")) if months != 12 else amount


def balance_total(year):
    """The balance sheet total (assets) at the end of ``year``."""
    sums = account_sums(year, year.start, year.end, BALANCE_SHEET_KINDS)
    assets = list(_rules(year).BALANCE_SHEET.sides[0].walk())
    return sum(
        (
            amount
            for account, amount in sums.items()
            if any(line.covers(account.number) for line in assets)
        ),
        ZERO,
    )


def size_class(year):
    """The size class for the statements of ``year``, from it and the year
    before (KPL 1:4a, 1:4b). On the safe side: micro only when no more than
    one micro limit is exceeded in each year looked at, and "larger" (the
    small-entity decree no longer applies) as soon as one year exceeds more
    than one small limit. A full small-entity statement is always allowed;
    micro only allows leaving details out."""
    limits = countries.size_limits(year.start, year.country)
    years = [year] + ([before] if (before := year.previous()) else [])
    sizes = []
    for item in years:
        values = (balance_total(item), turnover(item), item.staff)
        sizes.append(
            YearSize(
                item,
                *values,
                over_micro=sum(v > limit for v, limit in zip(values, limits.micro, strict=True)),
                over_small=sum(v > limit for v, limit in zip(values, limits.small, strict=True)),
            )
        )
    if any(size.over_small > 1 for size in sizes):
        key = "larger"
    elif all(size.over_micro <= 1 for size in sizes):
        key = "micro"
    else:
        key = "small"
    return SizeClass(key, limits, sizes)


# Budget


@dataclass
class BudgetRow:
    account: Account
    budget: Decimal
    actual: Decimal

    @property
    def difference(self):
        return self.actual - self.budget

    @property
    def used(self):
        """How much of the budget the actual is, in per cent, or None."""
        if not self.budget:
            return None
        return (self.actual * 100 / self.budget).quantize(Decimal("1"))


def budget_report(year, start, end):
    """Each income and expense account with a budget or entries: the year's
    budget and the actual from ``start`` to ``end``, both positive for
    income expected and costs expected; and the totals. Returns (income
    rows, expense rows, totals)."""
    budgets = {
        line.account: line.amount
        for line in Budget.objects.filter(year=year).select_related("account")
    }
    actuals = account_sums(year, start, end, INCOME_STATEMENT_KINDS)
    accounts = sorted(set(budgets) | set(actuals), key=lambda account: account.number)
    income, expenses = [], []
    for account in accounts:
        actual = actuals.get(account, ZERO)
        if account.kind == Account.Kind.INCOME:
            income.append(BudgetRow(account, budgets.get(account, ZERO), -actual))
        else:
            expenses.append(BudgetRow(account, budgets.get(account, ZERO), actual))

    def total(rows):
        return BudgetRow(
            None, sum((r.budget for r in rows), ZERO), sum((r.actual for r in rows), ZERO)
        )

    totals = {"income": total(income), "expenses": total(expenses)}
    totals["result"] = BudgetRow(
        None,
        totals["income"].budget - totals["expenses"].budget,
        totals["income"].actual - totals["expenses"].actual,
    )
    return income, expenses, totals
