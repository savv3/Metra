from django.db import migrations

from apps.plugins import api

SETTINGS = ["postingsettings", "salesaccount", "vatregistration"]


def perms(*actions, models):
    return [f"metra_bookkeeping.{action}_{model}" for model in models for action in actions]


class Migration(migrations.Migration):
    dependencies = [("metra_bookkeeping", "0005_more_locks"), ("accounts", "0001_roles")]
    operations = [
        api.grant_to_roles(
            {
                # Postings are made by the add-on, never by hand, so no role
                # adds, changes or deletes them.
                "Admin": [
                    *perms("view", "add", "change", "delete", models=SETTINGS),
                    "metra_bookkeeping.view_posting",
                ],
                "Treasurer": [
                    *perms("view", "add", "change", "delete", models=SETTINGS),
                    "metra_bookkeeping.view_posting",
                ],
                "Board": perms("view", models=[*SETTINGS, "posting"]),
                "Read-only": perms("view", models=[*SETTINGS, "posting"]),
            }
        ),
    ]
