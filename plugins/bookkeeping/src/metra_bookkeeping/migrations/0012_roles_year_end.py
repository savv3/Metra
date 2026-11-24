from django.db import migrations

from apps.plugins import api

MODELS = ["fixedasset", "bankbalance", "yearnote"]


def perms(*actions, models=MODELS):
    return [f"metra_bookkeeping.{action}_{model}" for model in models for action in actions]


class Migration(migrations.Migration):
    dependencies = [("metra_bookkeeping", "0011_year_end_locks"), ("accounts", "0001_roles")]
    operations = [
        api.grant_to_roles(
            {
                "Admin": [
                    *perms("view", "add", "change", "delete"),
                    "metra_bookkeeping.view_chartentry",
                    "metra_bookkeeping.close_fiscalyear",
                ],
                "Treasurer": [
                    *perms("view", "add", "change", "delete"),
                    "metra_bookkeeping.view_chartentry",
                    "metra_bookkeeping.close_fiscalyear",
                ],
                "Board": [*perms("view"), "metra_bookkeeping.view_chartentry"],
                "Read-only": [*perms("view"), "metra_bookkeeping.view_chartentry"],
            }
        ),
    ]
