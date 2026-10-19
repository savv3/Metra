from django.db import migrations

from apps.plugins import api


class Migration(migrations.Migration):
    dependencies = [("metra_webhooks", "0001_initial"), ("accounts", "0001_roles")]
    operations = [
        api.grant_to_roles(
            {
                "Admin": [
                    "metra_webhooks.add_webhookendpoint",
                    "metra_webhooks.change_webhookendpoint",
                    "metra_webhooks.view_webhookendpoint",
                    "metra_webhooks.delete_webhookendpoint",
                    "metra_webhooks.view_webhookdelivery",
                ],
            }
        ),
    ]
