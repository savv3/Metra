"""Locked periods and closed years hold in the database itself, as posted
vouchers do (0003, 0005):

- a closed year never changes or goes away, and gets no new vouchers or
  receipts; its chart of accounts, notes and bank balances are fixed;
- no voucher is posted on or before the day a year is locked until, and that
  day only moves forward;
- a year with posted vouchers keeps its dates.

0010 dropped the triggers of 0003 and 0005 to rebuild the voucher table, so
they are made again here, the voucher one now also covering the year a
correction is for."""

from importlib import import_module

from django.db import migrations

locks = import_module("metra_bookkeeping.migrations.0003_locks")
more = import_module("metra_bookkeeping.migrations.0005_more_locks")

Y = "metra_bookkeeping_fiscalyear"
V = locks.V
R = locks.R
C = "metra_bookkeeping_chartentry"
N = "metra_bookkeeping_yearnote"
B = "metra_bookkeeping_bankbalance"
POSTED = locks.POSTED
CLOSED = "'closed'"

VOUCHER_COLUMNS = [*locks.VOUCHER_COLUMNS, "corrects_id"]
# Every column of a year except the user who closed it, which is emptied
# when that user is deleted (the audit log keeps who did what).
YEAR_COLUMNS = [
    "id",
    "start",
    '"end"',
    "status",
    "country",
    "chart",
    "length_reason",
    "staff",
    "created_at",
    "locked_until",
    "signers",
    "retained_earnings_id",
    "closed_at",
]


def closed(year_id):
    return f"(SELECT status FROM {Y} WHERE id = {year_id}) = {CLOSED}"


def fixed_in_closed_year(table, what):
    return {
        f"bookkeeping_{what}_closed_insert": f"""
            CREATE TRIGGER bookkeeping_{what}_closed_insert BEFORE INSERT ON {table}
            WHEN {closed("NEW.year_id")}
            BEGIN SELECT RAISE(ABORT, 'A closed financial year cannot change.'); END""",
        f"bookkeeping_{what}_closed_update": f"""
            CREATE TRIGGER bookkeeping_{what}_closed_update BEFORE UPDATE ON {table}
            WHEN {closed("OLD.year_id")} OR {closed("NEW.year_id")}
            BEGIN SELECT RAISE(ABORT, 'A closed financial year cannot change.'); END""",
        f"bookkeeping_{what}_closed_delete": f"""
            CREATE TRIGGER bookkeeping_{what}_closed_delete BEFORE DELETE ON {table}
            WHEN {closed("OLD.year_id")}
            BEGIN SELECT RAISE(ABORT, 'A closed financial year cannot change.'); END""",
    }


VOUCHER_YEAR = f"(SELECT %s FROM {Y} WHERE id = NEW.year_id)"

TRIGGERS = {
    # 0003's trigger with the new column.
    "bookkeeping_voucher_no_update": f"""
        CREATE TRIGGER bookkeeping_voucher_no_update BEFORE UPDATE ON {V}
        WHEN OLD.status = {POSTED} AND ({locks.changed(VOUCHER_COLUMNS)})
        BEGIN SELECT RAISE(ABORT, 'A posted voucher cannot change.'); END""",
    "bookkeeping_year_closed_no_update": f"""
        CREATE TRIGGER bookkeeping_year_closed_no_update BEFORE UPDATE ON {Y}
        WHEN OLD.status = {CLOSED} AND ({locks.changed(YEAR_COLUMNS)})
        BEGIN SELECT RAISE(ABORT, 'A closed financial year cannot change.'); END""",
    "bookkeeping_year_closed_no_delete": f"""
        CREATE TRIGGER bookkeeping_year_closed_no_delete BEFORE DELETE ON {Y}
        WHEN OLD.status = {CLOSED}
        BEGIN SELECT RAISE(ABORT, 'A closed financial year cannot be deleted.'); END""",
    "bookkeeping_year_lock_forward": f"""
        CREATE TRIGGER bookkeeping_year_lock_forward BEFORE UPDATE ON {Y}
        WHEN OLD.locked_until IS NOT NULL
            AND (NEW.locked_until IS NULL OR NEW.locked_until < OLD.locked_until)
        BEGIN SELECT RAISE(ABORT, 'A locked period cannot be opened again.'); END""",
    "bookkeeping_year_dates_fixed": f"""
        CREATE TRIGGER bookkeeping_year_dates_fixed BEFORE UPDATE ON {Y}
        WHEN (NEW.start IS NOT OLD.start OR NEW."end" IS NOT OLD."end") AND EXISTS (
            SELECT 1 FROM {V} WHERE {V}.year_id = OLD.id AND {V}.status = {POSTED})
        BEGIN SELECT RAISE(ABORT, 'A year with posted vouchers keeps its dates.'); END""",
    "bookkeeping_voucher_closed_insert": f"""
        CREATE TRIGGER bookkeeping_voucher_closed_insert BEFORE INSERT ON {V}
        WHEN {closed("NEW.year_id")}
        BEGIN SELECT RAISE(ABORT, 'A closed financial year gets no new vouchers.'); END""",
    "bookkeeping_voucher_closed_update": f"""
        CREATE TRIGGER bookkeeping_voucher_closed_update BEFORE UPDATE ON {V}
        WHEN OLD.status <> {POSTED} AND ({closed("OLD.year_id")} OR {closed("NEW.year_id")})
        BEGIN SELECT RAISE(ABORT, 'A closed financial year cannot change.'); END""",
    "bookkeeping_voucher_post_locked": f"""
        CREATE TRIGGER bookkeeping_voucher_post_locked BEFORE UPDATE ON {V}
        WHEN NEW.status = {POSTED} AND OLD.status <> {POSTED}
            AND NEW.date <= {VOUCHER_YEAR % "locked_until"}
        BEGIN SELECT RAISE(ABORT, 'The period is locked.'); END""",
    "bookkeeping_receipt_closed_insert": f"""
        CREATE TRIGGER bookkeeping_receipt_closed_insert BEFORE INSERT ON {R}
        WHEN {closed(f"(SELECT year_id FROM {V} WHERE id = NEW.voucher_id)")}
        BEGIN SELECT RAISE(ABORT, 'A closed financial year cannot change.'); END""",
    **fixed_in_closed_year(C, "chart"),
    **fixed_in_closed_year(N, "note"),
    **fixed_in_closed_year(B, "bank"),
}

# 0003's triggers, but the one replaced above. (The chart entries are written
# in the transaction that closes the year, before its status changes, so
# their insert trigger lets them in.)
OLD_TRIGGERS = {name: sql for name, sql in locks.TRIGGERS.items() if name not in TRIGGERS}


def again(name, sql):
    return migrations.RunSQL([f"DROP TRIGGER IF EXISTS {name}", sql], migrations.RunSQL.noop)


class Migration(migrations.Migration):
    dependencies = [("metra_bookkeeping", "0010_year_end")]
    operations = [
        *(again(name, sql) for name, sql in OLD_TRIGGERS.items()),
        *(again(name, sql) for name, sql in more.TRIGGERS.items()),
        *(
            migrations.RunSQL(
                [f"DROP TRIGGER IF EXISTS {name}", sql], f"DROP TRIGGER IF EXISTS {name}"
            )
            for name, sql in TRIGGERS.items()
        ),
    ]
