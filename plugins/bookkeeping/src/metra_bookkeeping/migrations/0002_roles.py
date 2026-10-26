from django.db import migrations

from apps.plugins import api

MODELS = ["fiscalyear", "account", "voucherseries", "voucher", "voucherline", "receipt"]


def perms(*actions, models=MODELS):
    return [f"metra_bookkeeping.{action}_{model}" for model in models for action in actions]


class Migration(migrations.Migration):
    dependencies = [("metra_bookkeeping", "0001_initial"), ("accounts", "0001_roles")]
    operations = [
        api.grant_to_roles(
            {
                # The treasurer keeps the books: the chart of accounts, the
                # years and the vouchers. Posted vouchers never change, so
                # "delete" only removes drafts and accounts without entries.
                "Admin": [
                    *perms("view", "add", "change", "delete"),
                    "metra_bookkeeping.post_voucher",
                ],
                "Treasurer": [
                    *perms("view", "add", "change", "delete"),
                    "metra_bookkeeping.post_voucher",
                ],
                # The board answers for the books and reads them, and so can
                # someone with the read-only role, such as the auditor.
                "Board": perms("view"),
                "Read-only": perms("view"),
            }
        ),
    ]
