"""Posted vouchers, their lines and their receipts cannot change in the
database itself, whatever code or tool writes to it (KPL 2:7): the model
methods refuse it, and these triggers also stop queryset updates and
deletes, data migrations and raw SQL. Posting itself (a draft becoming
posted) and adding receipts are allowed; the user columns may be emptied
when a user is deleted (the audit log keeps who did what)."""

from django.db import migrations

V = "metra_bookkeeping_voucher"
L = "metra_bookkeeping_voucherline"
R = "metra_bookkeeping_receipt"
POSTED = "'posted'"

# Every column of a voucher except the two users.
VOUCHER_COLUMNS = [
    "id",
    "year_id",
    "series_id",
    "number",
    "date",
    "description",
    "kind",
    "status",
    "reverses_id",
    "created_at",
    "posted_at",
]
RECEIPT_COLUMNS = ["id", "voucher_id", "file", "name", "size", "content_type", "uploaded_at"]


def changed(columns):
    return " OR ".join(f"NEW.{c} IS NOT OLD.{c}" for c in columns)


def posted(voucher_id):
    return f"(SELECT status FROM {V} WHERE id = {voucher_id}) = {POSTED}"


TRIGGERS = {
    "bookkeeping_voucher_no_update": f"""
        CREATE TRIGGER bookkeeping_voucher_no_update BEFORE UPDATE ON {V}
        WHEN OLD.status = {POSTED} AND ({changed(VOUCHER_COLUMNS)})
        BEGIN SELECT RAISE(ABORT, 'A posted voucher cannot change.'); END""",
    "bookkeeping_voucher_no_delete": f"""
        CREATE TRIGGER bookkeeping_voucher_no_delete BEFORE DELETE ON {V}
        WHEN OLD.status = {POSTED}
        BEGIN SELECT RAISE(ABORT, 'A posted voucher cannot be deleted.'); END""",
    "bookkeeping_line_no_insert": f"""
        CREATE TRIGGER bookkeeping_line_no_insert BEFORE INSERT ON {L}
        WHEN {posted("NEW.voucher_id")}
        BEGIN SELECT RAISE(ABORT, 'A posted voucher cannot get new lines.'); END""",
    "bookkeeping_line_no_update": f"""
        CREATE TRIGGER bookkeeping_line_no_update BEFORE UPDATE ON {L}
        WHEN {posted("OLD.voucher_id")} OR {posted("NEW.voucher_id")}
        BEGIN SELECT RAISE(ABORT, 'The lines of a posted voucher cannot change.'); END""",
    "bookkeeping_line_no_delete": f"""
        CREATE TRIGGER bookkeeping_line_no_delete BEFORE DELETE ON {L}
        WHEN {posted("OLD.voucher_id")}
        BEGIN SELECT RAISE(ABORT, 'The lines of a posted voucher cannot be deleted.'); END""",
    "bookkeeping_receipt_no_update": f"""
        CREATE TRIGGER bookkeeping_receipt_no_update BEFORE UPDATE ON {R}
        WHEN {changed(RECEIPT_COLUMNS)}
        BEGIN SELECT RAISE(ABORT, 'A receipt cannot change.'); END""",
    "bookkeeping_receipt_no_delete": f"""
        CREATE TRIGGER bookkeeping_receipt_no_delete BEFORE DELETE ON {R}
        WHEN {posted("OLD.voucher_id")}
        BEGIN SELECT RAISE(ABORT, 'The receipt of a posted voucher cannot be removed.'); END""",
}


class Migration(migrations.Migration):
    dependencies = [("metra_bookkeeping", "0002_roles")]
    operations = [
        migrations.RunSQL(sql, f"DROP TRIGGER IF EXISTS {name}")
        for name, sql in TRIGGERS.items()
    ]
