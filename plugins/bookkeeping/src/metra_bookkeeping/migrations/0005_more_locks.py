"""More of what posted entries depend on cannot change in the database
itself (KPL 2:7), as in 0003:

- an account with lines on posted vouchers keeps its number and kind, and
  cannot be deleted;
- a voucher series with posted vouchers keeps its code, which is part of the
  voucher numbers;
- the link from a posted voucher to the invoice, payment or reminder it
  books never changes.

0004 rebuilt the voucher line table (SQLite does that to add a constraint),
which drops its triggers, so the triggers of 0003 are made again here."""

from importlib import import_module

from django.db import migrations

locks = import_module("metra_bookkeeping.migrations.0003_locks")

A = "metra_bookkeeping_account"
S = "metra_bookkeeping_voucherseries"
P = "metra_bookkeeping_posting"
V = locks.V
L = locks.L
POSTED = locks.POSTED

ACCOUNT_USED = f"""EXISTS (
    SELECT 1 FROM {L} JOIN {V} ON {V}.id = {L}.voucher_id
    WHERE {L}.account_id = OLD.id AND {V}.status = {POSTED})"""

TRIGGERS = {
    "bookkeeping_account_no_change": f"""
        CREATE TRIGGER bookkeeping_account_no_change BEFORE UPDATE ON {A}
        WHEN (NEW.number IS NOT OLD.number OR NEW.kind IS NOT OLD.kind) AND {ACCOUNT_USED}
        BEGIN SELECT RAISE(ABORT, 'An account with posted entries keeps its number and kind.');
        END""",
    "bookkeeping_account_no_delete": f"""
        CREATE TRIGGER bookkeeping_account_no_delete BEFORE DELETE ON {A}
        WHEN {ACCOUNT_USED}
        BEGIN SELECT RAISE(ABORT, 'An account with posted entries cannot be deleted.'); END""",
    "bookkeeping_series_no_change": f"""
        CREATE TRIGGER bookkeeping_series_no_change BEFORE UPDATE ON {S}
        WHEN NEW.code IS NOT OLD.code AND EXISTS (
            SELECT 1 FROM {V} WHERE {V}.series_id = OLD.id AND {V}.status = {POSTED})
        BEGIN SELECT RAISE(ABORT, 'A series with posted vouchers keeps its code.'); END""",
    "bookkeeping_series_no_delete": f"""
        CREATE TRIGGER bookkeeping_series_no_delete BEFORE DELETE ON {S}
        WHEN EXISTS (SELECT 1 FROM {V} WHERE {V}.series_id = OLD.id)
        BEGIN SELECT RAISE(ABORT, 'A series with vouchers cannot be deleted.'); END""",
    "bookkeeping_posting_no_update": f"""
        CREATE TRIGGER bookkeeping_posting_no_update BEFORE UPDATE ON {P}
        BEGIN SELECT RAISE(ABORT, 'A posting cannot change.'); END""",
    "bookkeeping_posting_no_delete": f"""
        CREATE TRIGGER bookkeeping_posting_no_delete BEFORE DELETE ON {P}
        WHEN {locks.posted("OLD.voucher_id")}
        BEGIN SELECT RAISE(ABORT, 'The posting of a posted voucher cannot be removed.'); END""",
}


def again(name, sql):
    return migrations.RunSQL(
        [f"DROP TRIGGER IF EXISTS {name}", sql], migrations.RunSQL.noop
    )


class Migration(migrations.Migration):
    dependencies = [("metra_bookkeeping", "0004_postings")]
    operations = [
        *(again(name, sql) for name, sql in locks.TRIGGERS.items()),
        *(
            migrations.RunSQL(sql, f"DROP TRIGGER IF EXISTS {name}")
            for name, sql in TRIGGERS.items()
        ),
    ]
