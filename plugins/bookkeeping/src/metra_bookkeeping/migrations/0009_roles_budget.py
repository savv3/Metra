from django.db import migrations

from apps.plugins import api


def perms(*actions):
    return [f"metra_bookkeeping.{action}_budget" for action in actions]


class Migration(migrations.Migration):
    dependencies = [("metra_bookkeeping", "0008_statements"), ("accounts", "0001_roles")]
    operations = [
        api.grant_to_roles(
            {
                "Admin": perms("view", "add", "change", "delete"),
                "Treasurer": perms("view", "add", "change", "delete"),
                "Board": perms("view"),
                "Read-only": perms("view"),
            }
        ),
    ]
