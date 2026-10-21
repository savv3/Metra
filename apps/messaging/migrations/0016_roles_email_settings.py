"""Email settings: admins only."""

from django.db import migrations

from apps.plugins.roles import grant_to_roles


class Migration(migrations.Migration):
    dependencies = [
        ("messaging", "0015_email_settings"),
        ("accounts", "0001_roles"),
    ]

    operations = [
        grant_to_roles(
            {
                "Admin": [
                    "messaging.add_emailsettings",
                    "messaging.change_emailsettings",
                    "messaging.view_emailsettings",
                ]
            }
        )
    ]
