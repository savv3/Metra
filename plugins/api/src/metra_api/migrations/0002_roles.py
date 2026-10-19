"""Only Admin manages API clients: a client can act with a role's full
permissions, so making one is an admin's decision."""

from django.db import migrations

from apps.plugins import api


class Migration(migrations.Migration):
    dependencies = [("metra_api", "0001_initial"), ("accounts", "0001_roles")]
    operations = [
        api.grant_to_roles(
            {
                "Admin": [
                    "metra_api.view_apiclient",
                    "metra_api.add_apiclient",
                    "metra_api.change_apiclient",
                ]
            }
        ),
    ]
